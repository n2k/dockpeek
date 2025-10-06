import logging
from flask import current_app

logger = logging.getLogger(__name__)


def get_container_logs(client, container_name, tail=500, timestamps=True, follow=False):
    """
    Pobiera logi kontenera.
    
    Args:
        client: Docker client
        container_name: Nazwa kontenera
        tail: Liczba ostatnich linii (default 500)
        timestamps: Czy dołączać timestampy (default True)
        follow: Czy streamować logi na żywo (default False)
    
    Returns:
        dict: Słownik z logami lub błędem
    """
    try:
        container = client.containers.get(container_name)
        
        logs = container.logs(
            tail=tail,
            timestamps=timestamps,
            follow=follow,
            stream=False
        )
        
        # Dekodowanie logów z bytes do string
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


def stream_container_logs(client, container_name, tail=10):
    """
    Generator do streamowania logów kontenera.
    
    Args:
        client: Docker client
        container_name: Nazwa kontenera
        tail: Liczba ostatnich linii do pobrania początkowo
    
    Yields:
        str: Kolejne linie logów
    """
    try:
        container = client.containers.get(container_name)
        
        for log_line in container.logs(
            tail=tail,
            timestamps=True,
            follow=True,
            stream=True
        ):
            yield log_line.decode('utf-8', errors='replace')
            
    except Exception as e:
        logger.error(f"Error streaming logs for {container_name}: {e}")
        yield f"Error: {str(e)}\n"