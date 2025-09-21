# dockpeek/update_manager.py

import logging
from flask import current_app

logger = logging.getLogger(__name__)

def update_container(client, server_name, container_name):
    """
    Safely stops, removes, and recreates a container with the latest image.
    Adopts a "Watchtower" like approach.
    """
    try:
        container = client.containers.get(container_name)
    except Exception as e:
        logger.error(f"[{server_name}] Container {container_name} not found: {e}")
        raise RuntimeError(f"Container {container_name} not found.")

    # --- Kluczowe zabezpieczenie przed kontenerami z zależnościami sieciowymi (np. Gluetun) ---
    network_mode = container.attrs.get('HostConfig', {}).get('NetworkMode', '')
    if network_mode.startswith('container:'):
        dependent_container = network_mode.split(':')[1]
        msg = (
            f"Container '{container_name}' depends on the network of '{dependent_container}'. "
            "It cannot be safely updated through the UI. "
            "Please update the entire stack using Docker Compose to avoid issues."
        )
        logger.warning(f"[{server_name}] {msg}")
        raise ValueError(msg)

    image_name = container.attrs.get('Config', {}).get('Image')
    if not image_name:
        raise RuntimeError("Could not determine image name for the container.")

    logger.info(f"[{server_name}] Starting update for {container_name} ({image_name})")

    # 1. Pobierz najnowszy obraz
    try:
        logger.info(f"[{server_name}] Pulling latest image for {image_name}")
        new_image = client.images.pull(image_name)
    except Exception as e:
        logger.error(f"[{server_name}] Failed to pull image {image_name}: {e}")
        raise RuntimeError(f"Failed to pull image {image_name}.")

    # 2. Zatrzymaj i zarchiwizuj stary kontener
    old_container_name_backup = f"{container_name}-old-{container.short_id}"
    logger.info(f"[{server_name}] Stopping container {container_name}")
    container.stop()
    logger.info(f"[{server_name}] Renaming {container_name} to {old_container_name_backup}")
    container.rename(old_container_name_backup)

    # 3. Przygotuj konfigurację dla nowego kontenera
    container_config = container.attrs
    config = {
        'name': container_name,
        'hostname': container_config['Config']['Hostname'],
        'user': container_config['Config'].get('User'),
        'labels': container_config['Config']['Labels'],
        'environment': container_config['Config']['Env'],
        'volumes': container_config['HostConfig']['Binds'],
        'network_mode': network_mode,
        'restart_policy': container_config['HostConfig']['RestartPolicy'],
        'detach': True,
        'ports': container_config['Config'].get('ExposedPorts'),
        'host_config': client.api.create_host_config(
            binds=container_config['HostConfig'].get('Binds'),
            port_bindings=container_config['HostConfig'].get('PortBindings'),
            restart_policy=container_config['HostConfig'].get('RestartPolicy'),
            devices=container_config['HostConfig'].get('Devices'),
            cap_add=container_config['HostConfig'].get('CapAdd'),
            cap_drop=container_config['HostConfig'].get('CapDrop'),
            privileged=container_config['HostConfig'].get('Privileged', False)
        )
    }

    # 4. Utwórz i uruchom nowy kontener
    try:
        logger.info(f"[{server_name}] Creating new container {container_name} with image {new_image.tags[0]}")
        new_container = client.containers.create(new_image.id, **config)
        
        # Podłącz do tych samych sieci
        current_networks = container_config['NetworkSettings']['Networks']
        for net_name in current_networks:
            logger.info(f"[{server_name}] Connecting {container_name} to network {net_name}")
            network = client.networks.get(net_name)
            network.connect(new_container)
            
        logger.info(f"[{server_name}] Starting new container {container_name}")
        new_container.start()
    except Exception as e:
        logger.error(f"[{server_name}] Failed to create or start new container: {e}. Attempting to restore old container.")
        old_container = client.containers.get(old_container_name_backup)
        old_container.rename(container_name)
        old_container.start()
        raise RuntimeError(f"Failed to start new container. Old container has been restored.")

    # 5. Usuń stary kontener
    try:
        logger.info(f"[{server_name}] Removing old container {old_container_name_backup}")
        old_container = client.containers.get(old_container_name_backup)
        old_container.remove()
    except Exception as e:
        logger.warning(f"[{server_name}] Could not remove old container {old_container_name_backup}: {e}")

    logger.info(f"[{server_name}] Successfully updated {container_name}")
    return {"status": "success", "message": f"Container {container_name} updated successfully."}