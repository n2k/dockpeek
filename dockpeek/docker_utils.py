import os
import re
import logging
from datetime import datetime, timedelta
from threading import Lock
from urllib.parse import urlparse
import docker
from docker.client import DockerClient
from packaging import version
from concurrent.futures import ThreadPoolExecutor
from flask import request

# Używamy loggera skonfigurowanego w __init__.py
logger = logging.getLogger(__name__)

# Globalny executor i klasa UpdateChecker pozostają bez zmian
executor = ThreadPoolExecutor(max_workers=4)

class UpdateChecker:
    # ... (cała klasa UpdateChecker skopiowana z app.py bez zmian) ...
    def __init__(self):
        self.cache = {}
        self.lock = Lock()
        self.cache_duration = 300  # 5 minutes
        
    def get_cache_key(self, server_name, container_name, image_name):
        return f"{server_name}:{container_name}:{image_name}"
    
    def is_cache_valid(self, timestamp):
        return datetime.now() - timestamp < timedelta(seconds=self.cache_duration)
    
    def get_cached_result(self, cache_key):
        with self.lock:
            if cache_key in self.cache:
                result, timestamp = self.cache[cache_key]
                if self.is_cache_valid(timestamp):
                    return result, True
        return None, False
    
    def set_cache_result(self, cache_key, result):
        with self.lock:
            self.cache[cache_key] = (result, datetime.now())

    def check_local_image_updates(self, client, container, server_name):
        try:
            container_image_id = container.attrs.get('Image', '')
            if not container_image_id: return False
            image_name = container.attrs.get('Config', {}).get('Image', '')
            if not image_name: return False
            if ':' in image_name: base_name, current_tag = image_name.rsplit(':', 1)
            else: base_name, current_tag = image_name, 'latest'
            try:
                local_image = client.images.get(f"{base_name}:{current_tag}")
                return container_image_id != local_image.id
            except Exception: return False
        except Exception as e:
            logger.error(f"Error checking local image updates for container '{container.name}'")
            return False
    
    def check_image_updates_async(self, client, container, server_name):
        try:
            container_image_id = container.attrs.get('Image', '')
            if not container_image_id: return False
            image_name = container.attrs.get('Config', {}).get('Image', '')
            if not image_name: return False
            cache_key = self.get_cache_key(server_name, container.name, image_name)
            cached_result, is_valid = self.get_cached_result(cache_key)
            if is_valid:
                logger.info(f"🔄[ {server_name} ] - Using cached update result for {image_name}: {cached_result}")
                return cached_result
            if ':' in image_name: base_name, current_tag = image_name.rsplit(':', 1)
            else: base_name, current_tag = image_name, 'latest'
            try:
                client.images.pull(base_name, tag=current_tag)
                updated_image = client.images.get(f"{base_name}:{current_tag}")
                result = container_image_id != updated_image.id
                self.set_cache_result(cache_key, result)                
                if result: logger.info(f" [ {server_name} ] - Update available - ⬆️{base_name}  :{current_tag}")
                else: logger.info(f" [ {server_name} ] - Image is up to date - ✅{base_name}  :{current_tag}")                
                return result                
            except Exception as pull_error:
                logger.warning(f" [ {server_name} ] - Cannot pull latest version of - ⚠️{base_name}  :{current_tag}  -  it might be a locally built image")
                self.set_cache_result(cache_key, False)
                return False
        except Exception as e:
            logger.error(f"❌ Error checking image updates for '{container.name}'")
            return False

# Globalna instancja
update_checker = UpdateChecker()

# ... (wszystkie funkcje pomocnicze _extract_hostname_from_url, _is_likely_internal_hostname, _get_link_hostname skopiowane z app.py bez zmian) ...
def _extract_hostname_from_url(url, is_docker_host):
    if not url: return None
    if url.startswith("unix://"): return None
    if url.startswith("tcp://"):
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if hostname and hostname not in ["127.0.0.1", "0.0.0.0", "localhost"] and not _is_likely_internal_hostname(hostname, is_docker_host):
                return hostname
        except Exception: pass
    try:
        match = re.search(r"(?:tcp://)?([^:]+)(?::\d+)?", url)
        if match:
            hostname = match.group(1)
            if hostname not in ["127.0.0.1", "0.0.0.0", "localhost"] and not _is_likely_internal_hostname(hostname, is_docker_host):
                return hostname
    except Exception: pass
    return None

def _is_likely_internal_hostname(hostname, is_docker_host):
    if not is_docker_host: return False
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', hostname): return False
    if '.' in hostname: return False
    return True

def _get_link_hostname(public_hostname, host_ip, is_docker_host):
    if public_hostname: return public_hostname
    if host_ip and host_ip not in ['0.0.0.0', '127.0.0.1']: return host_ip
    try: return request.host.split(":")[0]
    except: return "localhost"


