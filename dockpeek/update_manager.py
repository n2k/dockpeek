# update_manager.py

import logging
import time
import re
from typing import Dict, Any, Optional
from flask import current_app
import docker

logger = logging.getLogger(__name__)

class ContainerUpdateError(Exception):
    """Exception with separate HTML and plain text messages"""
    def __init__(self, html_message: str, log_message: str = None):
        # Use clean message for the exception itself (logging)
        clean_message = log_message or strip_html_tags(html_message)
        super().__init__(clean_message)
        self.html_message = html_message

def strip_html_tags(text: str) -> str:
    """Remove HTML tags and double newlines from text for clean logging"""
    clean_text = re.sub(r'<[^>]+>', '', text)
    clean_text = clean_text.replace('\n', ' ')
    return clean_text


def check_image_updates_available(client: docker.DockerClient, image_name: str, container_image_id: str = None) -> bool:
    try:
        local_image = client.images.get(image_name)
        
        if not container_image_id:
            logger.debug(f"No container image ID provided for comparison")
            return True
            
        has_update = container_image_id != local_image.id
        
        logger.debug(f"Image {image_name} - Container ID: {container_image_id[:12]}..., Local ID: {local_image.id[:12]}..., Has update: {has_update}")
        
        return has_update
        
    except docker.errors.ImageNotFound:
        logger.info(f"Local image {image_name} not found - update needed")
        return True
    except Exception as e:
        logger.warning(f"Could not check for updates for {image_name}: {e}")
        return True

def check_network_dependencies(client: docker.DockerClient, container) -> None:
    container_name = container.name
    
    try:
        all_containers = client.containers.list(all=True)
    except Exception as e:
        logger.warning(f"Could not list containers to check dependencies: {e}")
        return
    
    dependent_containers = []
    
    for other_container in all_containers:
        if other_container.id == container.id:
            continue
            
        network_mode = other_container.attrs.get('HostConfig', {}).get('NetworkMode', '')
        if network_mode == f'container:{container_name}' or network_mode == f'container:{container.id}':
            dependent_containers.append(other_container.name)
    
    if dependent_containers:
        html_message = (
            f"Cannot update container <strong>'{container_name}'</strong> because other containers <strong>depend</strong> on its network: <strong>{', '.join(dependent_containers)}.</strong>\n"
            f"<div class='text-center' style='margin-top: 0.7em;'>Updating such containers <strong>must be done outside of dockpeek.</strong></div>"
        )
        raise ContainerUpdateError(html_message)

