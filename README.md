<div align="center">
  <a href="https://github.com/dockpeek/dockpeek">
     <img src="static/logo_2.svg" alt="dockpeek logo" width="80" height="80"/>
  </a>
</div>

<h1 align="center">Dockpeek</h1>
<h3 align="center">Docker Port Dashboard</h3>

<br>
<br>

**Dockpeek** is a lightweight dashboard for browsing and accessing exposed Docker container ports. It supports both local Docker sockets and remote ones via socket-proxy, making it easy to monitor containers across multiple hosts.


### Features

- **Port Mapping** — View exposed ports of running Docker containers with a clean, minimal UI.
- **Clickable Access** — Instantly open services running in containers via direct links.
- **Multi Docker Sockets** — Manage multiple Docker sockets in one place.  
- **No Configuration Required** – Auto-discovers containers from connected sockets.

<br>

<div align="center">

![Dockpeek Night mode screenshot](screenshot.png)

</div>

<br>

### Why Use Dockpeek?

Managing multiple Docker hosts and containers often means juggling IP addresses and port numbers to access your apps. **Dockpeek** streamlines this by letting you open containerized applications with a single click—no need to remember or type IPs and ports.

<br>

## Installation

### Option 1: Direct Access to Socket
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

<br>

### Option 2 : Through `socket-proxy`


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

<br>

### Additional Docker Sockets
```yaml
    environment:
      - SECRET_KEY=my_secret_key      # Set a secret key for security
      - USERNAME=admin               # Change the default username
      - PASSWORD=admin               # Change the default password
      
      # Optional: Add extra Docker hosts by setting these variables.
      # Each host needs DOCKER_HOST_N_URL, DOCKER_HOST_N_NAME, and optionally DOCKER_HOST_N_PUBLIC_HOSTNAME.
      
      # Docker Host 1
      - DOCKER_HOST_1_URL=unix:///var/run/docker.sock    # Docker socket URL
      - DOCKER_HOST_1_NAME=MyServer1                      # Name shown in the UI
      - DOCKER_HOST_1_PUBLIC_HOSTNAME=                    # Optional public hostname or IP for links; if empty, inferred from URL
      
      # Docker Host 2
      - DOCKER_HOST_2_URL=tcp://192.168.1.168:2375       # Docker proxy URL
      - DOCKER_HOST_2_NAME=Synology                        # Name shown in the UI
      - DOCKER_HOST_2_PUBLIC_HOSTNAME=NAS                  # Optional public hostname or IP (e.g. 'NAS' for Tailscale access)
      
      # Add more Docker hosts by increasing the number (3, 4, etc.)

```
  
> [!NOTE]
> `unix:///var/run/docker.sock`   Requires mounting the Docker socket `volumes: /var/run/docker.sock:/var/run/docker.sock`


<br>

  ## Environment

Dockpeek is configured entirely through environment variables. 
| Variable                        | Required | Description                                                                                                              |
| ------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| `SECRET_KEY`                    | Yes      | A strong, unique secret.                                               |
| `USERNAME`                      | Yes      | Username for Dockpeek login.      |
| `PASSWORD`                      | Yes      | Password for Dockpeek login.        |
| `DOCKER_HOST`                   | No       | URL of the primary Docker socket (e.g., `unix:///var/run/docker.sock` or `tcp://socket-proxy:2375`). Defaults to local socket if omitted. Recommended for use with a local proxy                |
| `DOCKER_HOST_N_URL`             | No       | Defines an additional Docker host (e.g., `tcp://192.168.1.10:2375`). Replace `N` with a number (`1`, `2`, `3`, ...).     |
| `DOCKER_HOST_N_NAME`            | No       | Friendly name for the additional Docker host shown in the UI.                             |
| `DOCKER_HOST_N_PUBLIC_HOSTNAME` | No       | Public hostname or IP for clickable links (e.g. 'NAS' for Tailscale access); If unset, it's inferred from the `DOCKER_HOST_N_URL`. |
  
> [!NOTE]
> All multi-host variables (`DOCKER_HOST_N_*`) must use matching `N` indices for URL, name, and hostname entries.
