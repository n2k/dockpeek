
import os
import re
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for
import docker
from flask_cors import CORS
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse
from docker.client import DockerClient
from docker.constants import DEFAULT_TIMEOUT_SECONDS
import hashlib
from packaging import version
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
from threading import Lock

# === Flask Init ===
app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    raise RuntimeError("ERROR: SECRET_KEY environment variable is not set.")

app.secret_key = secret_key
CORS(app)

# === Cache dla update checks ===
update_cache = {}
cache_lock = Lock()
CACHE_DURATION = 300  # 5 minut cache

# === ThreadPoolExecutor dla asynchronicznych operacji ===
executor = ThreadPoolExecutor(max_workers=4)

class UpdateChecker:
    def __init__(self):
        self.cache = {}
        self.lock = Lock()
        self.cache_duration = 300  # 5 minut
        
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
        """
        Sprawdza czy lokalnie dostępny jest nowszy obraz niż ten używany przez kontener
        (szybkie sprawdzenie bez pullowania)
        """
        try:
            container_image_id = container.attrs.get('Image', '')
            if not container_image_id:
                return False
                
            image_name = container.attrs.get('Config', {}).get('Image', '')
            if not image_name:
                return False
            
            # Extract image name and tag
            if ':' in image_name:
                base_name, current_tag = image_name.rsplit(':', 1)
            else:
                base_name = image_name
                current_tag = 'latest'
            
            try:
                # Sprawdź czy lokalnie jest dostępny nowszy obraz
                local_image = client.images.get(f"{base_name}:{current_tag}")
                return container_image_id != local_image.id
                
            except Exception:
                # Jeśli nie ma lokalnego obrazu, nie ma aktualizacji
                return False
                
        except Exception as e:
            print(f"❌ Error checking local image updates: {e}")
            return False
    
    def check_image_updates_async(self, client, container, server_name):
        """
        Asynchroniczna wersja check_image_updates z cache
        """
        try:
            container_image_id = container.attrs.get('Image', '')
            if not container_image_id:
                return False
                
            image_name = container.attrs.get('Config', {}).get('Image', '')
            if not image_name:
                return False
            
            cache_key = self.get_cache_key(server_name, container.name, image_name)
            
            # Sprawdź cache
            cached_result, is_valid = self.get_cached_result(cache_key)
            if is_valid:
                print(f"🔄 Using cached update result for {image_name}")
                return cached_result
            
            # Extract image name and tag
            if ':' in image_name:
                base_name, current_tag = image_name.rsplit(':', 1)
            else:
                base_name = image_name
                current_tag = 'latest'
            
            print(f"🔍 Checking for updates for image {base_name}:{current_tag}")
            
            try:
                # Pull z timeoutem
                client.images.pull(base_name, tag=current_tag)
                updated_image = client.images.get(f"{base_name}:{current_tag}")
                updated_hash = updated_image.id
                
                result = container_image_id != updated_hash
                
                # Zapisz w cache
                self.set_cache_result(cache_key, result)
                
                if result:
                    print(f"✅ Update available for {base_name}:{current_tag}")
                else:
                    print(f"ℹ️ Image {base_name}:{current_tag} is up to date")
                
                return result
                
            except Exception as pull_error:
                print(f"⚠️ Cannot pull latest version of {base_name}:{current_tag}: {pull_error}")
                # Cache negative result for shorter time
                self.set_cache_result(cache_key, False)
                return False
                
        except Exception as e:
            print(f"❌ Error checking image updates: {e}")
            return False

# Global update checker instance
update_checker = UpdateChecker()

# === Flask-Login Init ===
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# === User credentials from environment ===
ADMIN_USERNAME = os.environ.get("USERNAME")
ADMIN_PASSWORD = os.environ.get("PASSWORD")

if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    raise RuntimeError("USERNAME and PASSWORD environment variables must be set.")

# Hashed user storage
users = {
    ADMIN_USERNAME: {
        "password": generate_password_hash(ADMIN_PASSWORD)
    }
}

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    if user_id in users:
        return User(user_id)
    return None

