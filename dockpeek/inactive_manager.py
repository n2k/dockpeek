import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any
import logging
from .inactive_config import parse_inactive_config, get_inactive_status, should_track_inactive
from .inactive_persistence import InactivePersistence

logger = logging.getLogger(__name__)

class InactiveContainerManager:
    def __init__(self, storage_file: str = "inactive_containers.json", persist_db: str = None):
        self.storage_file = storage_file
        self.persist_db = persist_db
        self.persistence = InactivePersistence(persist_db) if persist_db else None
        self.inactive_containers = self._load_inactive_containers()

    def _load_inactive_containers(self) -> List[Dict[str, Any]]:
        """Load inactive containers from storage file or database."""
        if self.persistence:
            containers = self.persistence.load_containers()
        else:
            try:
                if os.path.exists(self.storage_file):
                    with open(self.storage_file, 'r') as f:
                        containers = json.load(f)
                else:
                    containers = []
            except Exception as e:
                logger.error(f"Error loading inactive containers: {e}")
                containers = []
        
        # Ensure all containers have required properties (migration)
        for container in containers:
            if 'traefik_routes' not in container:
                container['traefik_routes'] = []
            if 'port_range_grouping' not in container:
                container['port_range_grouping'] = True
            if 'tags' not in container:
                container['tags'] = []
            if 'ports' not in container:
                container['ports'] = []
            if 'source_url' not in container:
                container['source_url'] = ''
            if 'custom_url' not in container:
                container['custom_url'] = ''
            if 'stack' not in container:
                container['stack'] = ''
            if 'container_id' not in container:
                container['container_id'] = ''
            if 'image' not in container:
                container['image'] = ''
        
        return containers

    def _save_inactive_containers(self):
        """Save inactive containers to storage file or database."""
        if self.persistence:
            self.persistence.save_containers(self.inactive_containers)
        else:
            try:
                with open(self.storage_file, 'w') as f:
                    json.dump(self.inactive_containers, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving inactive containers: {e}")

    def _update_inactive_statuses(self):
        """Update the status of inactive containers based on their configuration."""
        for container in self.inactive_containers:
            if not container.get('is_active', False) and 'inactive_config' in container:
                last_seen = datetime.fromisoformat(container['last_seen'].replace('Z', '+00:00'))
                status, color = get_inactive_status(last_seen, container['inactive_config'])
                if status is not None:
                    container['inactive_status'] = status
                    container['inactive_color'] = color
                else:
                    # Remove status fields if no status applies
                    container.pop('inactive_status', None)
                    container.pop('inactive_color', None)

    def update_inactive_containers(self, current_containers: List[Dict[str, Any]], global_config: Dict[str, Any] = None):
        """Update inactive containers based on current running containers."""
        if global_config is None:
            global_config = {}
            
        current_time = datetime.now(timezone.utc).isoformat()
        current_keys = {f"{c['server']}:{c['name']}" for c in current_containers}

        # Mark existing inactive containers as active if they're running
        for inactive in self.inactive_containers:
            key = f"{inactive['server']}:{inactive['name']}"
            if key in current_keys:
                # Update existing inactive with current container data
                current_container = next((c for c in current_containers if f"{c['server']}:{c['name']}" == key), None)
                if current_container:
                    inactive.update({
                        'container_id': current_container.get('container_id', inactive.get('container_id', '')),
                        'image': current_container.get('image', inactive.get('image', '')),
                        'image_size': current_container.get('image_size', inactive.get('image_size', '')),
                        'stack': current_container.get('stack', inactive.get('stack', '')),
                        'source_url': current_container.get('source_url', inactive.get('source_url', '')),
                        'custom_url': current_container.get('custom_url', inactive.get('custom_url', '')),
                        'tags': current_container.get('tags', inactive.get('tags', [])),
                        'ports': current_container.get('ports', inactive.get('ports', [])),
                        'traefik_routes': current_container.get('traefik_routes', inactive.get('traefik_routes', [])),
                        'port_range_grouping': current_container.get('port_range_grouping', inactive.get('port_range_grouping', True)),
                        'status': 'inactive',
                        'last_seen': current_time,
                        'is_active': True
                    })
            else:
                inactive['is_active'] = False

        # Add new containers that aren't in inactive list yet
        for container in current_containers:
            key = f"{container['server']}:{container['name']}"
            existing_inactive = next((i for i in self.inactive_containers if f"{i['server']}:{i['name']}" == key), None)

            if not existing_inactive:
                # Check if this container should be tracked for inactive status
                container_labels = container.get('labels', {})
                if should_track_inactive(container_labels, global_config):
                    inactive_container = {
                        'server': container['server'],
                        'name': container['name'],
                        'container_id': container.get('container_id', ''),
                        'image': container.get('image', ''),
                        'image_size': container.get('image_size', ''),
                        'stack': container.get('stack', ''),
                        'source_url': container.get('source_url', ''),
                        'custom_url': container.get('custom_url', ''),
                        'tags': container.get('tags', []),
                        'ports': container.get('ports', []),
                        'traefik_routes': container.get('traefik_routes', []),
                        'port_range_grouping': container.get('port_range_grouping', True),
                        'status': 'inactive',
                        'first_seen': current_time,
                        'last_seen': current_time,
                        'is_active': True,
                        'inactive_config': parse_inactive_config(container_labels, global_config)
                    }
                    self.inactive_containers.append(inactive_container)

        # Update status for inactive containers based on their configuration
        self._update_inactive_statuses()

        # Sort by last_seen (newest first)
        self.inactive_containers.sort(key=lambda x: x['last_seen'], reverse=True)

        self._save_inactive_containers()

    def get_inactive_containers(self) -> List[Dict[str, Any]]:
        """Get all inactive containers, sorted by last_seen (newest first)."""
        return self.inactive_containers.copy()

    def get_inactive_containers_only(self) -> List[Dict[str, Any]]:
        """Get only inactive containers (not currently running)."""
        return [i for i in self.inactive_containers if not i.get('is_active', False)]

    def delete_inactive_container(self, server: str, name: str) -> bool:
        """Delete a specific inactive container."""
        if self.persistence:
            success = self.persistence.delete_container(server, name)
            if success:
                # Reload from database
                self.inactive_containers = self._load_inactive_containers()
            return success
        else:
            key = f"{server}:{name}"
            original_length = len(self.inactive_containers)
            self.inactive_containers = [i for i in self.inactive_containers if f"{i['server']}:{i['name']}" != key]
            
            if len(self.inactive_containers) < original_length:
                self._save_inactive_containers()
                return True
            return False

    def clear_all_inactive_containers(self):
        """Clear all inactive containers."""
        if self.persistence:
            cleared_count = self.persistence.clear_containers(inactive_only=False)
            self.inactive_containers = self._load_inactive_containers()
            return cleared_count
        else:
            self.inactive_containers = []
            self._save_inactive_containers()
            return len(self.inactive_containers)

    def clear_inactive_containers_only(self):
        """Clear only inactive containers (not currently running)."""
        if self.persistence:
            cleared_count = self.persistence.clear_containers(inactive_only=True)
            self.inactive_containers = self._load_inactive_containers()
            return cleared_count
        else:
            original_length = len(self.inactive_containers)
            self.inactive_containers = [i for i in self.inactive_containers if i.get('is_active', False)]
            self._save_inactive_containers()
            return original_length - len(self.inactive_containers)

# Global instance
inactive_manager = InactiveContainerManager()