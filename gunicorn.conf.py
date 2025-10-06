import os

workers = int(os.environ.get('WORKERS', '4'))
worker_class = 'gevent'
worker_connections = 1000
bind = '0.0.0.0:8000'
timeout = 300
graceful_timeout = 30
accesslog = '-'
errorlog = '-'
loglevel = 'info'

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

# --- Server Hook ---
def when_ready(server):
    print(get_dockpeek_art())
    server.log.info(f"Starting {workers} workers...")