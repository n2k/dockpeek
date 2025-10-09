import os

workers = int(os.environ.get('WORKERS', '4'))
worker_class = 'gevent'
worker_connections = 1024
bind = '0.0.0.0:8000'
timeout = 300
graceful_timeout = 30
keepalive = 75 
accesslog = '-'
errorlog = '-'
loglevel = 'info'
sendfile = False
backlog = 2048
# --- ASCII Art ---
def get_dockpeek_art():
    version = os.environ.get('VERSION', 'dev')
    return f"""
--  
--     _         _               _   
--   _| |___ ___| |_ ___ ___ ___| |_ 
--  | . | . |  _| '_| . | -_| -_| '_|
--  |___|___|___|_|_|  _|___|___|_|_|
--                  |_|              
--                                                               
══════ Version: {version}                
══════ https://github.com/dockpeek/dockpeek     
--
════ Starting {workers} workers with {worker_class} worker class...
════ Timeout: {timeout}s | Graceful timeout: {graceful_timeout}s
════ Worker connections: {worker_connections}
"""

# --- Server Hooks ---
def when_ready(server):
    print(get_dockpeek_art())
#    server.log.info(f"Starting {workers} workers with {worker_class} worker class...")
#    server.log.info(f"Timeout: {timeout}s | Graceful timeout: {graceful_timeout}s")
#    server.log.info(f"Worker connections: {worker_connections}")

def worker_exit(server, worker):
    server.log.info(f"Worker {worker.pid} exited")

def worker_abort(worker):
    worker.log.warning(f"Worker {worker.pid} aborted (may have been handling a long-running request)")