@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('login'))

# === Docker Client Logic ===

DOCKER_TIMEOUT = 0.3  # Timeout in seconds

def _extract_hostname_from_url(url):
    """
    Extracts hostname from Docker URL for public hostname determination.
    Returns None for local connections or internal Docker network names.
    """
    if not url:
        return None
    
    # Handle unix socket - this means local connection
    if url.startswith("unix://"):
        return None  # Will use request.host as fallback
    
    # Handle TCP connections
    if url.startswith("tcp://"):
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if hostname:
                # Local addresses should use request.host
                if hostname in ["127.0.0.1", "0.0.0.0", "localhost"]:
                    return None
                
                # Check if it's likely a Docker Compose service name
                # (internal names usually don't have dots and aren't IP addresses)
                if _is_likely_internal_hostname(hostname):
                    return None  # Requires explicit public_hostname
                
                return hostname  # Return actual remote hostname/IP
        except Exception:
            pass
    
    # Handle other protocols or malformed URLs
    try:
        # Match patterns like tcp://hostname:port or hostname:port
        match = re.search(r"(?:tcp://)?([^:]+)(?::\d+)?", url)
        if match:
            hostname = match.group(1)
            if hostname in ["127.0.0.1", "0.0.0.0", "localhost"]:
                return None
            
            if _is_likely_internal_hostname(hostname):
                return None  # Requires explicit public_hostname
                
            return hostname
    except Exception:
        pass
    
    return None


def _is_likely_internal_hostname(hostname):
    """
    Determines if a hostname is likely an internal Docker network name.
    """
    # If it's an IP address, it's not internal
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ip_pattern, hostname):
        return False
    
    # If it contains a dot, it's likely a real domain
    if '.' in hostname:
        return False
    
    # If it's a single word (like 'dockpeek-dev-socket-proxy'), 
    # it's likely a Docker Compose service name
    return True


def _get_link_hostname(public_hostname, host_ip, is_docker_host):
    """
    Determines the correct hostname for generating links.
    """
    # If we have an explicitly set public_hostname, use it
    if public_hostname:
        return public_hostname
    
    # For connections without explicit public_hostname, we need to be smart
    # If host_ip is a real remote IP, use it
    if host_ip and host_ip not in ['0.0.0.0', '127.0.0.1']:
        return host_ip
    
    # For local bindings (0.0.0.0, 127.0.0.1) or when host_ip is None,
    # use request.host as fallback
    # This works for:
    # - Local Docker connections
    # - Docker Compose setups where the app and containers are on the same host
    try:
        return request.host.split(":")[0]
    except:
        # If request is not available (e.g., in tests), fallback to localhost
        return "localhost"


