import logging
import time
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import docker

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    ALLOWED = "allowed"
    BLOCKED_SELF = "blocked_self"
    BLOCKED_CRITICAL = "blocked_critical"
    BLOCKED_DATABASE = "blocked_database"
    BLOCKED_DEPENDENCY = "blocked_dependency"


@dataclass
class ValidationBlockage:
    result: ValidationResult
    html_message: str
    log_message: str


class ContainerUpdateError(Exception):
    def __init__(self, html_message: str, log_message: str = None):
        clean_message = log_message or strip_html_tags(html_message)
        super().__init__(clean_message)
        self.html_message = html_message


def strip_html_tags(text: str) -> str:
    clean_text = re.sub(r'<[^>]+>', '', text)
    clean_text = clean_text.replace('\n', ' ')
    return clean_text


class ValidationPatterns:
    CRITICAL_IMAGES = [
        'dockpeek', 'socket-proxy', 'traefik', 'portainer/portainer',
        'containrrr/watchtower', 'pihole/pihole', 'jwilder/nginx-proxy',
        'haproxy', 'envoyproxy/envoy', 'linuxserver/wireguard',
        'kylemanna/openvpn', 'nginx', 'caddy', 'cloudflare/cloudflared',
        'bitwarden/server', 'vaultwarden/server', 'grafana/grafana',
        'prom/prometheus', 'prom/alertmanager', 'louislam/uptime-kuma',
        'duplicati/duplicati', 'restic/restic', 'rclone/rclone',
        'nextcloud', 'authelia/authelia', 'oauth2-proxy/oauth2-proxy',
        'keycloak/keycloak', 'tailscale/tailscale', 'netbirdio/netbird',
        'adguardhome/adguardhome', 'jc21/nginx-proxy-manager',
        'linuxserver/swag'
    ]

    CRITICAL_NAME_PATTERNS = [
        'traefik', 'portainer', 'watchtower', 'pihole', 'wireguard',
        'openvpn', 'bitwarden', 'vaultwarden', 'grafana', 'prometheus',
        'alertmanager', 'authelia', 'keycloak', 'tailscale', 'netbird',
        'adguard', 'nginx-proxy-manager', 'uptime-kuma'
    ]

    DATABASE_IMAGES = [
        'postgres', 'mysql', 'mariadb', 'mongodb', 'mongo', 'redis',
        'sqlite', 'microsoft/mssql-server', 'couchdb', 'couchbase',
        'cockroachdb', 'neo4j', 'influxdb', 'elasticsearch',
        'cassandra', 'memcached'
    ]

    DATABASE_NAME_PATTERNS = [
        'database', 'postgres', 'mysql', 'mariadb', 'mongo', 'redis',
        'mssql', 'couch', 'cockroach', 'neo4j', 'influx', 'elastic',
        'cassandra', 'memcached'
    ]

    @classmethod
    def check_patterns(cls, text: str, patterns: List[str]) -> Optional[str]:
        text_lower = text.lower()
        for pattern in patterns:
            if pattern in text_lower:
                return pattern
        return None


