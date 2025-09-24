# dockpeek/update_manager.py

import logging
import time
from typing import Dict, Any, Optional
from flask import current_app
import docker

logger = logging.getLogger(__name__)

class ContainerUpdateError(Exception):
    """Custom exception for container update errors."""
    pass

def check_image_updates_available(client: docker.DockerClient, image_name: str) -> bool:
    """
    Check if there are updates available for the given image.
    Returns True if remote image digest differs from local.
    """
    try:
        # Get local image
        local_image = client.images.get(image_name)
        local_digest = local_image.attrs.get('RepoDigests', [])
        
        # Pull image info without downloading
        registry_data = client.api.inspect_distribution(image_name)
        remote_digest = registry_data.get('Descriptor', {}).get('digest')
        
        if not remote_digest or not local_digest:
            return True  # Assume update needed if we can't compare
            
        return remote_digest not in str(local_digest)
    except docker.errors.APIError as e:
        if e.response.status_code == 403:
            logger.info(f"Registry access restricted for {image_name}, will check by pulling")
        else:
            logger.warning(f"Could not check for updates for {image_name}: {e}")
        return True  # Assume update needed if check fails
    except Exception as e:
        logger.warning(f"Could not check for updates for {image_name}: {e}")
        return True  # Assume update needed if check fails

def check_network_dependencies(client: docker.DockerClient, container) -> None:
    """
    Check if other containers depend on this container's network.
    Raises ContainerUpdateError if other containers depend on this one.
    """
    container_name = container.name
    
    # Get all containers
    try:
        all_containers = client.containers.list(all=True)
    except Exception as e:
        logger.warning(f"Could not list containers to check dependencies: {e}")
        return
    
    dependent_containers = []
    
    for other_container in all_containers:
        if other_container.id == container.id:
            continue
            
        # Check if other container uses this container's network
        network_mode = other_container.attrs.get('HostConfig', {}).get('NetworkMode', '')
        if network_mode == f'container:{container_name}' or network_mode == f'container:{container.id}':
            dependent_containers.append(other_container.name)
    
    if dependent_containers:
        raise ContainerUpdateError(
            f"Cannot update container '{container_name}' because other containers depend on its network: "
            f"{', '.join(dependent_containers)}. Updating such containers must be done outside Dockpeek."
        )

def validate_container_for_update(client: docker.DockerClient, container) -> None:
    """
    Validate that a container can be safely updated.
    Raises ContainerUpdateError if container cannot be updated.
    """
    # Check if other containers depend on this container's network
    check_network_dependencies(client, container)
    
    # Get container info
    container_name = container.name.lower()
    image_name = container.attrs.get('Config', {}).get('Image', '').lower()
    labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
    
    # Critical system containers by image patterns
    critical_images = [
        'traefik',
        'portainer/portainer',
        'containrrr/watchtower',
        'nginx:',
        'caddy',
        'haproxy',
        'envoyproxy/envoy',
        'kong',
        'cloudflare/cloudflared'
    ]
    
    # Critical system containers by name patterns
    critical_name_patterns = [
        'traefik', 'proxy', 'nginx', 'caddy', 'haproxy',
        'portainer', 'watchtower', 'cloudflare', 'tunnel',
        'reverse-proxy', 'load-balancer', 'gateway'
    ]
    
    # Database containers (high risk)
    database_images = [
        'postgres', 'mysql', 'mariadb', 'mongodb', 'mongo',
        'redis', 'elasticsearch', 'cassandra', 'influxdb',
        'clickhouse', 'timescale', 'couchdb', 'neo4j',
        'memcached', 'sqlite', 'cockroachdb'
    ]
    
    database_name_patterns = [
        'db', 'database', 'postgres', 'mysql', 'mariadb', 'mongo',
        'redis', 'elastic', 'cassandra', 'influx', 'timescale'
    ]
    
    # Check critical system containers
    for pattern in critical_images:
        if pattern in image_name:
            raise ContainerUpdateError(
                f"Container '{container.name}' uses a critical system image ({pattern}). "
                f"Manual update is not recommended as it may disrupt essential services.\n\n"
                f"Consider updating this container manually."
            )
    
    for pattern in critical_name_patterns:
        if pattern in container_name:
            raise ContainerUpdateError(
                f"Container '{container.name}' appears to be a critical system container. "
                f"Manual update is not recommended as it may disrupt essential services.\n\n"
                f"Consider updating this container manually."
            )
    
    # Check database containers (warning but allow with explicit confirmation needed)
    for pattern in database_images:
        if pattern in image_name:
            raise ContainerUpdateError(
                f"Container '{container.name}' is a database container ({pattern}). "
                f"Updating databases can cause data corruption or service interruption.\n\n"
                f"Consider updating this container manually."
            )
    
    for pattern in database_name_patterns:
        if pattern in container_name:
            raise ContainerUpdateError(
                f"Container '{container.name}' appears to be a database container. "
                f"Updating databases can cause data corruption or service interruption.\n\n"
                f"Consider updating this container manually."
            )
    
    # Check if container is part of a compose stack
    if 'com.docker.compose.project' in labels:
        project_name = labels['com.docker.compose.project']
        logger.warning(f"Container '{container.name}' is part of Docker Compose project '{project_name}'")
    
    # Check for containers with health checks (may need special handling)
    health_config = container.attrs.get('Config', {}).get('Healthcheck')
    if health_config and health_config.get('Test'):
        logger.info(f"Container '{container.name}' has health check configured - will monitor during update")