def validate_container_for_update(client: docker.DockerClient, container) -> None:
    check_network_dependencies(client, container)
    
    container_name = container.name.lower()
    image_name = container.attrs.get('Config', {}).get('Image', '').lower()
    labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
    
    critical_images = [  
        'dockpeek',
        'socket-proxy',
        'traefik',
        'portainer/portainer',
        'containrrr/watchtower',
        'pihole/pihole',
        'jwilder/nginx-proxy',
        'haproxy',
        'envoyproxy/envoy',
        'linuxserver/wireguard',
        'kylemanna/openvpn',
        'nginx',
        'caddy',
        'cloudflare/cloudflared',
        'bitwarden/server',
        'vaultwarden/server',
        'grafana/grafana',
        'prom/prometheus',
        'prom/alertmanager',
        'louislam/uptime-kuma',
        'duplicati/duplicati',
        'restic/restic',
        'rclone/rclone',
        'nextcloud',
        'authelia/authelia',
        'oauth2-proxy/oauth2-proxy',
        'keycloak/keycloak',
        'tailscale/tailscale',
        'netbirdio/netbird',
        'adguardhome/adguardhome',
        'jc21/nginx-proxy-manager',
        'linuxserver/swag'
    ]

    critical_name_patterns = [
        'traefik', 'portainer', 'watchtower', 'pihole', 
        'wireguard', 'openvpn', 'bitwarden', 'vaultwarden',
        'grafana', 'prometheus', 'alertmanager', 'authelia', 
        'keycloak', 'tailscale', 'netbird', 'adguard',
        'nginx-proxy-manager', 'uptime-kuma'
    ]

    database_images = [
        'postgres', 'mysql', 'mariadb', 'mongodb', 'mongo',
        'redis', 'sqlite', 'microsoft/mssql-server',
        'couchdb', 'couchbase', 'cockroachdb', 'neo4j',
        'influxdb', 'elasticsearch', 'cassandra', 'memcached'
    ]

    database_name_patterns = [
        'database', 'postgres', 'mysql', 'mariadb', 'mongo',
        'redis', 'mssql', 'couch', 'cockroach', 'neo4j',
        'influx', 'elastic', 'cassandra', 'memcached'
    ]
    
    for pattern in critical_images:
        if pattern in image_name:
            if pattern == 'dockpeek':
                html_message = (
                    f"<div class='text-center'><strong>Dockpeek</strong> cannot update itself, as this would <strong>interrupt the update process.</strong></div>"
                    f"<div class='text-center' style='margin-top: 0.7em;'>Please update the dockpeek container <strong>outside of dockpeek.</strong></div>"
                )
                raise ContainerUpdateError(html_message)
            else:
                html_message = (
                    f"Container <strong>'{container.name}'</strong> appears to be a <strong>critical system service.</strong> "
                    f"Updating it through Dockpeek is not recommended.\n"
                    f"<div class='text-center' style='margin-top: 0.7em;'>Please update this container <strong>outside of dockpeek.</strong></div>"
                )
                raise ContainerUpdateError(html_message)
    
    for pattern in critical_name_patterns:
        if pattern in container_name:
            html_message = (
                f"Container <strong>'{container.name}'</strong> appears to be a <strong>critical system service.</strong> "
                f"Updating it through Dockpeek is not recommended.\n"
                f"<div class='text-center' style='margin-top: 0.7em;'>Please update this container <strong>outside of dockpeek.</strong></div>"
            )
            raise ContainerUpdateError(html_message)
    
    for pattern in database_images:
        if pattern in image_name:
            html_message = (
                f"Container <strong>'{container.name}'</strong> appears to be a <strong>database service.</strong> "
                f"Updating databases through Dockpeek is not recommended, as it may cause <strong>downtime or data loss.</strong>\n"
                f"<div class='text-center' style='margin-top: 0.7em;'>Please update this container <strong>outside of dockpeek.</strong></div>"
            )
            raise ContainerUpdateError(html_message)
    
    for pattern in database_name_patterns:
        if pattern in container_name:
            html_message = (
                f"Container <strong>'{container.name}'</strong> appears to be a <strong>database service.</strong> "
                f"Updating databases through Dockpeek is not recommended, as it may cause <strong>downtime or data loss.</strong>\n"
                f"<div class='text-center' style='margin-top: 0.7em;'>Please update this container <strong>outside of dockpeek.</strong></div>"
            )
            raise ContainerUpdateError(html_message)
    
    if 'com.docker.compose.project' in labels:
        project_name = labels['com.docker.compose.project']
        logger.debug(f"Container '{container.name}' is part of Docker Compose project '{project_name}'")
    
    health_config = container.attrs.get('Config', {}).get('Healthcheck')
    if health_config and health_config.get('Test'):
        logger.info(f"Container '{container.name}' has health check configured - Dockpeek will monitor it during the update process.")

def extract_container_config(container) -> Dict[str, Any]:
    attrs = container.attrs
    config = attrs.get('Config', {})
    host_config = attrs.get('HostConfig', {})
    
    env_vars = config.get('Env', []) or []
    clean_env = [env for env in env_vars if env is not None]
    
    labels = config.get('Labels') or {}
    clean_labels = {k: v for k, v in labels.items() if v is not None}
    
    binds = host_config.get('Binds') or []
    clean_binds = [bind for bind in binds if bind is not None]
    
    port_bindings = host_config.get('PortBindings') or {}
    clean_port_bindings = {k: v for k, v in port_bindings.items() if v is not None}
    
    network_mode = host_config.get('NetworkMode')
    
    hostname = None
    if network_mode and not network_mode.startswith('container:'):
        hostname = config.get('Hostname')
    
    return {
        'name': container.name,
        'hostname': hostname,
        'user': config.get('User'),
        'working_dir': config.get('WorkingDir'),
        'labels': clean_labels,
        'environment': clean_env,
        'command': config.get('Cmd'),
        'entrypoint': config.get('Entrypoint'),
        'volumes': clean_binds,
        'ports': clean_port_bindings,
        'network_mode': network_mode,
        'restart_policy': host_config.get('RestartPolicy', {'Name': 'no'}),
        'privileged': host_config.get('Privileged', False),
        'cap_add': host_config.get('CapAdd'),
        'cap_drop': host_config.get('CapDrop'),
        'devices': host_config.get('Devices'),
        'security_opt': host_config.get('SecurityOpt'),
        'detach': True
    }