def discover_docker_clients():
    # ... (cała funkcja discover_docker_clients skopiowana z app.py, ale DOCKER_TIMEOUT pobieramy z config.py) ...
    # Zamiast DOCKER_TIMEOUT użyj current_app.config['DOCKER_TIMEOUT']
    # Jednak dla prostoty zostawmy stałą wartość, bo ta funkcja nie ma dostępu do kontekstu aplikacji
    DOCKER_TIMEOUT = 0.5 
    clients = []
    if "DOCKER_HOST" in os.environ:
        host_url = os.environ.get("DOCKER_HOST")
        host_name = os.environ.get("DOCKER_HOST_NAME", "default")
        public_hostname = os.environ.get("DOCKER_HOST_PUBLIC_HOSTNAME") or _extract_hostname_from_url(host_url, True)
        try:
            client = DockerClient(base_url=host_url, timeout=DOCKER_TIMEOUT)
            client.ping()
            clients.append({"name": host_name, "client": client, "url": host_url, "public_hostname": public_hostname, "status": "active", "is_docker_host": True, "order": 0})
        except Exception:
            logger.error(f"Could not connect to DOCKER_HOST '{host_name}' at '{host_url}'")
            clients.append({"name": host_name, "client": None, "url": host_url, "public_hostname": public_hostname, "status": "inactive", "is_docker_host": True, "order": 0})
    host_vars = {k: v for k, v in os.environ.items() if re.match(r"^DOCKER_HOST_\d+_URL$", k)}
    for key, url in host_vars.items():
        match = re.match(r"^DOCKER_HOST_(\d+)_URL$", key)
        if match:
            num = match.group(1)
            name = os.environ.get(f"DOCKER_HOST_{num}_NAME", f"server{num}")
            public_hostname = os.environ.get(f"DOCKER_HOST_{num}_PUBLIC_HOSTNAME") or _extract_hostname_from_url(url, False)
            try:
                client = DockerClient(base_url=url, timeout=DOCKER_TIMEOUT)
                client.ping()
                logger.info(f"[ {name} ]  Docker host is active")
                clients.append({"name": name, "client": client, "url": url, "public_hostname": public_hostname, "status": "active", "is_docker_host": False, "order": int(num)})
            except Exception:
                logger.error(f"[ {name} ] Could not connect to Docker host at {url}")
                clients.append({"name": name, "client": None, "url": url, "public_hostname": public_hostname, "status": "inactive", "is_docker_host": False, "order": int(num)})
    if not clients:
        fallback_name = os.environ.get("DOCKER_NAME", "default")
        try:
            client = docker.from_env(timeout=DOCKER_TIMEOUT)
            client.ping()
            clients.append({"name": fallback_name, "client": client, "url": "unix:///var/run/docker.sock", "public_hostname": "", "status": "active", "is_docker_host": True, "order": 0})
        except Exception:
            clients.append({"name": fallback_name, "client": None, "url": "unix:///var/run/docker.sock", "public_hostname": "", "status": "inactive", "is_docker_host": True, "order": 0})
    return clients

def get_container_status_with_exit_code(container):
    # ... (cała funkcja get_container_status_with_exit_code skopiowana z app.py bez zmian) ...
    try:
        base_status = container.status
        state = container.attrs.get('State', {})
        exit_code = state.get('ExitCode')
        if base_status in ['exited', 'dead']: return base_status, exit_code
        if base_status in ['paused', 'restarting', 'removing', 'created']: return base_status, None
        if base_status == 'running':
            health = state.get('Health', {})
            if health:
                health_status = health.get('Status', '')
                if health_status == 'healthy': return 'healthy', None
                if health_status == 'unhealthy': return 'unhealthy', exit_code
                if health_status == 'starting': return 'starting', None
            return 'running', None
        return base_status, None
    except Exception as e:
        logger.warning(f"Error getting status for container {container.name}: {e}")
        return container.status, None
        