class ContainerValidator:
    def __init__(self, container, client: docker.DockerClient):
        self.container = container
        self.client = client
        self.container_name = container.name.lower()
        self.image_name = container.attrs.get('Config', {}).get('Image', '').lower()
        self.labels = container.attrs.get('Config', {}).get('Labels', {}) or {}
    
    def validate(self) -> Optional[ValidationBlockage]:
        dependency_check = self._check_network_dependencies()
        if dependency_check:
            return dependency_check
        
        pattern_check = self._check_patterns()
        if pattern_check:
            return pattern_check
        
        return None
    
    def _check_network_dependencies(self) -> Optional[ValidationBlockage]:
        try:
            all_containers = self.client.containers.list(all=True)
        except Exception as e:
            logger.warning(f"Could not list containers to check dependencies: {e}")
            return None
        
        dependent_containers = []
        for other_container in all_containers:
            if other_container.id == self.container.id:
                continue
            
            network_mode = other_container.attrs.get('HostConfig', {}).get('NetworkMode', '')
            if network_mode in [f'container:{self.container.name}', f'container:{self.container.id}']:
                dependent_containers.append(other_container.name)
        
        if dependent_containers:
            html_message = (
                f"Cannot update container <strong>'{self.container.name}'</strong> because other containers "
                f"<strong>depend</strong> on its network: <strong>{', '.join(dependent_containers)}.</strong>\n"
                f"<div class='text-center' style='margin-top: 0.7em;'>Updating such containers "
                f"<strong>must be done outside of dockpeek.</strong></div>"
            )
            return ValidationBlockage(
                ValidationResult.BLOCKED_DEPENDENCY,
                html_message,
                f"Container {self.container.name} has network dependencies: {dependent_containers}"
            )
        
        return None
    
    def _check_patterns(self) -> Optional[ValidationBlockage]:
        if 'dockpeek' in self.image_name:
            html_message = (
                f"<div class='text-center'><strong>Dockpeek</strong> cannot update itself, as this would "
                f"<strong>interrupt the update process.</strong></div>"
                f"<div class='text-center' style='margin-top: 0.7em;'>Please update the dockpeek container "
                f"<strong>outside of dockpeek.</strong></div>"
            )
            return ValidationBlockage(ValidationResult.BLOCKED_SELF, html_message, "Cannot update dockpeek itself")
        
        critical_match = ValidationPatterns.check_patterns(
            self.image_name, ValidationPatterns.CRITICAL_IMAGES
        ) or ValidationPatterns.check_patterns(
            self.container_name, ValidationPatterns.CRITICAL_NAME_PATTERNS
        )
        
        if critical_match:
            html_message = (
                f"Container <strong>'{self.container.name}'</strong> appears to be a "
                f"<strong>critical system service.</strong> Updating it through Dockpeek is not recommended.\n"
                f"<div class='text-center' style='margin-top: 0.7em;'>Please update this container "
                f"<strong>outside of dockpeek.</strong></div>"
            )
            return ValidationBlockage(
                ValidationResult.BLOCKED_CRITICAL,
                html_message,
                f"Container {self.container.name} matches critical pattern: {critical_match}"
            )
        
        database_match = ValidationPatterns.check_patterns(
            self.image_name, ValidationPatterns.DATABASE_IMAGES
        ) or ValidationPatterns.check_patterns(
            self.container_name, ValidationPatterns.DATABASE_NAME_PATTERNS
        )
        
        if database_match:
            html_message = (
                f"Container <strong>'{self.container.name}'</strong> appears to be a "
                f"<strong>database service.</strong> Updating databases through Dockpeek is not recommended, "
                f"as it may cause <strong>downtime or data loss.</strong>\n"
                f"<div class='text-center' style='margin-top: 0.7em;'>Please update this container "
                f"<strong>outside of dockpeek.</strong></div>"
            )
            return ValidationBlockage(
                ValidationResult.BLOCKED_DATABASE,
                html_message,
                f"Container {self.container.name} matches database pattern: {database_match}"
            )
        
        return None


class ContainerConfigExtractor:
    def __init__(self, container):
        self.container = container
        self.attrs = container.attrs
        self.config = self.attrs.get('Config', {})
        self.host_config = self.attrs.get('HostConfig', {})
    
    def extract(self) -> Dict[str, Any]:
        network_mode = self.host_config.get('NetworkMode')
        
        hostname = None
        if network_mode and not network_mode.startswith('container:'):
            hostname = self.config.get('Hostname')
        
        return {
            'name': self.container.name,
            'hostname': hostname,
            'user': self.config.get('User'),
            'working_dir': self.config.get('WorkingDir'),
            'labels': self._clean_dict(self.config.get('Labels') or {}),
            'environment': self._clean_list(self.config.get('Env', []) or []),
            'command': self.config.get('Cmd'),
            'entrypoint': self.config.get('Entrypoint'),
            'volumes': self._clean_list(self.host_config.get('Binds') or []),
            'ports': self._clean_dict(self.host_config.get('PortBindings') or {}),
            'network_mode': network_mode,
            'restart_policy': self.host_config.get('RestartPolicy', {'Name': 'no'}),
            'privileged': self.host_config.get('Privileged', False),
            'cap_add': self.host_config.get('CapAdd'),
            'cap_drop': self.host_config.get('CapDrop'),
            'devices': self.host_config.get('Devices'),
            'security_opt': self.host_config.get('SecurityOpt'),
            'detach': True
        }
    
    @staticmethod
    def _clean_list(items: List) -> List:
        return [item for item in items if item is not None]
    
    @staticmethod
    def _clean_dict(items: Dict) -> Dict:
        return {k: v for k, v in items.items() if v is not None}