def extract_container_config(container) -> Dict[str, Any]:
    """
    Extract container configuration for recreation.
    Returns a clean configuration dict.
    """
    attrs = container.attrs
    config = attrs.get('Config', {})
    host_config = attrs.get('HostConfig', {})
    
    # Clean environment variables (remove None values)
    env_vars = config.get('Env', []) or []
    clean_env = [env for env in env_vars if env is not None]
    
    # Clean labels
    labels = config.get('Labels') or {}
    clean_labels = {k: v for k, v in labels.items() if v is not None}
    
    # Prepare volumes/binds
    binds = host_config.get('Binds') or []
    clean_binds = [bind for bind in binds if bind is not None]
    
    # Prepare port bindings
    port_bindings = host_config.get('PortBindings') or {}
    clean_port_bindings = {k: v for k, v in port_bindings.items() if v is not None}
    
    # Get network mode
    network_mode = host_config.get('NetworkMode')
    
    # Docker doesn't allow hostname when using container network mode
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
    """
    Create a new container with the given configuration.
    """
    # Remove None values from config
    clean_config = {k: v for k, v in config.items() if v is not None}
    
    # Handle special cases for empty lists/dicts
    for key in ['environment', 'volumes', 'cap_add', 'cap_drop', 'devices', 'security_opt']:
        if key in clean_config and not clean_config[key]:
            del clean_config[key]
    
    try:
        return client.containers.create(image_name, **clean_config)
    except Exception as e:
        logger.error(f"Failed to create container with config: {clean_config}")
        raise ContainerUpdateError(f"Failed to create new container: {e}")

def connect_to_networks(client: docker.DockerClient, container, original_networks: Dict[str, Any]) -> None:
    """
    Connect container to the same networks as the original.
    Skip if using container network mode.
    """
    # Skip network connection if using container network mode
    container_attrs = container.attrs
    network_mode = container_attrs.get('HostConfig', {}).get('NetworkMode', '')
    
    if network_mode and network_mode.startswith('container:'):
        logger.info(f"Container uses network mode '{network_mode}', skipping network connections")
        return
    
    for network_name, network_config in original_networks.items():
        if network_name == 'bridge':
            continue  # Skip default bridge network
            
        try:
            network = client.networks.get(network_name)
            
            # Prepare connection config
            connect_config = {}
            if network_config.get('IPAddress'):
                connect_config['ipv4_address'] = network_config['IPAddress']
            if network_config.get('Aliases'):
                connect_config['aliases'] = network_config['Aliases']
                
            network.connect(container, **connect_config)
            logger.info(f"Connected container to network: {network_name}")
            
        except Exception as e:
            logger.warning(f"Failed to connect to network {network_name}: {e}")

