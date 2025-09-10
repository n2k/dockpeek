import logging
from datetime import datetime, timedelta
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Global thread pool executor for async operations
executor = ThreadPoolExecutor(max_workers=4)


class UpdateChecker:
    """Handles checking for container image updates with caching."""
    
    def __init__(self):
        self.cache = {}
        self.lock = Lock()
        self.cache_duration = 300  # 5 minutes
        
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

    def check_local_image_updates(self, client, container, server_name):
        """Check for updates by comparing local image IDs (fast, no network)."""
        try:
            container_image_id = container.attrs.get('Image', '')
            if not container_image_id: 
                return False
                
            image_name = container.attrs.get('Config', {}).get('Image', '')
            if not image_name: 
                return False
                
            # Parse image name and tag
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
            logger.error(f"Error checking local image updates for container '{container.name}'")
            return False
    
    def check_image_updates_async(self, client, container, server_name):
        """Check for updates by pulling latest image (slow, requires network)."""
        try:
            container_image_id = container.attrs.get('Image', '')
            if not container_image_id: 
                return False
                
            image_name = container.attrs.get('Config', {}).get('Image', '')
            if not image_name: 
                return False
                
            # Check cache first
            cache_key = self.get_cache_key(server_name, container.name, image_name)
            cached_result, is_valid = self.get_cached_result(cache_key)
            if is_valid:
                logger.info(f"📄[ {server_name} ] - Using cached update result for {image_name}: {cached_result}")
                return cached_result
            
            # Parse image name and tag
            if ':' in image_name: 
                base_name, current_tag = image_name.rsplit(':', 1)
            else: 
                base_name, current_tag = image_name, 'latest'
                
            try:
                # Pull latest version
                client.images.pull(base_name, tag=current_tag)
                updated_image = client.images.get(f"{base_name}:{current_tag}")
                result = container_image_id != updated_image.id
                
                # Cache the result
                self.set_cache_result(cache_key, result)                
                
                if result: 
                    logger.info(f" [ {server_name} ] - Update available - ⬆️{base_name}  :{current_tag}")
                else: 
                    logger.info(f" [ {server_name} ] - Image is up to date - ✅{base_name}  :{current_tag}")                
                return result                
                
            except Exception as pull_error:
                logger.warning(f" [ {server_name} ] - Cannot pull latest version of - ⚠️{base_name}  :{current_tag}  -  it might be a locally built image")
                self.set_cache_result(cache_key, False)
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking image updates for '{container.name}'")
            return False


# Global update checker instance
update_checker = UpdateChecker()