def discover_docker_clients():
    """
    Discovers Docker clients from environment variables and checks their status.
    Returns a list of all discovered servers, including inactive ones.
    """
    clients = []
    
    # Support for DOCKER_HOST for backward compatibility
    if "DOCKER_HOST" in os.environ:
        host_url = os.environ.get("DOCKER_HOST")
        host_name = os.environ.get("DOCKER_HOST_NAME", "default")  # Allow custom name, default to "default"
        public_hostname = os.environ.get("DOCKER_HOST_PUBLIC_HOSTNAME")
        
        # Determine public hostname based on URL if not explicitly set
        if not public_hostname:
            public_hostname = _extract_hostname_from_url(host_url)
            # If still None, it means local connection or internal Docker name
            # - will use request.host later or require explicit configuration
        
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
            print(f"✅ Discovered and connected to default Docker daemon '{host_name}' at {host_url}")
        except Exception as e:
            print(f"❌ Error connecting to default Docker daemon '{host_name}' at {host_url}: {e}")
            clients.append({
                "name": host_name, 
                "client": None, 
                "url": host_url, 
                "public_hostname": public_hostname, 
                "status": "inactive", 
                "is_docker_host": True,
                "order": 0
            })

    # Discovery of DOCKER_HOST_n_URL and DOCKER_HOST_n_NAME
    host_vars = {k: v for k, v in os.environ.items() if re.match(r"^DOCKER_HOST_\d+_URL$", k)}
    for key, url in host_vars.items():
        match = re.match(r"^DOCKER_HOST_(\d+)_URL$", key)
        if match:
            num = match.group(1)
            name = os.environ.get(f"DOCKER_HOST_{num}_NAME", f"server{num}")
            public_hostname = os.environ.get(f"DOCKER_HOST_{num}_PUBLIC_HOSTNAME")
            
            # Determine public hostname based on URL if not explicitly set
            if not public_hostname:
                public_hostname = _extract_hostname_from_url(url)
                # If still None, it means local connection or internal Docker name
                # - will use request.host later or require explicit configuration
            
            try:
                client = DockerClient(base_url=url, timeout=DOCKER_TIMEOUT)
                client.ping()
                clients.append({
                    "name": name, 
                    "client": client, 
                    "url": url, 
                    "public_hostname": public_hostname, 
                    "status": "active", 
                    "is_docker_host": False,
                    "order": int(num)
                })
                print(f"✅ Discovered and connected to Docker daemon '{name}' at {url}")
            except Exception as e:
                print(f"❌ Error connecting to Docker daemon '{name}' at {url}: {e}")
                clients.append({
                    "name": name, 
                    "client": None, 
                    "url": url, 
                    "public_hostname": public_hostname, 
                    "status": "inactive", 
                    "is_docker_host": False,
                    "order": int(num)
                })

    # If no hosts are configured, try the local socket
    if not clients:
        fallback_name = os.environ.get("DOCKER_NAME", "default")
        print("⚠️ No Docker hosts configured via environment variables. Trying default socket...")
        try:
            client = docker.from_env(timeout=DOCKER_TIMEOUT)
            client.ping()
            clients.append({
                "name": fallback_name, 
                "client": client, 
                "url": "unix:///var/run/docker.sock", 
                "public_hostname": "", 
                "status": "active", 
                "is_docker_host": True,
                "order": 0
            })
            print(f"✅ Discovered and connected to default Docker daemon '{fallback_name}' via socket.")
        except Exception as e:
            print(f"❌ Failed to connect to any Docker daemon, including default socket: {e}")
            clients.append({
                "name": fallback_name, 
                "client": None, 
                "url": "unix:///var/run/docker.sock", 
                "public_hostname": "", 
                "status": "inactive", 
                "is_docker_host": True,
                "order": 0
            })
            
    return clients

