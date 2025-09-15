import os
import re
import logging
from urllib.parse import urlparse
import docker
from docker.client import DockerClient
from flask import request

logger = logging.getLogger(__name__)


def _extract_hostname_from_url(url, is_docker_host):
    if not url: 
        return None
    if url.startswith("unix://"): 
        return None
    if url.startswith("tcp://"):
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if hostname and hostname not in ["127.0.0.1", "0.0.0.0", "localhost"] and not _is_likely_internal_hostname(hostname, is_docker_host):
                return hostname
        except Exception: 
            pass
    try:
        match = re.search(r"(?:tcp://)?([^:]+)(?::\d+)?", url)
        if match:
            hostname = match.group(1)
            if hostname not in ["127.0.0.1", "0.0.0.0", "localhost"] and not _is_likely_internal_hostname(hostname, is_docker_host):
                return hostname
    except Exception: 
        pass
    return None


def _is_likely_internal_hostname(hostname, is_docker_host):
    if not is_docker_host: 
        return False
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', hostname): 
        return False
    if '.' in hostname: 
        return False
    return True


def _get_link_hostname(public_hostname, host_ip, is_docker_host):
    if public_hostname: 
        return public_hostname
    if host_ip and host_ip not in ['0.0.0.0', '127.0.0.1']: 
        return host_ip
    try: 
        return request.host.split(":")[0]
    except: 
        return "localhost"


def discover_docker_clients():
    """Discover and connect to Docker clients based on environment variables."""
    DOCKER_TIMEOUT = 0.5 
    clients = []
    
    # Check main DOCKER_HOST environment variable
    if "DOCKER_HOST" in os.environ:
        host_url = os.environ.get("DOCKER_HOST")
        host_name = os.environ.get("DOCKER_HOST_NAME", "default")
        public_hostname = os.environ.get("DOCKER_HOST_PUBLIC_HOSTNAME") or _extract_hostname_from_url(host_url, True)
        try:
            client = DockerClient(base_url=host_url, timeout=DOCKER_TIMEOUT)
            client.ping()
            clients.append({
                "name": host_name, 
                "client": client, 
                "url": host_url, 
                "public_hostname": public_hostname, 
                "status": "active", 
                "is_docker_host": True, 
                "order": 0
            })
        except Exception:
            logger.error(f"Could not connect to DOCKER_HOST '{host_name}' at '{host_url}'")
            clients.append({
                "name": host_name, 
                "client": None, 
                "url": host_url, 
                "public_hostname": public_hostname, 
                "status": "inactive", 
                "is_docker_host": True, 
                "order": 0
            })
    
    # Check for numbered Docker hosts (DOCKER_HOST_1_URL, DOCKER_HOST_2_URL, etc.)
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
                clients.append({
                    "name": name, 
                    "client": client, 
                    "url": url, 
                    "public_hostname": public_hostname, 
                    "status": "active", 
                    "is_docker_host": False, 
                    "order": int(num)
                })
            except Exception:
                logger.error(f"[ {name} ] Could not connect to Docker host at {url}")
                clients.append({
                    "name": name, 
                    "client": None, 
                    "url": url, 
                    "public_hostname": public_hostname, 
                    "status": "inactive", 
                    "is_docker_host": False, 
                    "order": int(num)
                })
    
    # Fallback to default Docker socket if no other clients found
    if not clients:
        fallback_name = os.environ.get("DOCKER_NAME", "default")
        public_hostname = os.environ.get("DOCKER_HOST_PUBLIC_HOSTNAME", "")
        try:
            client = docker.from_env(timeout=DOCKER_TIMEOUT)
            client.ping()
            clients.append({
                "name": fallback_name, 
                "client": client, 
                "url": "unix:///var/run/docker.sock", 
                "public_hostname": public_hostname, 
                "status": "active", 
                "is_docker_host": True, 
                "order": 0
            })
        except Exception:
            clients.append({
                "name": fallback_name, 
                "client": None, 
                "url": "unix:///var/run/docker.sock", 
                "public_hostname": public_hostname, 
                "status": "inactive", 
                "is_docker_host": True, 
                "order": 0
            })
    
    return clients


def get_container_status_with_exit_code(container):
    """Get container status and exit code if applicable."""
    try:
        base_status = container.status
        state = container.attrs.get('State', {})
        exit_code = state.get('ExitCode')
        
        if base_status in ['exited', 'dead']: 
            return base_status, exit_code
        if base_status in ['paused', 'restarting', 'removing', 'created']: 
            return base_status, None
        if base_status == 'running':
            health = state.get('Health', {})
            if health:
                health_status = health.get('Status', '')
                if health_status == 'healthy': 
                    return 'healthy', None
                if health_status == 'unhealthy': 
                    return 'unhealthy', exit_code
                if health_status == 'starting': 
                    return 'starting', None
            return 'running', None
        return base_status, None
    except Exception as e:
        logger.warning(f"Error getting status for container {container.name}: {e}")
        return container.status, None