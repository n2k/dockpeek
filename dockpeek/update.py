import logging
from datetime import datetime, timedelta
from threading import Lock
import time
import signal
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class UpdateChecker:
    """Handles checking for container image updates with caching and cancellation support."""
    
    def __init__(self):
        self.cache = {}
        self.lock = Lock()
        self.cache_duration = 120
        self.is_cancelled = False
        self.pull_timeout = 300
        
    def start_check(self):
        """Reset the cancellation flag before starting a new check."""
        self.is_cancelled = False
        logger.debug("Update check started")

    def cancel_check(self):
        """Set the cancellation flag."""
        self.is_cancelled = True
        logger.info("Update check cancellation requested")

    @contextmanager
    def timeout_handler(self, seconds):
        """Context manager for handling timeouts."""
        def timeout_signal_handler(signum, frame):
            raise TimeoutError(f"Operation timed out after {seconds} seconds")
        
        old_handler = signal.signal(signal.SIGALRM, timeout_signal_handler)
        signal.alarm(seconds)
        
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def get_cache_key(self, server_name, container_name, image_name):
        """Generate a unique cache key for the given parameters."""
        return f"{server_name}:{container_name}:{image_name}"
    
    def is_cache_valid(self, timestamp):
        """Check if a cached result is still valid based on timestamp."""
        return datetime.now() - timestamp < timedelta(seconds=self.cache_duration)
    
    def get_cached_result(self, cache_key):
        """Retrieve a cached result if it exists and is valid."""
        with self.lock:
            if cache_key in self.cache:
                result, timestamp = self.cache[cache_key]
                if self.is_cache_valid(timestamp):
                    return result, True
        return None, False
    
    def set_cache_result(self, cache_key, result):
        """Store a result in the cache with current timestamp."""
        with self.lock:
            self.cache[cache_key] = (result, datetime.now())

    def clear_cache(self):
        """Clear all cached results."""
        with self.lock:
            self.cache.clear()
            logger.info("Update checker cache cleared")

    def check_local_image_updates(self, client, container, server_name):
        """Check for updates by comparing local image IDs (fast, no network)."""
        if self.is_cancelled:
            return False
            
        try:
            container_image_id = container.attrs.get('Image', '')
            if not container_image_id: 
                return False
                
            image_name = container.attrs.get('Config', {}).get('Image', '')
            if not image_name: 
                return False
                
            if ':' in image_name: 
                base_name, current_tag = image_name.rsplit(':', 1)
            else: 
                base_name, current_tag = image_name, 'latest'
                
            try:
                local_image = client.images.get(f"{base_name}:{current_tag}")
                return container_image_id != local_image.id
            except Exception: 
                return False
        except Exception as e:
            logger.error(f"Error checking local image updates for container '{container.name}': {e}")
            return False
    
    def check_image_updates(self, client, container, server_name):
        """Check for updates by pulling latest image and comparing with container's current image."""
        if self.is_cancelled:
            logger.debug(f"Update check cancelled before starting for {container.name}")
            return False
            
        try:
            container_image_id = container.attrs.get('Image', '')
            if not container_image_id: 
                return False
                
            image_name = container.attrs.get('Config', {}).get('Image', '')
            if not image_name: 
                return False
                
            cache_key = self.get_cache_key(server_name, container.name, image_name)
            cached_result, is_valid = self.get_cached_result(cache_key)
            if is_valid:
                logger.info(f"Using cached update result for {server_name}:{container.name}")
                return cached_result
            
            if ':' in image_name: 
                base_name, current_tag = image_name.rsplit(':', 1)
            else: 
                base_name, current_tag = image_name, 'latest'
                
            try:
                if self.is_cancelled:
                    logger.info(f"Update check cancelled before pulling {base_name}:{current_tag} on {server_name}")
                    return False
    
                logger.debug(f"Pulling {base_name}:{current_tag} on {server_name}")
                start_time = time.time()
                
                try:
                    with self.timeout_handler(self.pull_timeout):
                        client.images.pull(base_name, tag=current_tag)
                        
                except TimeoutError:
                    logger.warning(f"Pull timeout ({self.pull_timeout}s) for {base_name}:{current_tag} on {server_name}")
                    self.set_cache_result(cache_key, False)
                    return False
                
                if self.is_cancelled:
                    logger.info(f"Update check cancelled after pulling {base_name}:{current_tag} on {server_name}")
                    return False
                    
                pull_time = time.time() - start_time
                logger.debug(f"Pull completed in {pull_time:.2f}s for {base_name}:{current_tag}")
                
                # Get the updated local image
                updated_image = client.images.get(f"{base_name}:{current_tag}")
                
                # Compare container's current image ID with the pulled image ID
                result = container_image_id != updated_image.id
                
                self.set_cache_result(cache_key, result)                
                
                if result: 
                    logger.info(f"[{server_name}] ⬆️ Update available for {base_name}:{current_tag} (container: {container_image_id[:12]}..., latest: {updated_image.id[:12]}...)")
                else: 
                    logger.info(f"[{server_name}] ✅ Image up to date: {base_name}:{current_tag}")
                    
                return result                
                
            except Exception as pull_error:
                if self.is_cancelled:
                    logger.info(f"Update check cancelled during pull error handling for {base_name}:{current_tag}")
                    return False
                    
                logger.info(f"[{server_name}] ❌ Cannot pull {base_name}:{current_tag} - built locally or private repository: {pull_error}")
                self.set_cache_result(cache_key, False)
                return False
                
        except Exception as e:
            if not self.is_cancelled:
                logger.error(f"Error checking image updates for '{container.name}' on {server_name}: {e}")
            return False

    def get_cache_stats(self):
        """Get cache statistics."""
        with self.lock:
            total_entries = len(self.cache)
            valid_entries = 0
            now = datetime.now()
            
            for _, (_, timestamp) in self.cache.items():
                if self.is_cache_valid(timestamp):
                    valid_entries += 1
                    
            return {
                "total_entries": total_entries,
                "valid_entries": valid_entries,
                "expired_entries": total_entries - valid_entries,
                "cache_duration_seconds": self.cache_duration
            }


update_checker = UpdateChecker()