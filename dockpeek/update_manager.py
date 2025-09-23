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
            f"{', '.join(dependent_containers)}. Please update the dependent containers first or "
            "update the entire stack using Docker Compose."
        )

def validate_container_for_update(client: docker.DockerClient, container) -> None:
    """
    Validate that a container can be safely updated.
    Raises ContainerUpdateError if container cannot be updated.
    """
    # Check if other containers depend on this container's network
    check_network_dependencies(client, container)
    
    # Check if container is part of a compose stack
    labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
    if 'com.docker.compose.project' in labels:
        project_name = labels['com.docker.compose.project']
        logger.warning(f"Container '{container.name}' is part of Docker Compose project '{project_name}'")
    
    # Check for critical system containers
    if container.name in ['watchtower', 'portainer', 'traefik']:
        raise ContainerUpdateError(
            f"Container '{container.name}' is a critical system container. "
            "Manual update is not recommended."
        )

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

def wait_for_container_health(container, timeout: int = 30) -> bool:
    """
    Wait for container to be healthy or running.
    Returns True if container is healthy/running, False if timeout.
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            container.reload()
            status = container.status
            
            if status == 'running':
                # Check health if health check is configured
                health = container.attrs.get('State', {}).get('Health', {})
                if health.get('Status') == 'healthy' or not health:
                    return True
                elif health.get('Status') == 'unhealthy':
                    return False
            elif status in ['exited', 'dead']:
                return False
                
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Error checking container health: {e}")
            time.sleep(1)
    
    return False

def update_container(client: docker.DockerClient, server_name: str, container_name: str, force: bool = False) -> Dict[str, Any]:
    """
    Safely stops, removes, and recreates a container with the latest image.
    Adopts a "Watchtower" like approach with improved error handling and rollback.
    
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
    
    # Create backup name
    backup_name = f"{container_name}-backup-{int(time.time())}"
    
    # Stop and rename original container
    logger.info(f"[{server_name}] Stopping container: {container_name}")
    try:
        container.stop(timeout=10)
    except Exception as e:
        logger.warning(f"[{server_name}] Error stopping container: {e}")
    
    logger.info(f"[{server_name}] Renaming container to: {backup_name}")
    try:
        container.rename(backup_name)
    except Exception as e:
        # Try to restart original container
        try:
            container.start()
        except:
            pass
        raise ContainerUpdateError(f"Failed to rename container: {e}")
    
    # Create new container
    new_container = None
    try:
        logger.info(f"[{server_name}] Creating new container: {container_name}")
        new_container = create_new_container(client, image_name, container_config)
        
        # Connect to networks
        if original_networks:
            connect_to_networks(client, new_container, original_networks)
        
        # Start new container
        logger.info(f"[{server_name}] Starting new container: {container_name}")
        new_container.start()
        
        # Wait for container to be healthy
        if not wait_for_container_health(new_container, timeout=30):
            raise ContainerUpdateError("New container failed to start properly")
        
        logger.info(f"[{server_name}] New container is running successfully")
        
    except Exception as e:
        logger.error(f"[{server_name}] Failed to create/start new container: {e}")
        
        # Cleanup new container if it was created
        if new_container:
            try:
                new_container.remove(force=True)
            except:
                pass
        
        # Restore original container
        try:
            backup_container = client.containers.get(backup_name)
            backup_container.rename(container_name)
            backup_container.start()
            logger.info(f"[{server_name}] Restored original container")
        except Exception as restore_error:
            logger.error(f"[{server_name}] Failed to restore original container: {restore_error}")
        
        raise ContainerUpdateError(f"Update failed: {e}. Original container restored.")
    
    # Remove backup container
    try:
        backup_container = client.containers.get(backup_name)
        # Use longer timeout for remove operation
        backup_container.remove()
        logger.info(f"[{server_name}] Removed backup container: {backup_name}")
    except docker.errors.ReadTimeout:
        logger.warning(f"[{server_name}] Timeout removing backup container {backup_name} (container may still be removed)")
    except Exception as e:
        logger.warning(f"[{server_name}] Could not remove backup container {backup_name}: {e}")
    
    logger.info(f"[{server_name}] Successfully updated container: {container_name}")
    return {
        "status": "success", 
        "message": f"Container '{container_name}' updated successfully to latest image."
    }