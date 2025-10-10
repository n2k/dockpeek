import logging
from flask import current_app

logger = logging.getLogger(__name__)


def get_container_logs(client, container_name, tail=500, timestamps=True, follow=False):
    try:
        container = client.containers.get(container_name)
        
        logs = container.logs(
            tail=tail,
            timestamps=timestamps,
            follow=follow,
            stream=False
        )
        
        logs_text = logs.decode('utf-8', errors='replace')
        
        return {
            'success': True,
            'logs': logs_text,
            'container_name': container_name,
            'lines': len(logs_text.splitlines())
        }
        
    except Exception as e:
        logger.error(f"Error fetching logs for {container_name}: {e}")
        return {
            'success': False,
            'error': str(e),
            'container_name': container_name
        }


def stream_container_logs(client, container_name, tail=100):
    container = None
    log_stream = None
    try:
        container = client.containers.get(container_name)
        log_stream = container.logs(
            tail=tail,
            timestamps=True,
            follow=True,
            stream=True
        )
        
        for log_line in log_stream:
            yield log_line.decode('utf-8', errors='replace')
            
    except Exception as e:
        logger.error(f"Error streaming logs for {container_name}: {e}")
        yield f"Error: {str(e)}\n"
    finally:
        if log_stream:
            try:
                log_stream.close()
            except:
                pass