def wait_for_container_health(container, timeout: int = 60) -> bool:
    """
    Wait for container to be healthy or running.
    Returns True if container is healthy/running, False if timeout.
    """
    start_time = time.time()
    check_interval = 2  # Check every 2 seconds
    
    while time.time() - start_time < timeout:
        try:
            container.reload()
            status = container.status
            
            logger.debug(f"Container {container.name} status: {status}")
            
            if status == 'running':
                # Check health if health check is configured
                health = container.attrs.get('State', {}).get('Health', {})
                if health.get('Status') == 'healthy' or not health:
                    logger.info(f"Container {container.name} is running and healthy")
                    return True
                elif health.get('Status') == 'unhealthy':
                    logger.warning(f"Container {container.name} is unhealthy")
                    return False
                else:
                    # Still starting up, continue waiting
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
    """
    Safely remove a container by name, with proper error handling.
    Returns True if successfully removed or didn't exist, False on error.
    """
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
    """
    Safely stops, removes, and recreates a container with the latest image.
    Improved version with better timeout handling and rollback logic.
    
    Args:
        client: Docker client instance  
        server_name: Name of the server (for logging)
        container_name: Name of the container to update
        force: Force update even if no new image is available
    
    Returns:
        Dict with status and message
    
    Raises:
        ContainerUpdateError: If update cannot be performed safely
    """
    logger.info(f"[{server_name}] Starting update process for container: {container_name}")
    
    # Configure client timeouts for this operation
    original_timeout = getattr(client.api, 'timeout', None)
    try:
        # Increase timeout for container operations
        client.api.timeout = 30
    except AttributeError:
        logger.warning("Could not set client timeout")
    
    backup_container = None
    new_container = None
    
    try:
        # Get the container
        try:
            container = client.containers.get(container_name)
        except docker.errors.NotFound:
            raise ContainerUpdateError(f"Container '{container_name}' not found.")
        except Exception as e:
            raise ContainerUpdateError(f"Error accessing container '{container_name}': {e}")
        
        # Validate container can be updated
        validate_container_for_update(client, container)
        
        # Get image name
        image_name = container.attrs.get('Config', {}).get('Image')
        if not image_name:
            raise ContainerUpdateError("Could not determine image name for the container.")
        
        logger.info(f"[{server_name}] Container image: {image_name}")
        
        # Check if update is needed (unless forced)
        if not force and not check_image_updates_available(client, image_name):
            logger.info(f"[{server_name}] No updates available for {image_name}")
            return {
                "status": "success", 
                "message": f"Container {container_name} is already up to date."
            }
        
        # Pull latest image
        logger.info(f"[{server_name}] Pulling latest image: {image_name}")
        try:
            new_image = client.images.pull(image_name)
            logger.info(f"[{server_name}] Successfully pulled image: {new_image.short_id}")
        except Exception as e:
            raise ContainerUpdateError(f"Failed to pull image '{image_name}': {e}")
        
        # Extract configuration
        container_config = extract_container_config(container)
        original_networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
        
        # Create backup name with timestamp
        timestamp = int(time.time())
        backup_name = f"{container_name}-backup-{timestamp}"
        
        # Ensure backup name doesn't conflict
        backup_counter = 1
        while True:
            try:
                client.containers.get(backup_name)
                backup_name = f"{container_name}-backup-{timestamp}-{backup_counter}"
                backup_counter += 1
            except docker.errors.NotFound:
                break
        
        # Stop original container with longer timeout
        logger.info(f"[{server_name}] Stopping container: {container_name}")
        try:
            container.stop(timeout=30)
            logger.info(f"[{server_name}] Container stopped successfully")
        except Exception as e:
            logger.warning(f"[{server_name}] Error stopping container gracefully: {e}")
            try:
                container.kill()
                logger.info(f"[{server_name}] Container killed successfully")
            except Exception as kill_error:
                logger.error(f"[{server_name}] Failed to kill container: {kill_error}")
                raise ContainerUpdateError(f"Failed to stop container: {e}")
        
        # Rename original container to backup
        logger.info(f"[{server_name}] Renaming container to: {backup_name}")
        try:
            container.rename(backup_name)
            backup_container = container  # Keep reference for cleanup
        except Exception as e:
            # Try to restart original container
            try:
                container.start()
            except:
                pass
            raise ContainerUpdateError(f"Failed to rename container: {e}")
        
        # Create new container
        try:
            logger.info(f"[{server_name}] Creating new container: {container_name}")
            new_container = create_new_container(client, image_name, container_config)
            
            # Connect to networks before starting
            if original_networks:
                logger.info(f"[{server_name}] Connecting to networks")
                connect_to_networks(client, new_container, original_networks)
            
            # Start new container
            logger.info(f"[{server_name}] Starting new container: {container_name}")
            new_container.start()
            
            # Wait for container to be healthy with increased timeout
            logger.info(f"[{server_name}] Waiting for container to become healthy...")
            if not wait_for_container_health(new_container, timeout=60):
                raise ContainerUpdateError("New container failed to start properly within 60 seconds")
            
            logger.info(f"[{server_name}] New container is running successfully")
            
        except Exception as e:
            logger.error(f"[{server_name}] Failed to create/start new container: {e}")
            
            # Cleanup new container if it exists
            if new_container:
                try:
                    new_container.remove(force=True)
                    logger.info(f"[{server_name}] Cleaned up failed new container")
                except Exception as cleanup_error:
                    logger.warning(f"[{server_name}] Failed to cleanup new container: {cleanup_error}")
            
            # Restore original container
            if backup_container:
                try:
                    logger.info(f"[{server_name}] Restoring original container")
                    
                    # First ensure no container with original name exists
                    cleanup_container_by_name(client, container_name, force=True)
                    
                    # Rename backup back to original
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
        
        # Remove backup container
        if backup_container:
            try:
                logger.info(f"[{server_name}] Removing backup container: {backup_name}")
                backup_container.remove(force=True)
                logger.info(f"[{server_name}] Successfully removed backup container")
            except Exception as e:
                logger.warning(f"[{server_name}] Could not remove backup container {backup_name}: {e}")
                # This is not critical - the update succeeded
        
        logger.info(f"[{server_name}] Successfully updated container: {container_name}")
        return {
            "status": "success", 
            "message": f"Container '{container_name}' updated successfully to latest image."
        }
        
    finally:
        # Restore original client timeout
        if original_timeout is not None:
            try:
                client.api.timeout = original_timeout
            except AttributeError:
                pass