class ContainerUpdater:
    def __init__(self, client: docker.DockerClient, server_name: str, timeouts: Dict[str, int] = None):
        self.client = client
        self.server_name = server_name
        self.timeouts = timeouts or {
            'api': 300,
            'stop': 60,
        }
        self.original_timeout = None
        
    def __enter__(self):
        self.original_timeout = getattr(self.client.api, 'timeout', None)
        try:
            self.client.api.timeout = self.timeouts['api']
        except AttributeError:
            logger.warning("Could not set client timeout")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.original_timeout is not None:
            try:
                self.client.api.timeout = self.original_timeout
            except AttributeError:
                pass
    
    def update(self, container_name: str, force: bool = False) -> Dict[str, Any]:
        logger.info(f"[{self.server_name}] Starting update for: {container_name} (force={force})")
        
        container = self._get_container(container_name)
        self._validate_container(container)
        
        image_name, container_image_id = self._get_image_info(container)
        
        self._pull_image(image_name)
        
        if not force and not self._has_updates(image_name, container_image_id):
            logger.info(f"[{self.server_name}] No updates for {image_name}")
            return {"status": "success", "message": f"Container {container_name} is already up to date."}
        
        config = ContainerConfigExtractor(container).extract()
        original_networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
        
        backup_name = self._generate_backup_name(container_name)
        
        return self._perform_update(container, backup_name, image_name, config, original_networks)
    
    def _get_container(self, container_name: str):
        try:
            return self.client.containers.get(container_name)
        except docker.errors.NotFound:
            raise ContainerUpdateError(f"Container '{container_name}' not found.")
        except Exception as e:
            raise ContainerUpdateError(f"Error accessing container '{container_name}': {e}")
    
    def _validate_container(self, container):
        validator = ContainerValidator(container, self.client)
        blockage = validator.validate()
        
        if blockage:
            logger.warning(f"[{self.server_name}] Validation blocked: {blockage.log_message}")
            raise ContainerUpdateError(blockage.html_message, blockage.log_message)
        
        if 'com.docker.compose.project' in validator.labels:
            project = validator.labels['com.docker.compose.project']
            logger.debug(f"Container '{container.name}' is part of Compose project '{project}'")        
   
    def _get_image_info(self, container) -> Tuple[str, str]:
        image_name = container.attrs.get('Config', {}).get('Image')
        container_image_id = container.attrs.get('Image', '')
        
        if not image_name:
            raise ContainerUpdateError("Could not determine image name for the container.")
        
        logger.info(f"[{self.server_name}] Container image: {image_name}")
        logger.debug(f"[{self.server_name}] Current image ID: {container_image_id[:12]}...")
        
        return image_name, container_image_id
    
    def _pull_image(self, image_name: str):
        logger.info(f"[{self.server_name}] Pulling latest image: {image_name}")
        try:
            new_image = self.client.images.pull(image_name)
            logger.info(f"[{self.server_name}] Successfully pulled: {new_image.short_id}")
        except Exception as e:
            raise ContainerUpdateError(f"Failed to pull image '{image_name}': {e}")
    
    def _has_updates(self, image_name: str, container_image_id: str) -> bool:
        try:
            local_image = self.client.images.get(image_name)
            return container_image_id != local_image.id
        except Exception:
            return True
    
    def _generate_backup_name(self, container_name: str) -> str:
        timestamp = int(time.time())
        backup_name = f"{container_name}-backup-{timestamp}"
        
        counter = 1
        while True:
            try:
                self.client.containers.get(backup_name)
                backup_name = f"{container_name}-backup-{timestamp}-{counter}"
                counter += 1
            except docker.errors.NotFound:
                break
        
        return backup_name
    
    def _perform_update(self, container, backup_name: str, image_name: str, 
                        config: Dict[str, Any], networks: Dict[str, Any]) -> Dict[str, Any]:
        backup_container = None
        new_container = None
        
        try:
            self._stop_container(container)
            backup_container = self._rename_to_backup(container, backup_name)
            new_container = self._create_and_start(image_name, config, networks)
            self._cleanup_backup(backup_container, backup_name)
            
            success_msg = f"Container '{container.name}' updated successfully to latest image."
            if config.get('force'):
                success_msg += " (Forced update)"
            
            logger.info(f"[{self.server_name}] Successfully updated: {container.name}")
            return {"status": "success", "message": success_msg}
            
        except Exception as e:
            self._handle_failure(e, backup_container, backup_name, new_container, container.name)
    
    def _stop_container(self, container):
        logger.info(f"[{self.server_name}] Stopping: {container.name}")
        try:
            container.stop(timeout=self.timeouts['stop'])
            logger.info(f"[{self.server_name}] Container stopped")
        except Exception as e:
            logger.warning(f"[{self.server_name}] Graceful stop failed: {e}")
            try:
                container.kill()
                logger.info(f"[{self.server_name}] Container killed")
            except Exception as kill_error:
                logger.error(f"[{self.server_name}] Kill failed: {kill_error}")
                raise ContainerUpdateError(f"Failed to stop container: {e}")
    
    def _rename_to_backup(self, container, backup_name: str):
        logger.info(f"[{self.server_name}] Renaming to: {backup_name}")
        try:
            container.rename(backup_name)
            return container
        except Exception as e:
            try:
                container.start()
            except:
                pass
            raise ContainerUpdateError(f"Failed to rename container: {e}")
    
    def _create_and_start(self, image_name: str, config: Dict[str, Any], networks: Dict[str, Any]):
        logger.info(f"[{self.server_name}] Creating new container: {config['name']}")
        
        clean_config = {k: v for k, v in config.items() if v is not None}
        for key in ['environment', 'volumes', 'cap_add', 'cap_drop', 'devices', 'security_opt']:
            if key in clean_config and not clean_config[key]:
                del clean_config[key]
        
        try:
            new_container = self.client.containers.create(image_name, **clean_config)
        except Exception as e:
            logger.error(f"Failed to create with config: {clean_config}")
            raise ContainerUpdateError(f"Failed to create new container: {e}")
        
        if networks:
            self._connect_networks(new_container, networks)
        
        logger.info(f"[{self.server_name}] Starting new container")
        new_container.start()
        
        logger.info(f"[{self.server_name}] Verifying container started...")
        time.sleep(2)
        try:
            new_container.reload()
            if new_container.status != 'running':
                raise ContainerUpdateError(f"Container failed to start properly (status: {new_container.status})")
        except Exception as e:
            if isinstance(e, ContainerUpdateError):
                raise
            logger.warning(f"[{self.server_name}] Could not verify status: {e}")

        
        logger.info(f"[{self.server_name}] Container running successfully")
        return new_container
    
    def _connect_networks(self, container, networks: Dict[str, Any]):
        network_mode = container.attrs.get('HostConfig', {}).get('NetworkMode', '')
        
        if network_mode and network_mode.startswith('container:'):
            logger.info(f"Using network mode '{network_mode}', skipping network connections")
            return
        
        logger.info(f"[{self.server_name}] Connecting to networks")
        for network_name, network_config in networks.items():
            if network_name == 'bridge':
                continue
            
            try:
                network = self.client.networks.get(network_name)
                connect_config = {}
                if network_config.get('IPAddress'):
                    connect_config['ipv4_address'] = network_config['IPAddress']
                if network_config.get('Aliases'):
                    connect_config['aliases'] = network_config['Aliases']
                
                network.connect(container, **connect_config)
                logger.info(f"Connected to network: {network_name}")
            except Exception as e:
                logger.warning(f"Failed to connect to {network_name}: {e}")
    
    def _cleanup_backup(self, backup_container, backup_name: str):
        if not backup_container:
            return
        
        try:
            logger.info(f"[{self.server_name}] Removing backup: {backup_name}")
            backup_container.remove(force=True)
            logger.info(f"[{self.server_name}] Backup removed")
        except Exception as e:
            logger.warning(f"[{self.server_name}] Could not remove backup {backup_name}: {e}")
    
    def _handle_failure(self, error: Exception, backup_container, backup_name: str, 
                       new_container, original_name: str):
        logger.error(f"[{self.server_name}] Update failed: {error}")
        
        if new_container:
            try:
                new_container.remove(force=True)
                logger.info(f"[{self.server_name}] Cleaned up failed container")
            except Exception as cleanup_error:
                logger.warning(f"[{self.server_name}] Failed to cleanup: {cleanup_error}")
        
        if backup_container:
            try:
                logger.info(f"[{self.server_name}] Restoring original container")
                
                try:
                    temp = self.client.containers.get(original_name)
                    temp.remove(force=True)
                except docker.errors.NotFound:
                    pass
                
                backup_container.rename(original_name)
                backup_container.start()
                logger.info(f"[{self.server_name}] Original container restored")
                
            except Exception as restore_error:
                logger.error(f"[{self.server_name}] Failed to restore: {restore_error}")
                raise ContainerUpdateError(
                    f"Update failed: {error}. CRITICAL: Failed to restore original container: {restore_error}. "
                    f"Manual intervention required for '{backup_name}'"
                )
        
        raise ContainerUpdateError(f"Update failed: {error}. Original container restored.")


def update_container(client: docker.DockerClient, server_name: str, 
                     container_name: str, force: bool = False) -> Dict[str, Any]:
    with ContainerUpdater(client, server_name) as updater:
        return updater.update(container_name, force)