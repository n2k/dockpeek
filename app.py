import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
import docker
from flask_cors import CORS
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

# === Flask Init ===
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "defaultsecretkey")
CORS(app)

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

# === Docker Client Init ===
try:
    docker_host = os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")
    client = docker.DockerClient(base_url=docker_host)
    client.ping()
    print("✅ Connected to Docker daemon.")
except Exception as e:
    print(f"❌ Error connecting to Docker daemon: {e}")
    client = None

# === Helpers ===
def get_container_data():
    if client is None:
        return []

    try:
        containers = client.containers.list(all=True)
    except Exception as e:
        print(f"Error retrieving container list: {e}")
        return []

    data = []
    for container in containers:
        ports = container.attrs['NetworkSettings']['Ports']
        port_map = []

        if ports:
            for container_port, mappings in ports.items():
                if mappings:
                    m = mappings[0]
                    host_ip = m['HostIp']
                    host_port = m['HostPort']
                    link_ip = request.host.split(":")[0] if host_ip in ['0.0.0.0', '127.0.0.1'] else host_ip
                    link = f"http://{link_ip}:{host_port}"
                    port_map.append({
                        'container_port': container_port,
                        'host_port': host_port,
                        'link': link
                    })

        data.append({
            'name': container.name,
            'id': container.short_id,
            'status': container.status,
            'image': container.image.tags[0] if container.image.tags else "none",
            'ports': port_map
        })

    return data

# === Routes ===

@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html")
    return redirect(url_for("login"))

@app.route("/data")
@login_required
def data():
    return jsonify(get_container_data())

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

# === Entry Point ===
if __name__ == "__main__":
    if not os.path.exists('templates'):
        os.makedirs('templates')
        print("Created 'templates' directory.")
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=8000, debug=debug)
