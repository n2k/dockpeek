<img src="static/logo_2.svg" alt="dockpeek logo" width="60" height="60" />

# dockpeek

**dockpeek** is a lightweight dashboard for inspecting Docker container port mappings and statuses via a web interface.

---

## ✨ Features

- 🔍 Displays Docker container port-to-host mappings
- 🟢 Shows container status (running, stopped, etc.)
- 🔎 Filter containers by name or image
- 🌙 Dark mode support
- 🔐 User login
- 🐳 Easy to deploy with Docker Compose

---

## 📸 Screenshots

<p align="left">
  <img src="dockpeek_night_mode.png" alt="Night mode" width="800" />
</p>

---

## 🚀 Installation & Usage

### Using Docker Compose

To run dockpeek with a secure Docker socket proxy:

```yaml
services:
  dockpeek:
    container_name: dockpeek
    build:
      context: .
    environment:
      - SECRET_KEY=my_secret_key
      - USERNAME=admin
      - PASSWORD=admin
      - DOCKER_HOST=tcp://socket-proxy:2375
    ports:
      - "3420:8000"
    depends_on:
      - socket-proxy

  socket-proxy:
    image: lscr.io/linuxserver/socket-proxy:latest
    container_name: socket-proxy
    environment:
      - CONTAINERS=1
      - IMAGES=1
      - PING=1
      - VERSION=1
      - LOG_LEVEL=info
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /run
    ports:
      - "2375:2375"
