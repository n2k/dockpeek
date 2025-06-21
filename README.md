<img src="static/logo_2.svg" alt="dockpeek logo" width="60" height="60" />

# dockpeek

**dockpeek** is a lightweight, dashboard for monitoring Docker containers. With an simple UI and built-in authentication, it allows users to inspect container statuses and port mappings securely.

---

## Features

* **Port Mapping Visibility** — Maps host → container ports with clickable links
* **Container Overview** — Instantly see all running/stopped containers
* **Security-Oriented Design** — Supports `socket-proxy` for read-only Docker access
* **Export Data** — Easily export container information in JSON format
* **Login Authentication** — Simple username/password access
* **Dark Mode Support** — Theme toggle with persistence

---

## 📸 Screenshots

<p align="left">
  <img src="screenshot.png" alt="Night mode" width="800" />
</p>

---

## Getting Started

### Deployment Options

> **Recommended:** Use `socket-proxy` for secure access to Docker API.

### 🔧 Option 1: Secure Setup (with `socket-proxy`)

```yaml
services:
  dockpeek:
    image: ghcr.io/dockpeek/dockpeek:latest
    container_name: dockpeek
    environment:
      - SECRET_KEY=my_secret_key   # Set secret key
      - USERNAME=admin             # Change default username
      - PASSWORD=admin             # Change default password
      - DOCKER_HOST=tcp://dockpeek-socket-proxy:2375
    ports:
      - "3420:8000"
    depends_on:
      - dockpeek-socket-proxy
    restart: unless-stopped

  dockpeek-socket-proxy:
    image: lscr.io/linuxserver/socket-proxy:latest
    container_name: dockpeek-socket-proxy
    environment:
      - CONTAINERS=1
      - IMAGES=1
      - PING=1
      - VERSION=1
      - LOG_LEVEL=info
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    read_only: true
    tmpfs:
      - /run
    ports:
      - "2375:2375"
    restart: unless-stopped
```

### Option 2: Direct Access (without proxy)

> **⚠️ Not Recommended:** Grants full access to Docker Socket.

```yaml
services:
  dockpeek:
    image: ghcr.io/dockpeek/dockpeek:latest
    container_name: dockpeek
    environment:
      - SECRET_KEY=my_secret_key   # Set secret key
      - USERNAME=admin             # Change default username
      - PASSWORD=admin             # Change default password
    ports:
      - "3420:8000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    restart: unless-stopped
```
```yaml

environment:
  - SECRET_KEY=your_very_secret_key_here # **Required:** Change this to a unique, strong key for session management.
  - USERNAME=admin                       # **Required:** Change the default username for login.
  - PASSWORD=admin                       # **Required:** Change the default password for the specified username.
  - DOCKER_HOST=tcp://socket-proxy:2375  # **Optional:** Specifies the primary Docker daemon endpoint. If not set, the application attempts to connect to a local Docker socket.

  # **Optional:** Configure additional Docker hosts by uncommenting and modifying the following lines.
  # Each host requires a DOCKER_HOST_N_URL and DOCKER_HOST_N_NAME, where 'N' is an incrementing number.
  # Docker 1
  - DOCKER_HOST_1_URL=tcp://192.168.1.168:2375 # **Required for DOCKER_HOST_N_**: URL of the first additional Docker host.
  - DOCKER_HOST_1_NAME=Synology             # **Required for DOCKER_HOST_N_**: Display name for the first additional host in the UI.
  - DOCKER_HOST_1_PUBLIC_HOSTNAME=          # **Optional:** Public hostname/IP for the first host. Used for generating clickable links to exposed container ports. If empty, the app will try to infer from DOCKER_HOST_N_URL.
  # Docker 2
  - DOCKER_HOST_2_URL=unix:///var/run/docker.sock # **Required for DOCKER_HOST_N_**: URL of the second additional Docker host.
  - DOCKER_HOST_2_NAME=StagingEnvironment       # **Required for DOCKER_HOST_N_**: Display name for the second additional host in the UI.
  - DOCKER_HOST_2_PUBLIC_HOSTNAME=pisi          # **Optional:** Public hostname/IP for the second host. Used for generating clickable links to exposed container ports. If empty, the app will try to infer from DOCKER_HOST_N_URL.
  # Docker 3 ... etc.

  ```