import json
from datetime import datetime
from functools import wraps
from flask import (
    Blueprint, render_template, jsonify, request, current_app, make_response
)
from flask_login import login_required, current_user

from .get_data import get_all_data
from .update_manager import update_container
from .docker_utils import discover_docker_clients
from .update import update_checker

main_bp = Blueprint('main', __name__)

def conditional_login_required(f):
    """Dekorator który wymaga logowania tylko gdy autoryzacja nie jest wyłączona."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_app.config.get('DISABLE_AUTH', False):
            return f(*args, **kwargs)
        else:
            from flask_login import current_user
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            return f(*args, **kwargs)
    return decorated_function

@main_bp.route("/")
@conditional_login_required
def index():
    version = current_app.config['APP_VERSION']
    return render_template("index.html", version=version)

@main_bp.route("/data")
@conditional_login_required
def data():
    return jsonify(get_all_data())

@main_bp.route("/check-updates", methods=["POST"])
@conditional_login_required
def check_updates():
    update_checker.start_check()
    request_data = request.get_json() or {}
    server_filter = request_data.get('server_filter', 'all')
    
    servers = discover_docker_clients()
    active_servers = [s for s in servers if s['status'] == 'active']
    
    if server_filter != 'all':
        active_servers = [s for s in active_servers if s['name'] == server_filter]
    
    updates = {}
    was_cancelled = False
    total_containers = 0
    processed_containers = 0
    
    for server in active_servers:
        try:
            containers = server['client'].containers.list(all=True)
            total_containers += len(containers)
        except Exception:
            pass
    
    current_app.logger.info(f"Starting update check for {total_containers} containers")
    
    for server in active_servers:
        if update_checker.is_cancelled:
            current_app.logger.info("Update check cancelled at server level.")
            was_cancelled = True
            break
            
        try:
            containers = server['client'].containers.list(all=True)
            for container in containers:
                if update_checker.is_cancelled:
                    current_app.logger.info(f"Update check cancelled at container {container.name}. Processed {processed_containers}/{total_containers}")
                    was_cancelled = True
                    break
                
                processed_containers += 1
                key = f"{server['name']}:{container.name}"
                
                if processed_containers == 1 or processed_containers % 10 == 0 or processed_containers == total_containers:
                    current_app.logger.info(f"Checking updates: {processed_containers}/{total_containers} - {key}")
                
                try:
                    update_available = update_checker.check_image_updates(
                        server['client'], container, server['name']
                    )
                    updates[key] = update_available
                except Exception as e:
                    updates[key] = False
                    current_app.logger.error(f"Error during update check for {key}: {e}")
                
                if update_checker.is_cancelled:
                    current_app.logger.info(f"Update check cancelled after processing {key}")
                    was_cancelled = True
                    break
                    
        except Exception as e:
            current_app.logger.error(f"Error accessing containers on {server['name']}: {e}")
        
        if was_cancelled:
            break

    if was_cancelled:
        current_app.logger.info(f"Update check cancelled. Processed {processed_containers}/{total_containers} containers")
    else:
        current_app.logger.info(f"Update check completed. Processed {processed_containers}/{total_containers} containers")

    return jsonify({
        "updates": updates, 
        "cancelled": was_cancelled,
        "progress": {
            "processed": processed_containers,
            "total": total_containers
        }
    })

@main_bp.route("/check-single-update", methods=["POST"])
@conditional_login_required
def check_single_update():
    """Sprawdza aktualizację dla pojedynczego kontenera."""
    update_checker.start_check()
    request_data = request.get_json() or {}
    server_name = request_data.get('server_name')
    container_name = request_data.get('container_name')
    
    if not server_name or not container_name:
        return jsonify({"error": "Missing server_name or container_name"}), 400
    
    if update_checker.is_cancelled:
        return jsonify({"cancelled": True}), 200
    
    servers = discover_docker_clients()
    server = next((s for s in servers if s['name'] == server_name and s['status'] == 'active'), None)
    
    if not server:
        return jsonify({"error": f"Server {server_name} not found or inactive"}), 404
    
    try:
        container = server['client'].containers.get(container_name)
        
        if update_checker.is_cancelled:
            return jsonify({"cancelled": True}), 200
            
        update_available = update_checker.check_image_updates(
            server['client'], container, server_name
        )
        
        key = f"{server_name}:{container_name}" 
        if update_available:
            current_app.logger.debug(f"⬆️ Update available for {key}")
        else:
            current_app.logger.debug(f"✅ Container {key} is up to date")
        return jsonify({
            "key": key,
            "update_available": update_available,
            "server_name": server_name,
            "container_name": container_name,
            "cancelled": update_checker.is_cancelled
        })
        
    except Exception as e:
        current_app.logger.error(f"Error checking update for {server_name}:{container_name}: {e}")
        return jsonify({"error": str(e)}), 500

@main_bp.route("/get-containers-list", methods=["POST"])  
@conditional_login_required
def get_containers_list():
    """Zwraca listę kontenerów do sprawdzenia bez sprawdzania aktualizacji."""
    request_data = request.get_json() or {}
    server_filter = request_data.get('server_filter', 'all')
    
    servers = discover_docker_clients()
    active_servers = [s for s in servers if s['status'] == 'active']
    
    if server_filter != 'all':
        active_servers = [s for s in active_servers if s['name'] == server_filter]
    
    containers_list = []
    
    for server in active_servers:
        try:
            for container in server['client'].containers.list(all=True):
                containers_list.append({
                    "server_name": server['name'],
                    "container_name": container.name,
                    "key": f"{server['name']}:{container.name}",
                    "image": container.attrs.get('Config', {}).get('Image', ''),
                    "status": container.status
                })
        except Exception as e:
            current_app.logger.error(f"Error accessing containers on {server['name']}: {e}")
    
    return jsonify({
        "containers": containers_list,
        "total": len(containers_list)
    })

@main_bp.route("/update-check-status", methods=["GET"])
@conditional_login_required
def get_update_check_status():
    """Zwraca status sprawdzania aktualizacji."""
    return jsonify({
        "is_cancelled": update_checker.is_cancelled,
        "cache_stats": update_checker.get_cache_stats()
    })

@main_bp.route("/cancel-updates", methods=["POST"])
@conditional_login_required
def cancel_updates():
    update_checker.cancel_check()
    current_app.logger.info("Cancellation request received.")
    return jsonify({"status": "cancellation_requested"})

@main_bp.route("/update-container", methods=["POST"])
@conditional_login_required
def update_container_route():
    """Uruchamia proces aktualizacji dla pojedynczego kontenera."""
    data = request.get_json()
    server_name = data.get('server_name')
    container_name = data.get('container_name')

    if not server_name or not container_name:
        return jsonify({"error": "Missing server_name or container_name"}), 400

    servers = discover_docker_clients()
    server = next((s for s in servers if s['name'] == server_name and s['status'] == 'active'), None)
    
    if not server:
        return jsonify({"error": f"Server '{server_name}' not found or inactive"}), 404
    
    try:
        result = update_container(server['client'], server_name, container_name)
        return jsonify(result), 200
    except (RuntimeError, ValueError) as e:
        # Przekaż szczegółowy komunikat błędu
        current_app.logger.error(f"Update error for {container_name}: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        # Loguj pełny błąd ale nie ujawniaj wszystkich szczegółów użytkownikowi
        current_app.logger.error(f"An unexpected error occurred during update of {container_name}: {e}")
        return jsonify({"error": f"{str(e)}"}), 500
    
@main_bp.route("/export/json")
@conditional_login_required
def export_json():
    server_filter = request.args.get('server', 'all')
    data = get_all_data()
    
    filtered_containers = data.get("containers", [])
    if server_filter != 'all':
        filtered_containers = [c for c in filtered_containers if c.get("server") == server_filter]
        
    export_data = {
        "export_info": {
            "timestamp": datetime.now().isoformat(),
            "dockpeek_version": current_app.config['APP_VERSION'],
            "server_filter": server_filter,
            "total_containers": len(filtered_containers),
        },
        "containers": []
    }
    for c in filtered_containers:
        export_container = {k: v for k, v in c.items() if k in ['name', 'server', 'stack', 'image', 'status', 'exit_code', 'custom_url']}
        if c.get("ports"): 
            export_container["ports"] = c["ports"]
        if c.get("traefik_routes"): 
            export_container["traefik_routes"] = [
                {"router": r["router"], "url": r["url"]} 
                for r in c["traefik_routes"]
            ]
        export_data["containers"].append(export_container)

    formatted_json = json.dumps(export_data, indent=2, ensure_ascii=False)
    filename = f'dockpeek-export-{server_filter}-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json'
    
    response = make_response(formatted_json)
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    response.headers['Content-Type'] = 'application/json'
    return response