def get_all_data():
    """
    Szybka wersja - najpierw zwraca dane, potem sprawdza aktualizacje w tle
    """
    servers = discover_docker_clients()
    
    if not servers:
        return {"servers": [], "containers": []}

    all_container_data = []
    server_list_for_json = [{"name": s["name"], "status": s["status"], "order": s["order"]} for s in servers]

    # Szybkie zbieranie podstawowych danych kontenerów
    for host in servers:
        if host['status'] == 'inactive':
            continue
        
        try:
            server_name = host["name"]
            client = host["client"]
            public_hostname = host["public_hostname"]
            is_docker_host = host["is_docker_host"]

            containers = client.containers.list(all=True)
            
            for container in containers:
                try:
                    # Get the original image name from container configuration
                    image_name = "unknown"
                    
                    try:
                        original_image = container.attrs.get('Config', {}).get('Image', '')
                        
                        if original_image:
                            image_name = original_image
                        else:
                            if hasattr(container, 'image') and container.image:
                                if hasattr(container.image, 'tags') and container.image.tags:
                                    image_name = container.image.tags[0]
                                else:
                                    image_name = container.image.id[:12] if hasattr(container.image, 'id') else "unknown"
                                    
                    except Exception as img_error:
                        print(f"⚠️ Could not access image info for container '{container.name}' on '{server_name}': {img_error}")
                        try:
                            image_name = container.attrs.get('Config', {}).get('Image', 'unknown')
                        except:
                            image_name = "missing-image"

                    # Port information
                    ports = container.attrs['NetworkSettings']['Ports']
                    port_map = []

                    if ports:
                        for container_port, mappings in ports.items():
                            if mappings:
                                m = mappings[0]
                                host_port = m['HostPort']
                                host_ip = m.get('HostIp', '0.0.0.0')
                                
                                link_hostname = _get_link_hostname(public_hostname, host_ip, is_docker_host)
                                link = f"http://{link_hostname}:{host_port}"
                                
                                port_map.append({
                                    'container_port': container_port,
                                    'host_port': host_port,
                                    'link': link
                                })

                    # Sprawdź cache dla update_available
                    cache_key = update_checker.get_cache_key(server_name, container.name, image_name)
                    cached_update, is_cache_valid = update_checker.get_cached_result(cache_key)
                    
                    container_info = {
                        'server': server_name,
                        'name': container.name,
                        'status': container.status,
                        'image': image_name,
                        'ports': port_map
                    }
                    # Sprawdź lokalnie dostępne aktualizacje (szybko, bez pullowania)
                    if cached_update is not None and is_cache_valid:
                        container_info['update_available'] = cached_update
                    else:
                        # Szybkie sprawdzenie lokalnych obrazów
                        local_update = update_checker.check_local_image_updates(client, container, server_name)
                        container_info['update_available'] = local_update
                    
                    all_container_data.append(container_info)
                    
                except Exception as container_error:
                    print(f"⚠️ Error processing container '{getattr(container, 'name', 'unknown')}' on '{server_name}': {container_error}")
                    all_container_data.append({
                        'server': server_name,
                        'name': getattr(container, 'name', 'unknown'),
                        'status': getattr(container, 'status', 'unknown'),
                        'image': 'error-loading',
                        'ports': []
                    })
                    
        except Exception as e:
            print(f"❌ Could not retrieve container data from host '{host.get('name', 'unknown')}'. Error: {e}. Marking as inactive.")
            for s in server_list_for_json:
                if s["name"] == host["name"]:
                    s["status"] = "inactive"
                    break
            continue

    return {"servers": server_list_for_json, "containers": all_container_data}


# === Routes ===

@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html")
    return redirect(url_for("login"))

@app.route("/data")
@login_required
def data():
    return jsonify(get_all_data())

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user_record = users.get(username)
        if user_record and check_password_hash(user_record["password"], password):
            login_user(User(username))
            return redirect(url_for("index"))
        else:
            error = "Invalid credentials. Please try again."
    return render_template("login.html", error=error)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/check-updates", methods=["POST"])
@login_required
def check_updates():
    """
    Endpoint do ręcznego sprawdzania aktualizacji wszystkich running kontenerów
    """
    servers = discover_docker_clients()
    active_servers = [s for s in servers if s['status'] == 'active']
    
    updates = {}
    
    def check_container_update(args):
        server, container = args
        try:
            if container.status == 'running':
                update_available = update_checker.check_image_updates_async(
                    server['client'], container, server['name']
                )
                container_key = f"{server['name']}:{container.name}"
                return container_key, update_available
        except Exception as e:
            print(f"❌ Error checking updates for {container.name}: {e}")
            return f"{server['name']}:{container.name}", False
        return None, None
    
    # Zbierz wszystkie running kontenery
    check_args = []
    for server in active_servers:
        try:
            containers = server['client'].containers.list(all=True)
            for container in containers:
                if container.status == 'running':
                    check_args.append((server, container))
        except Exception as e:
            print(f"❌ Error accessing containers on {server['name']}: {e}")
    
    # Sprawdź równolegle
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(check_container_update, check_args)
        for container_key, update_result in results:
            if container_key:
                updates[container_key] = update_result
    
    return jsonify({"updates": updates})

# === Entry Point ===
if __name__ == "__main__":
    if not os.path.exists('templates'):
        os.makedirs('templates')
        print("Created 'templates' directory.")
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=8000, debug=debug)
