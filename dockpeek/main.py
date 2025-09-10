import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from flask import (
    Blueprint, render_template, jsonify, request, current_app, make_response
)
from flask_login import login_required, current_user

from .docker_utils import get_all_data, discover_docker_clients, update_checker

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
@login_required
def index():
    version = current_app.config['APP_VERSION']
    return render_template("index.html", version=version)

@main_bp.route("/data")
@login_required
def data():
    return jsonify(get_all_data())

@main_bp.route("/check-updates", methods=["POST"])
@login_required
def check_updates():
    request_data = request.get_json() or {}
    server_filter = request_data.get('server_filter', 'all')
    
    servers = discover_docker_clients()
    active_servers = [s for s in servers if s['status'] == 'active']
    
    if server_filter != 'all':
        active_servers = [s for s in active_servers if s['name'] == server_filter]
    
    updates = {}
    
    def check_container_update(args):
        server, container = args
        try:
            update_available = update_checker.check_image_updates_async(
                server['client'], container, server['name']
            )
            return f"{server['name']}:{container.name}", update_available
        except Exception:
            return f"{server['name']}:{container.name}", False

    check_args = []
    for server in active_servers:
        try:
            for container in server['client'].containers.list(all=True):
                check_args.append((server, container))
        except Exception as e:
            current_app.logger.error(f"❌ Error accessing containers on {server['name']}: {e}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(check_container_update, check_args)
        for key, result in results:
            updates[key] = result
            
    return jsonify({"updates": updates})


@main_bp.route("/export/json")
@login_required
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
        if c.get("ports"): export_container["ports"] = c["ports"]
        if c.get("traefik_routes"): export_container["traefik_routes"] = [{"router": r["router"], "url": r["url"]} for r in c["traefik_routes"]]
        export_data["containers"].append(export_container)

    formatted_json = json.dumps(export_data, indent=2, ensure_ascii=False)
    filename = f'dockpeek-export-{server_filter}-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json'
    
    response = make_response(formatted_json)
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    response.headers['Content-Type'] = 'application/json'
    return response