def create_new_container(client: docker.DockerClient, image_name: str, config: Dict[str, Any]) -> docker.models.containers.Container:
    clean_config = {k: v for k, v in config.items() if v is not None}
    
    for key in ['environment', 'volumes', 'cap_add', 'cap_drop', 'devices', 'security_opt']:
        if key in clean_config and not clean_config[key]:
            del clean_config[key]
    
    try:
        return client.containers.create(image_name, **clean_config)
    except Exception as e:
        logger.error(f"Failed to create container with config: {clean_config}")
        raise ContainerUpdateError(f"Failed to create new container: {e}")

def connect_to_networks(client: docker.DockerClient, container, original_networks: Dict[str, Any]) -> None:
    container_attrs = container.attrs
    network_mode = container_attrs.get('HostConfig', {}).get('NetworkMode', '')
    
    if network_mode and network_mode.startswith('container:'):
        logger.info(f"Container uses network mode '{network_mode}', skipping network connections")
        return
    
    for network_name, network_config in original_networks.items():
        if network_name == 'bridge':
            continue
            
        try:
            network = client.networks.get(network_name)
            
            connect_config = {}
            if network_config.get('IPAddress'):
                connect_config['ipv4_address'] = network_config['IPAddress']
            if network_config.get('Aliases'):
                connect_config['aliases'] = network_config['Aliases']
                
            network.connect(container, **connect_config)
            logger.info(f"Connected container to network: {network_name}")
            
        except Exception as e:
            logger.warning(f"Failed to connect to network {network_name}: {e}")

def wait_for_container_health(container, timeout: int = 180) -> bool:
    start_time = time.time()
    check_interval = 2
    
    while time.time() - start_time < timeout:
        try:
            container.reload()
            status = container.status
            
            logger.debug(f"Container {container.name} status: {status}")
            
            if status == 'running':
                health = container.attrs.get('State', {}).get('Health', {})
                if health.get('Status') == 'healthy' or not health:
                    logger.info(f"Container {container.name} is running and healthy")
                    return True
                elif health.get('Status') == 'unhealthy':
                    logger.warning(f"Container {container.name} is unhealthy")
                    return False
                else:
                    logger.debug(f"Container {container.name} health status: {health.get('Status', 'unknown')}")
            elif status in ['exited', 'dead']:
                logger.error(f"Container {container.name} has exited or died")
                return False
                
            time.sleep(check_interval)
        except Exception as e:
            logger.warning(f"Error checking container health: {e}")
            time.sleep(check_interval)
    
    logger.warning(f"Container health check timed out after {timeout} seconds")
    return False

def cleanup_container_by_name(client: docker.DockerClient, container_name: str, force: bool = True) -> bool:
    try:
        container = client.containers.get(container_name)
        container.remove(force=force)
        logger.info(f"Successfully removed container: {container_name}")
        return True
    except docker.errors.NotFound:
        logger.debug(f"Container {container_name} not found (already removed)")
        return True
    except Exception as e:
        logger.error(f"Failed to remove container {container_name}: {e}")
        return False