def get_all_data():
    # ... (cała funkcja get_all_data skopiowana z app.py, z modyfikacją pobierania konfiguracji) ...
    # Zamiast TRAEFIK_ENABLE i TAGS_ENABLE użyj current_app.config['TRAEFIK_ENABLE'] itd.
    from flask import current_app
    TRAEFIK_ENABLE = current_app.config['TRAEFIK_ENABLE']
    TAGS_ENABLE = current_app.config['TAGS_ENABLE']
    
    servers = discover_docker_clients()
    if not servers: return {"servers": [], "containers": []}
    all_container_data = []
    server_list_for_json = [{"name": s["name"], "status": s["status"], "order": s["order"], "url": s["url"]} for s in servers]
    for host in servers:
        if host['status'] == 'inactive': continue
        try:
            server_name, client, public_hostname, is_docker_host = host["name"], host["client"], host["public_hostname"], host["is_docker_host"]
            containers = client.containers.list(all=True)
            for container in containers:
                try:
                    image_name = container.attrs.get('Config', {}).get('Image', 'unknown')
                    cache_key = update_checker.get_cache_key(server_name, container.name, image_name)
                    cached_update, is_cache_valid = update_checker.get_cached_result(cache_key)
                    container_status, exit_code = get_container_status_with_exit_code(container)
                    labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
                    stack_name = labels.get('com.docker.compose.project', '')
                    source_url = labels.get('org.opencontainers.image.source') or labels.get('org.opencontainers.image.url', '')
                    https_ports = labels.get('dockpeek.https', '')
                    custom_url = labels.get('dockpeek.link', '')
                    custom_ports = labels.get('dockpeek.ports', '') or labels.get('dockpeek.port', '')
                    custom_tags = labels.get('dockpeek.tags', '') or labels.get('dockpeek.tag', '')
                    tags = [tag.strip() for tag in custom_tags.split(',') if tag.strip()] if TAGS_ENABLE and custom_tags else []
                    traefik_routes = []
                    if TRAEFIK_ENABLE and labels.get('traefik.enable', '').lower() != 'false':
                        for key, value in labels.items():
                            if key.startswith('traefik.http.routers.') and key.endswith('.rule'):
                                router_name = key.split('.')[3]
                                host_matches = re.findall(r'Host\(`([^`]+)`\)', value)
                                for host_match in host_matches:
                                    tls_key = f'traefik.http.routers.{router_name}.tls'
                                    is_tls = labels.get(tls_key, '').lower() == 'true'
                                    entrypoints_key = f'traefik.http.routers.{router_name}.entrypoints'
                                    entrypoints_str = labels.get(entrypoints_key, '')
                                    is_https_entrypoint = any('https' in ep or '443' in ep for ep in entrypoints_str.split(',')) if entrypoints_str else False
                                    protocol = 'https' if is_tls or is_https_entrypoint else 'http'
                                    url = f"{protocol}://{host_match}"
                                    path_match = re.search(r'PathPrefix\(`([^`]+)`\)', value)
                                    if path_match: url += path_match.group(1)
                                    traefik_routes.append({'router': router_name, 'url': url, 'rule': value, 'host': host_match})
                    https_ports_list = [str(p.strip()) for p in https_ports.split(',') if p.strip()] if https_ports else []
                    port_map = []
                    custom_ports_list = [str(p.strip()) for p in custom_ports.split(',') if p.strip()] if custom_ports else []
                    ports = container.attrs['NetworkSettings']['Ports']
                    if ports:
                        for container_port, mappings in ports.items():
                            if mappings:
                                m = mappings[0]
                                host_port, host_ip = m['HostPort'], m.get('HostIp', '0.0.0.0')
                                link_hostname = _get_link_hostname(public_hostname, host_ip, is_docker_host)
                                is_https = "443" in container_port or host_port == "443" or str(host_port) in https_ports_list
                                protocol = "https" if is_https else "http"
                                link = f"{protocol}://{link_hostname}" + (f":{host_port}" if host_port != "443" else "")
                                port_map.append({'container_port': container_port, 'host_port': host_port, 'link': link, 'is_custom': False})
                    if custom_ports_list:
                        link_hostname = _get_link_hostname(public_hostname, None, is_docker_host)
                        for port in custom_ports_list:
                            is_https = port == "443" or str(port) in https_ports_list
                            protocol = "https" if is_https else "http"
                            link = f"{protocol}://{link_hostname}" + (f":{port}" if port != "443" else "")
                            port_map.append({'container_port': '', 'host_port': port, 'link': link, 'is_custom': True})
                    
                    container_info = {'server': server_name, 'name': container.name, 'status': container_status, 'exit_code': exit_code, 'image': image_name, 'stack': stack_name, 'source_url': source_url, 'custom_url': custom_url, 'ports': port_map, 'traefik_routes': traefik_routes, 'tags': tags if TAGS_ENABLE else []}
                    if cached_update is not None and is_cache_valid:
                        container_info['update_available'] = cached_update
                    else:
                        container_info['update_available'] = update_checker.check_local_image_updates(client, container, server_name)
                    all_container_data.append(container_info)
                except Exception as container_error:
                    logger.error(f"Error processing container {getattr(container, 'name', 'unknown')}: {container_error}")
                    all_container_data.append({'server': server_name, 'name': getattr(container, 'name', 'unknown'), 'status': 'error', 'image': 'error-loading', 'ports': []})
        except Exception as host_error:
            logger.error(f"Error connecting to host {host['name']}: {host_error}")
            for s in server_list_for_json:
                if s["name"] == host["name"]: s["status"] = "inactive"
    return {"servers": server_list_for_json, "containers": all_container_data, "traefik_enabled": TRAEFIK_ENABLE}