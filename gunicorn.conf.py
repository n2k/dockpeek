import os

workers = int(os.environ.get('WORKERS', '4'))
worker_class = 'gevent'
worker_connections = 1000
bind = '0.0.0.0:8000'
timeout = 600
graceful_timeout = 60
keepalive = 75  # Important for SSE connections
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Prevent request buffering for SSE streams
sendfile = False
# Allow larger number of pending connections
backlog = 2048

# --- ASCII Art ---
def get_dockpeek_art():
    version = os.environ.get('VERSION', 'dev')
    return f"""                                                               
██████╗  ██████╗  ██████╗██╗  ██╗██████╗ ███████╗███████╗██╗  ██╗
██╔══██╗██╔═══██╗██╔════╝██║ ██╔╝██╔══██╗██╔════╝██╔════╝██║ ██╔╝
██║  ██║██║   ██║██║     █████╔╝ ██████╔╝█████╗  █████╗  █████╔╝ 
██║  ██║██║   ██║██║     ██╔═██╗ ██╔═══╝ ██╔══╝  ██╔══╝  ██╔═██╗ 
██████╔╝╚██████╔╝╚██████╗██║  ██╗██║     ███████╗███████╗██║  ██╗
╚═════╝  ╚═════╝  ╚═════╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝╚═╝  ╚═╝
                                                Version: {version}
"""

# --- Server Hooks ---
def when_ready(server):
    print(get_dockpeek_art())
    server.log.info(f"Starting {workers} workers with {worker_class} worker class...")
    server.log.info(f"Timeout: {timeout}s | Graceful timeout: {graceful_timeout}s")
    server.log.info(f"Worker connections: {worker_connections}")

def worker_exit(server, worker):
    server.log.info(f"Worker {worker.pid} exited")

def worker_abort(worker):
    worker.log.warning(f"Worker {worker.pid} aborted (may have been handling a long-running request)")