<div align="center">
  <a href="https://github.com/dockpeek/dockpeek">
     <img src="dockpeek/static/images/logo_2.svg" alt="dockpeek logo" width="80" height="80"/>
  </a>
  <h1>Dockpeek</h1>
  <h3>Docker Dashboard for Easy Container Access</h3>
  
  
 <p>A lightweight, self-hosted Docker dashboard for quick access to container web interfaces across multiple hosts. Monitor ports, manage updates with one-click, and integrate seamlessly with Traefik.</p>
</div>

## ✨ Features

- **Port Mapping Overview** — View all running containers and their published ports at a glance
- **One-Click Access** — Launch containerized web applications instantly with direct URL links
- **Traefik Integration** — Automatically detect and display container addresses from Traefik labels
- **Multi-Host Management** — Monitor multiple Docker hosts from a unified dashboard
- **Zero Configuration** — Detects containers automatically with no setup required
- **Image Update Management** — Monitor and install updates
- **Mobile-Responsive** — Full functionality across smartphones, tablets, and desktops

### Labels Support

Enhance control with custom labels:
- `dockpeek.https` — Force HTTPS protocol for specific ports
- `dockpeek.link` — Make container names clickable links
- `dockpeek.ports` — Add custom ports to display alongside detected ports
- `dockpeek.tags` — Organize and categorize containers with custom tags

<div align="center">
  
![Dockpeek Night mode screenshot](screenshot_v1.6.2.png)

</div>

---

## 🚀 Quick Start

### Basic Setup (Recommended)

The easiest way to get started with Dockpeek:

```yaml
services:
  dockpeek:
    image: ghcr.io/dockpeek/dockpeek:latest
    container_name: dockpeek
    environment:
      - SECRET_KEY=your_secure_secret_key_here
      - USERNAME=admin
      - PASSWORD=your_secure_password_here
    ports:
      - "3420:8000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    restart: unless-stopped
```

**Then visit:** http://localhost:3420

### Secure Setup with Socket Proxy

For enhanced security, use a socket proxy to limit Docker API access:

```yaml
services:
  dockpeek:
    image: ghcr.io/dockpeek/dockpeek:latest
    container_name: dockpeek
    environment:
      - SECRET_KEY=your_secure_secret_key_here
      - USERNAME=admin
      - PASSWORD=your_secure_password_here
      - DOCKER_HOST=tcp://socket-proxy:2375
    ports:
      - "3420:8000"
    depends_on:
      - socket-proxy
    restart: unless-stopped

  socket-proxy:
    image: lscr.io/linuxserver/socket-proxy:latest
    container_name: dockpeek-socket-proxy
    environment:
      - CONTAINERS=1
      - IMAGES=1
      - PING=1
      - VERSION=1
      - INFO=1
      - POST=1
      # Required for container updates
      - ALLOW_START=1  
      - ALLOW_STOP=1     
      - ALLOW_RESTARTS=1  
      - NETWORKS=1     
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    read_only: true
    tmpfs:
      - /run
    restart: unless-stopped
```

---

## 🌐 Multi-Host Setup

Manage multiple Docker hosts from a single dashboard:

```yaml
services:
  dockpeek:
    image: ghcr.io/dockpeek/dockpeek:latest
    container_name: dockpeek
    ports:
      - "3420:8000"
    environment:
      - SECRET_KEY=your_secure_secret_key_here
      - USERNAME=admin
      - PASSWORD=your_secure_password_here
      
      # Local Docker
      - DOCKER_HOST_1_URL=unix:///var/run/docker.sock
      - DOCKER_HOST_1_NAME=Local Development
      
      # Remote Server
      - DOCKER_HOST_2_URL=tcp://192.168.1.100:2375
      - DOCKER_HOST_2_NAME=Production Server
      - DOCKER_HOST_2_PUBLIC_HOSTNAME=server.local
      
      # Add more hosts as needed...
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    restart: unless-stopped
```

> [!TIP]
> Install a Docker Socket Proxy on each remote host for secure API access.

---

## ⚙️ Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | **Required.** Secure secret key for session security |
| `USERNAME` | **Required.** Username for dashboard login |
| `PASSWORD` | **Required.** Password for dashboard login |

### Optional Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DISABLE_AUTH` | `false` | Set to `true` to disable authentication |
| `TRAEFIK_LABELS` | `true` | Show Traefik integration column |
| `TAGS` | `true` | Enable container tagging feature |
| `DOCKER_HOST` | Local socket | Primary Docker connection URL |
| `DOCKER_HOST_NAME` | `default` | Display name for the primary server in the UI |
| `DOCKER_HOST_PUBLIC_HOSTNAME` | Auto-detected | Optional hostname or IP for generating clickable links |

### Multi-Host Variables

For additional Docker hosts, use the pattern `DOCKER_HOST_N_*`:

| Variable | Description |
|----------|-------------|
| `DOCKER_HOST_N_URL` | Docker API URL (e.g., `tcp://host:2375`) |
| `DOCKER_HOST_N_NAME` | Display name in the dashboard |
| `DOCKER_HOST_N_PUBLIC_HOSTNAME` | Optional public hostname for links |

