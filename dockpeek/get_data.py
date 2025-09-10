import re
import logging
from flask import current_app
from .docker_utils import discover_docker_clients, get_container_status_with_exit_code, _get_link_hostname
from .update import update_checker

logger = logging.getLogger(__name__)


def get_all_data():
    """Retrieve comprehensive data about all Docker containers across all configured servers."""
    # Get configuration from Flask app
    TRAEFIK_ENABLE = current_app.config['TRAEFIK_ENABLE']
    TAGS_ENABLE = current_app.config['TAGS_ENABLE']
    
    # Discover all available Docker servers
    servers = discover_docker_clients()
    if not servers: 
        return {"servers": [], "containers": []}
    
    all_container_data = []
    server_list_for_json = [
        {
            "name": s["name"], 
            "status": s["status"], 
            "order": s["order"], 
            "url": s["url"]
        } 
        for s in servers
    ]
    
    # Process each Docker server
    for host in servers:
        if host['status'] == 'inactive': 
            continue
            
        try:
            server_name = host["name"]
            client = host["client"]
            public_hostname = host["public_hostname"]
            is_docker_host = host["is_docker_host"]
            
            # Get all containers from this server
            containers = client.containers.list(all=True)
            
            for container in containers:
                try:
                    container_info = _process_container(
                        container, server_name, client, public_hostname, 
                        is_docker_host, TRAEFIK_ENABLE, TAGS_ENABLE
                    )
                    all_container_data.append(container_info)
                    
                except Exception as container_error:
                    logger.error(f"Error processing container {getattr(container, 'name', 'unknown')}: {container_error}")
                    all_container_data.append({
                        'server': server_name, 
                        'name': getattr(container, 'name', 'unknown'), 
                        'status': 'error', 
                        'image': 'error-loading', 
                        'ports': []
                    })
                    
        except Exception as host_error:
            logger.error(f"Error connecting to host {host['name']}: {host_error}")
            # Mark server as inactive in response
            for s in server_list_for_json:
                if s["name"] == host["name"]: 
                    s["status"] = "inactive"
    
    return {
        "servers": server_list_for_json, 
        "containers": all_container_data, 
        "traefik_enabled": TRAEFIK_ENABLE
    }


def _process_container(container, server_name, client, public_hostname, is_docker_host, traefik_enable, tags_enable):
    """Process a single container and extract all relevant information."""
    # Basic container information
    image_name = container.attrs.get('Config', {}).get('Image', 'unknown')
    container_status, exit_code = get_container_status_with_exit_code(container)
    labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
    
    # Extract metadata from labels
    stack_name = labels.get('com.docker.compose.project', '')
    source_url = labels.get('org.opencontainers.image.source') or labels.get('org.opencontainers.image.url', '')
    https_ports = labels.get('dockpeek.https', '')
    custom_url = labels.get('dockpeek.link', '')
    custom_ports = labels.get('dockpeek.ports', '') or labels.get('dockpeek.port', '')
    custom_tags = labels.get('dockpeek.tags', '') or labels.get('dockpeek.tag', '')
    
    # Process tags if enabled
    tags = []
    if tags_enable and custom_tags:
        tags = [tag.strip() for tag in custom_tags.split(',') if tag.strip()]
    
    # Process Traefik routes if enabled
    traefik_routes = _extract_traefik_routes(labels, traefik_enable)
    
    # Process port mappings
    port_map = _extract_port_mappings(
        container, public_hostname, is_docker_host, https_ports, custom_ports
    )
    
    # Check for updates
    cache_key = update_checker.get_cache_key(server_name, container.name, image_name)
    cached_update, is_cache_valid = update_checker.get_cached_result(cache_key)
    
    container_info = {
        'server': server_name,
        'name': container.name,
        'status': container_status,
        'exit_code': exit_code,
        'image': image_name,
        'stack': stack_name,
        'source_url': source_url,
        'custom_url': custom_url,
        'ports': port_map,
        'traefik_routes': traefik_routes,
        'tags': tags if tags_enable else []
    }
    
    # Add update information
    if cached_update is not None and is_cache_valid:
        container_info['update_available'] = cached_update
    else:
        container_info['update_available'] = update_checker.check_local_image_updates(
            client, container, server_name
        )
    
    return container_info


def _extract_traefik_routes(labels, traefik_enable):
    """Extract Traefik routing information from container labels."""
    traefik_routes = []
    
    if not traefik_enable or labels.get('traefik.enable', '').lower() == 'false':
        return traefik_routes
    
    for key, value in labels.items():
        if key.startswith('traefik.http.routers.') and key.endswith('.rule'):
            router_name = key.split('.')[3]
            host_matches = re.findall(r'Host\(`([^`]+)`\)', value)
            
            for host_match in host_matches:
                # Check for TLS configuration
                tls_key = f'traefik.http.routers.{router_name}.tls'
                is_tls = labels.get(tls_key, '').lower() == 'true'
                
                # Check entrypoints for HTTPS indicators
                entrypoints_key = f'traefik.http.routers.{router_name}.entrypoints'
                entrypoints_str = labels.get(entrypoints_key, '')
                is_https_entrypoint = False
                if entrypoints_str:
                    is_https_entrypoint = any(
                        'https' in ep or '443' in ep 
                        for ep in entrypoints_str.split(',')
                    )
                
                # Determine protocol
                protocol = 'https' if is_tls or is_https_entrypoint else 'http'
                url = f"{protocol}://{host_match}"
                
                # Add path prefix if present
                path_match = re.search(r'PathPrefix\(`([^`]+)`\)', value)
                if path_match: 
                    url += path_match.group(1)
                
                traefik_routes.append({
                    'router': router_name,
                    'url': url,
                    'rule': value,
                    'host': host_match
                })
    
    return traefik_routes


def _extract_port_mappings(container, public_hostname, is_docker_host, https_ports, custom_ports):
    """Extract and process port mappings for a container."""
    port_map = []
    
    # Parse HTTPS ports list
    https_ports_list = []
    if https_ports:
        https_ports_list = [str(p.strip()) for p in https_ports.split(',') if p.strip()]
    
    # Parse custom ports list
    custom_ports_list = []
    if custom_ports:
        custom_ports_list = [str(p.strip()) for p in custom_ports.split(',') if p.strip()]
    
    # Process actual port mappings from Docker
    ports = container.attrs['NetworkSettings']['Ports']
    if ports:
        for container_port, mappings in ports.items():
            if mappings:
                mapping = mappings[0]
                host_port = mapping['HostPort']
                host_ip = mapping.get('HostIp', '0.0.0.0')
                
                link_hostname = _get_link_hostname(public_hostname, host_ip, is_docker_host)
                
                # Determine if this should be HTTPS
                is_https = (
                    "443" in container_port or 
                    host_port == "443" or 
                    str(host_port) in https_ports_list
                )
                protocol = "https" if is_https else "http"
                
                # Build the link
                link = f"{protocol}://{link_hostname}"
                if host_port != "443":
                    link += f":{host_port}"
                
                port_map.append({
                    'container_port': container_port,
                    'host_port': host_port,
                    'link': link,
                    'is_custom': False
                })
    
    # Add custom ports
    if custom_ports_list:
        link_hostname = _get_link_hostname(public_hostname, None, is_docker_host)
        for port in custom_ports_list:
            is_https = port == "443" or str(port) in https_ports_list
            protocol = "https" if is_https else "http"
            
            link = f"{protocol}://{link_hostname}"
            if port != "443":
                link += f":{port}"
            
            port_map.append({
                'container_port': '',
                'host_port': port,
                'link': link,
                'is_custom': True
            })
    
    return port_map