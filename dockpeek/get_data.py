import re
import logging
from flask import current_app
from .docker_utils import discover_docker_clients, get_container_status_with_exit_code, _get_link_hostname
from .update import update_checker

logger = logging.getLogger(__name__)


def get_all_data():
    """Return data for all Docker hosts, with Swarm support if enabled."""
    servers = discover_docker_clients()
    
    # Get configuration from Flask app
    TRAEFIK_ENABLE = current_app.config['TRAEFIK_ENABLE']
    TAGS_ENABLE = current_app.config['TAGS_ENABLE']
    
    if not servers:
        return {"servers": [], "containers": [], "swarm_servers": []}


    all_container_data = []
    swarm_servers = []
    server_list_for_json = [{"name": s["name"], "status": s["status"], "order": s["order"], "url": s["url"]} for s in servers]

    for host in servers:
        if host['status'] == 'inactive':
            continue
        
        try:
            server_name = host["name"]
            client = host["client"]
            public_hostname = host["public_hostname"]
            is_docker_host = host["is_docker_host"]

            # --- Swarm support ---
            try:
                info = client.info()
                is_swarm = info.get('Swarm', {}).get('LocalNodeState', '').lower() == 'active'
            except Exception:
                is_swarm = False

            if is_swarm:
                swarm_servers.append(server_name)
                # Swarm mode: show services/tasks as containers
                try:
                    services = client.services.list()
                    tasks = client.api.tasks()
                    nodes = {n['ID']: n for n in client.api.nodes()}
                    # Map tasks by service
                    tasks_by_service = {}
                    for t in tasks:
                        sid = t['ServiceID']
                        tasks_by_service.setdefault(sid, []).append(t)
                    for service in services:
                        s_attrs = service.attrs
                        spec = s_attrs.get('Spec', {})
                        labels = spec.get('Labels', {}) or {}
                        image_name = spec.get('TaskTemplate', {}).get('ContainerSpec', {}).get('Image', 'unknown')
                        stack_name = labels.get('com.docker.stack.namespace', '')
                        custom_url = labels.get('dockpeek.link', '')
                        custom_ports = labels.get('dockpeek.ports', '') or labels.get('dockpeek.port', '')
                        custom_tags = labels.get('dockpeek.tags', '') or labels.get('dockpeek.tag', '')
                        https_ports = labels.get('dockpeek.https', '')
                        source_url = labels.get('org.opencontainers.image.source') or labels.get('org.opencontainers.image.url', '')
                        # Parse tags
                        tags = []
                        if TAGS_ENABLE and custom_tags:
                            try:
                                tags = [tag.strip() for tag in custom_tags.split(',') if tag.strip()]
                            except:
                                tags = []
                        # Traefik routes
                        traefik_routes = []
                        if TRAEFIK_ENABLE and labels.get('traefik.enable', '').lower() != 'false':
                            for key, value in labels.items():
                                if key.startswith('traefik.http.routers.') and key.endswith('.rule'):
                                    router_name = key.split('.')[3]
                                    host_matches = re.findall(r'Host\(`([^`]+)`\)', value)
                                    for host_ in host_matches:
                                        tls_key = f'traefik.http.routers.{router_name}.tls'
                                        is_tls = labels.get(tls_key, '').lower() == 'true'
                                        entrypoints_key = f'traefik.http.routers.{router_name}.entrypoints'
                                        entrypoints = labels.get(entrypoints_key, '')
                                        is_https_entrypoint = False
                                        if entrypoints:
                                            entrypoint_list = [ep.strip().lower() for ep in entrypoints.split(',')]
                                            is_https_entrypoint = any(
                                                any(key in ep for key in ("https", "443", "secure", "ssl", "tls"))
                                                for ep in entrypoint_list
                                            )
                                        protocol = 'https' if is_tls or is_https_entrypoint else 'http'
                                        url = f"{protocol}://{host_}"
                                        path_match = re.search(r'PathPrefix\(`([^`]+)`\)', value)
                                        if path_match:
                                            url += path_match.group(1)
                                        traefik_routes.append({
                                            'router': router_name,
                                            'url': url,
                                            'rule': value,
                                            'host': host_
                                        })
                        # Ports
                        https_ports_list = []
                        if https_ports:
                            try:
                                https_ports_list = [str(port.strip()) for port in https_ports.split(',') if port.strip()]
                            except:
                                https_ports_list = []
                        port_map = []
                        custom_ports_list = []
                        if custom_ports:
                            try:
                                custom_ports_list = [str(port.strip()) for port in custom_ports.split(',') if port.strip()]
                            except:
                                custom_ports_list = []
                        # Published ports from Endpoint
                        endpoint = s_attrs.get('Endpoint', {})
                        ports = endpoint.get('Ports', [])
                        for p in ports:
                            host_port = str(p.get('PublishedPort'))
                            container_port = str(p.get('TargetPort'))
                            protocol = p.get('Protocol', 'tcp')
                            link_hostname = _get_link_hostname(public_hostname, None, is_docker_host)
                            is_https_port = (
                                container_port == "443" or
                                host_port == "443" or
                                host_port.endswith("443") or
                                host_port in https_ports_list
                            )
                            proto = "https" if is_https_port else "http"
                            if host_port == "443":
                                link = f"{proto}://{link_hostname}"
                            else:
                                link = f"{proto}://{link_hostname}:{host_port}"
                            port_map.append({
                                'container_port': f"{container_port}/{protocol}",
                                'host_port': host_port,
                                'link': link,
                                'is_custom': False
                            })
                        # Add custom ports
                        if custom_ports_list:
                            link_hostname = _get_link_hostname(public_hostname, None, is_docker_host)
                            for port in custom_ports_list:
                                is_https_port = (
                                    port == "443" or 
                                    port.endswith("443") or
                                    port in https_ports_list
                                )
                                proto = "https" if is_https_port else "http"
                                if port == "443":
                                    link = f"{proto}://{link_hostname}"
                                else:
                                    link = f"{proto}://{link_hostname}:{port}"
                                port_map.append({
                                    'container_port': '',
                                    'host_port': port,
                                    'link': link,
                                    'is_custom': True
                                })
                        # Status: summarize from tasks
                        service_tasks = tasks_by_service.get(service.id, [])
                        running = sum(1 for t in service_tasks if t['Status']['State'] == 'running')
                        total = len(service_tasks)
                        status = f"running ({running}/{total})" if total else "no-tasks"
                        exit_code = None
                        # Compose info
                        container_info = {
                            'server': server_name,
                            'name': spec.get('Name', service.name),
                            'status': status,
                            'exit_code': exit_code,
                            'image': image_name,
                            'stack': stack_name,
                            'source_url': source_url,
                            'custom_url': custom_url,
                            'ports': port_map,
                            'traefik_routes': traefik_routes,
                            'tags': tags
                        }
                        if TAGS_ENABLE:
                            container_info['tags'] = tags
                        # Update check: use image name as cache key
                        cache_key = update_checker.get_cache_key(server_name, service.name, image_name)
                        cached_update, is_cache_valid = update_checker.get_cached_result(cache_key)
                        if cached_update is not None and is_cache_valid:
                            container_info['update_available'] = cached_update
                        else:
                            # For Swarm, check local image update using the image name
                            try:
                                local_update = False
                                if image_name:
                                    local_image = client.images.get(image_name)
                                    # No container_image_id, so just skip or always False
                                    local_update = False
                                container_info['update_available'] = local_update
                            except Exception:
                                container_info['update_available'] = False
                        all_container_data.append(container_info)
                except Exception as swarm_error:
                    all_container_data.append({
                        'server': server_name,
                        'name': getattr(service, 'name', 'unknown'),
                        'status': 'swarm-error',
                        'image': 'error-loading',
                        'ports': []
                    })
                continue  # skip normal container listing if Swarm
            # --- End Swarm support ---

            # Normal container listing (non-Swarm)
            containers = client.containers.list(all=True)
            for container in containers:
                try:
                    original_image = container.attrs.get('Config', {}).get('Image', '')
                    if original_image:
                        image_name = original_image
                    else:
                        if hasattr(container, 'image') and container.image:
                            if hasattr(container.image, 'tags') and container.image.tags:
                                image_name = container.image.tags[0]
                            else:
                                image_name = container.image.id[:12] if hasattr(container.image, 'id') else "unknown"
                    # Check update cache
                    cache_key = update_checker.get_cache_key(server_name, container.name, image_name)
                    cached_update, is_cache_valid = update_checker.get_cached_result(cache_key)
                    
                    # Get status with health check information and exit codes
                    container_status, exit_code = get_container_status_with_exit_code(container)
                    start_time = container.attrs.get('State', {}).get('StartedAt', '')


                    # Get stack information from Docker Compose labels
                    labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
                    stack_name = labels.get('com.docker.compose.project', '')
                    
                    # Get source URL from OCI labels
                    source_url = (labels.get('org.opencontainers.image.source') or 
                                labels.get('org.opencontainers.image.url', ''))                             

                    # Get custom dockpeek labels
                    https_ports = labels.get('dockpeek.https', '')
                    custom_url = labels.get('dockpeek.link', '')
                    custom_ports = labels.get('dockpeek.ports', '') or labels.get('dockpeek.port', '')
                    custom_tags = labels.get('dockpeek.tags', '') or labels.get('dockpeek.tag', '')     

                    # Parse tags
                    tags = []
                    if TAGS_ENABLE and custom_tags:
                        try:
                            tags = [tag.strip() for tag in custom_tags.split(',') if tag.strip()]
                        except:
                            tags = []

                    # Extract Traefik routes
                    traefik_routes = []
                    if TRAEFIK_ENABLE and labels.get('traefik.enable', '').lower() != 'false':
                        for key, value in labels.items():
                            if key.startswith('traefik.http.routers.') and key.endswith('.rule'):
                                router_name = key.split('.')[3]

                                # Find all hosts in the rule
                                host_matches = re.findall(r'Host\(`([^`]+)`\)', value)

                                for host_ in host_matches:
                                    # Check if this router has TLS enabled
                                    tls_key = f'traefik.http.routers.{router_name}.tls'
                                    is_tls = labels.get(tls_key, '').lower() == 'true'

                                    # Check entrypoints to determine protocol
                                    entrypoints_key = f'traefik.http.routers.{router_name}.entrypoints'
                                    entrypoints = labels.get(entrypoints_key, '')

                                    is_https_entrypoint = False
                                    if entrypoints:
                                        entrypoint_list = [ep.strip().lower() for ep in entrypoints.split(',')]
                                        is_https_entrypoint = any(
                                            any(key in ep for key in ("https", "443", "secure", "ssl", "tls"))
                                            for ep in entrypoint_list
                                        )

                                    protocol = 'https' if is_tls or is_https_entrypoint else 'http'
                                    url = f"{protocol}://{host_}"

                                    # Check for PathPrefix
                                    path_match = re.search(r'PathPrefix\(`([^`]+)`\)', value)
                                    if path_match:
                                        url += path_match.group(1)

                                    traefik_routes.append({
                                        'router': router_name,
                                        'url': url,
                                        'rule': value,
                                        'host': host_
                                    })

                                    
                    # Parse HTTPS ports
                    https_ports_list = []
                    if https_ports:
                        try:
                            https_ports_list = [str(port.strip()) for port in https_ports.split(',') if port.strip()]
                        except:
                            https_ports_list = []
                    
                    # Port information with HTTPS detection
                    ports = container.attrs['NetworkSettings']['Ports']
                    port_map = []

                    # Parse custom ports for any container with dockpeek.ports label
                    custom_ports_list = []
                    if custom_ports:
                        try:
                            custom_ports_list = [str(port.strip()) for port in custom_ports.split(',') if port.strip()]
                        except:
                            custom_ports_list = []

                    # First, add standard mapped ports (only if no custom ports or for additional ports)
                    if ports:
                        for container_port, mappings in ports.items():
                            if mappings:
                                m = mappings[0]
                                host_port = m['HostPort']
                                host_ip = m.get('HostIp', '0.0.0.0')
                                link_hostname = _get_link_hostname(public_hostname, host_ip, is_docker_host)

                                # Check if this port should use HTTPS
                                is_https_port = (
                                    container_port == "443/tcp" or 
                                    host_port == "443" or 
                                    host_port.endswith("443") or
                                    str(host_port) in https_ports_list
                                )
                                protocol = "https" if is_https_port else "http"

                                if host_port == "443":
                                    link = f"{protocol}://{link_hostname}"
                                else:
                                    link = f"{protocol}://{link_hostname}:{host_port}"

                                port_map.append({
                                    'container_port': container_port,
                                    'host_port': host_port,
                                    'link': link,
                                    'is_custom': False
                                })

                    # Then, add custom ports if label is present
                    if custom_ports_list:
                        link_hostname = _get_link_hostname(public_hostname, None, is_docker_host)

                        for port in custom_ports_list:
                            # Check if this port should use HTTPS
                            is_https_port = (
                                port == "443" or 
                                port.endswith("443") or
                                port in https_ports_list
                            )
                            protocol = "https" if is_https_port else "http"

                            if port == "443":
                                link = f"{protocol}://{link_hostname}"
                            else:
                                link = f"{protocol}://{link_hostname}:{port}"

                            port_map.append({
                                'container_port': '',
                                'host_port': port,
                                'link': link,
                                'is_custom': True
                            })
                    container_info = {
                         'server': server_name,
                         'name': container.name,
                         'status': container_status,
                         'started_at': start_time,
                         'exit_code': exit_code,
                         'image': image_name,
                         'stack': stack_name,
                         'source_url': source_url,
                         'custom_url': custom_url,
                         'ports': port_map,
                         'traefik_routes': traefik_routes,
                         'tags': tags
                    }
                    if TAGS_ENABLE:
                        container_info['tags'] = tags

                    
                    if cached_update is not None and is_cache_valid:
                        container_info['update_available'] = cached_update
                    else:
                        local_update = update_checker.check_local_image_updates(client, container, server_name)
                        container_info['update_available'] = local_update
                    
                    all_container_data.append(container_info)
                except Exception as container_error:
                    all_container_data.append({
                        'server': server_name,
                        'name': getattr(container, 'name', 'unknown'),
                        'status': getattr(container, 'status', 'unknown'),
                        'image': 'error-loading',
                        'ports': []
                    })
        except Exception as e:
            for s in server_list_for_json:
                if s["name"] == host["name"]:
                    s["status"] = "inactive"
                    break
            continue

    return {
        "servers": server_list_for_json, 
        "containers": all_container_data,
        "traefik_enabled": TRAEFIK_ENABLE,
         "swarm_servers": swarm_servers
    }