> [!IMPORTANT]
> **Important Configuration Requirements:**
> - `SECRET_KEY` must always be set for session security
> - `USERNAME` and `PASSWORD` are required unless `DISABLE_AUTH=true`
> - Multi-host variables require matching `N` identifiers (URL, name, hostname)

---

## 🏷️ Container Labels

Customize how containers appear and behave in Dockpeek:

```yaml
services:
  webapp:
    image: nginx:latest
    ports:
      - "3001:80"
    labels:
      - "dockpeek.ports=8080,9090"              # Show additional ports
      - "dockpeek.https=3001,8080"              # Force HTTPS for these ports
      - "dockpeek.link=https://myapp.local"     # Make container name clickable
      - "dockpeek.tags=frontend,production"     # Add organization tags
```

### Available Labels

| Label | Purpose | Example |
|-------|---------|---------|
| `dockpeek.ports` | Show additional ports | `dockpeek.ports=8080,9090` |
| `dockpeek.https` | Force HTTPS for ports | `dockpeek.https=443,8443` |
| `dockpeek.link` | Custom container link | `dockpeek.link=https://app.com` |
| `dockpeek.tags` | Organization tags | `dockpeek.tags=web,prod` |

---

## 🐳 Docker Swarm Support

Deploy Dockpeek in Docker Swarm mode to manage all services and tasks:

<details>
<summary>Click to see Swarm deployment example</summary>

```yaml
services:
  dockpeek:
    image: ghcr.io/dockpeek/dockpeek:latest
    environment:
      - SECRET_KEY=your_secure_secret_key_here
      - USERNAME=admin
      - PASSWORD=your_secure_password_here
      - TRAEFIK_LABELS=true
      - DOCKER_HOST=tcp://tasks.socket-proxy:2375
    ports:
      - "3420:8000"
    networks:
      - traefik
      - socket-proxy
    deploy:
      replicas: 1
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.dockpeek.rule=Host(`dockpeek.example.com`)"
        - "traefik.http.routers.dockpeek.entrypoints=websecure"
        - "traefik.http.routers.dockpeek.tls=true"
        - "traefik.http.services.dockpeek.loadbalancer.server.port=8000"

  socket-proxy:
    image: lscr.io/linuxserver/socket-proxy:latest
    environment:
      - CONTAINERS=1
      - IMAGES=1
      - SERVICES=1
      - TASKS=1
      - NODES=1
      - PING=1
      - VERSION=1
      - INFO=1
      - POST=1
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - socket-proxy
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager

networks:
  socket-proxy:
  traefik:
    external: true
```

Deploy with: `docker stack deploy -c docker-compose-swarm.yml dockpeek`

</details>

---

## Frequently Asked Questions

<details>
<summary><strong>How do I search for containers by port?</strong></summary>

Use the format `:port` in the search box. For example, typing `:8080` will show all containers exposing port 8080.

</details>

<details>
<summary><strong>When does Dockpeek use HTTPS automatically?</strong></summary>

Dockpeek automatically uses HTTPS for:
- Container port `443/tcp`
- Host ports ending with `443` (e.g., `8443`, `9443`)
- Ports specified with the `dockpeek.https` label

</details>

<details>
<summary><strong>How do I make container names clickable?</strong></summary>

Use the `dockpeek.link` label:

```yaml
labels:
  - "dockpeek.link=https://myapp.example.com"
```

This is especially useful with reverse proxies to link directly to public addresses.

</details>

<details>
<summary><strong>How do I show ports for containers without port mapping?</strong></summary>

Some containers (like those using host networking or behind reverse proxies) don't expose ports through Docker's standard port mapping. Use the `dockpeek.ports` label:

```yaml
labels:
  - "dockpeek.ports=8096,8920"
```

</details>

<details>
<summary><strong>How do I clear the search filter?</strong></summary>

Click on the "Dockpeek" logo/title at the top of the page to reset the search and return to the full container view.

</details>

<details>
<summary><strong>What permissions does Dockpeek need for updates?</strong></summary>

To install container updates, Dockpeek needs:

**For direct Docker socket access:**
- Read/write access to `/var/run/docker.sock`

**For socket-proxy setups, ensure these permissions are enabled:**
```yaml
environment:
  - POST=1             # Required for API write operations
  - ALLOW_START=1      # Start containers after update
  - ALLOW_STOP=1       # Stop containers for update
  - ALLOW_RESTARTS=1   # Restart containers if needed
  - NETWORKS=1         # Connect containers to networks
```

The update feature works with all supported connection methods (local socket, remote socket-proxy, and multi-host configurations).

</details>

---

## 🤝 Contributing

We welcome contributions! Please feel free to submit issues and pull requests.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <p>Made with ❤️ for the Docker community</p>
  <p>
    <a href="https://github.com/dockpeek/dockpeek/issues">Report Bug</a> •
    <a href="https://github.com/dockpeek/dockpeek/issues">Request Feature</a>
  </p>
</div>