def update_container(client: docker.DockerClient, server_name: str, container_name: str, force: bool = False) -> Dict[str, Any]:
    logger.info(f"[{server_name}] Starting update process for container: {container_name} (force={force})")
    
    original_timeout = getattr(client.api, 'timeout', None)
    try:
        client.api.timeout = 300
    except AttributeError:
        logger.warning("Could not set client timeout")
    
    backup_container = None
    new_container = None
    
    try:
        try:
            container = client.containers.get(container_name)
        except docker.errors.NotFound:
            raise ContainerUpdateError(f"Container '{container_name}' not found.")
        except Exception as e:
            raise ContainerUpdateError(f"Error accessing container '{container_name}': {e}")
        
        validate_container_for_update(client, container)
        
        image_name = container.attrs.get('Config', {}).get('Image')
        container_image_id = container.attrs.get('Image', '')
        
        if not image_name:
            raise ContainerUpdateError("Could not determine image name for the container.")
        
        logger.info(f"[{server_name}] Container image: {image_name}")
        logger.debug(f"[{server_name}] Current container image ID: {container_image_id[:12]}...")
        
        logger.info(f"[{server_name}] Pulling latest image: {image_name}")
        try:
            new_image = client.images.pull(image_name)
            logger.info(f"[{server_name}] Successfully pulled image: {new_image.short_id}")
        except Exception as e:
            raise ContainerUpdateError(f"Failed to pull image '{image_name}': {e}")
        
        if not force and not check_image_updates_available(client, image_name, container_image_id):
            logger.info(f"[{server_name}] No updates available for {image_name} - container is already using the latest image")
            return {
                "status": "success", 
                "message": f"Container {container_name} is already up to date."
            }
        
        container_config = extract_container_config(container)
        original_networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
        
        timestamp = int(time.time())
        backup_name = f"{container_name}-backup-{timestamp}"
        
        backup_counter = 1
        while True:
            try:
                client.containers.get(backup_name)
                backup_name = f"{container_name}-backup-{timestamp}-{backup_counter}"
                backup_counter += 1
            except docker.errors.NotFound:
                break
        
        logger.info(f"[{server_name}] Stopping container: {container_name}")
        try:
            container.stop(timeout=60)
            logger.info(f"[{server_name}] Container stopped successfully")
        except Exception as e:
            logger.warning(f"[{server_name}] Error stopping container gracefully: {e}")
            try:
                container.kill()
                logger.info(f"[{server_name}] Container killed successfully")
            except Exception as kill_error:
                logger.error(f"[{server_name}] Failed to kill container: {kill_error}")
                raise ContainerUpdateError(f"Failed to stop container: {e}")
        
        logger.info(f"[{server_name}] Renaming container to: {backup_name}")
        try:
            container.rename(backup_name)
            backup_container = container
        except Exception as e:
            try:
                container.start()
            except:
                pass
            raise ContainerUpdateError(f"Failed to rename container: {e}")
        
        try:
            logger.info(f"[{server_name}] Creating new container: {container_name}")
            new_container = create_new_container(client, image_name, container_config)
            
            if original_networks:
                logger.info(f"[{server_name}] Connecting to networks")
                connect_to_networks(client, new_container, original_networks)
            
            logger.info(f"[{server_name}] Starting new container: {container_name}")
            new_container.start()
            
            logger.info(f"[{server_name}] Waiting for container to become healthy...")
            if not wait_for_container_health(new_container, timeout=120):
                raise ContainerUpdateError("New container failed to start properly within 120 seconds")
            
            logger.info(f"[{server_name}] New container is running successfully")
            
        except Exception as e:
            logger.error(f"[{server_name}] Failed to create/start new container: {e}")
            
            if new_container:
                try:
                    new_container.remove(force=True)
                    logger.info(f"[{server_name}] Cleaned up failed new container")
                except Exception as cleanup_error:
                    logger.warning(f"[{server_name}] Failed to cleanup new container: {cleanup_error}")
            
            if backup_container:
                try:
                    logger.info(f"[{server_name}] Restoring original container")
                    
                    cleanup_container_by_name(client, container_name, force=True)
                    
                    backup_container.rename(container_name)
                    backup_container.start()
                    logger.info(f"[{server_name}] Successfully restored original container")
                    
                except Exception as restore_error:
                    logger.error(f"[{server_name}] Failed to restore original container: {restore_error}")
                    raise ContainerUpdateError(
                        f"Update failed: {e}. CRITICAL: Failed to restore original container: {restore_error}. "
                        f"Manual intervention required for container '{backup_name}'"
                    )
            
            raise ContainerUpdateError(f"Update failed: {e}. Original container restored.")
        
        if backup_container:
            try:
                logger.info(f"[{server_name}] Removing backup container: {backup_name}")
                backup_container.remove(force=True)
                logger.info(f"[{server_name}] Successfully removed backup container")
            except Exception as e:
                logger.warning(f"[{server_name}] Could not remove backup container {backup_name}: {e}")
        
        success_message = f"Container '{container_name}' updated successfully to latest image."
        if force:
            success_message += " (Forced update)"
        
        logger.info(f"[{server_name}] Successfully updated container: {container_name}")
        return {
            "status": "success", 
            "message": success_message
        }
        
    finally:
        if original_timeout is not None:
            try:
                client.api.timeout = original_timeout
            except AttributeError:
                pass