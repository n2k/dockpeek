import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)

class InactivePersistence:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the SQLite database with required tables."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS inactive_containers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        server TEXT NOT NULL,
                        name TEXT NOT NULL,
                        container_id TEXT,
                        image TEXT,
                        image_size TEXT,
                        stack TEXT,
                        source_url TEXT,
                        custom_url TEXT,
                        tags TEXT,  -- JSON string
                        ports TEXT,  -- JSON string
                        traefik_routes TEXT,  -- JSON string
                        port_range_grouping BOOLEAN DEFAULT 1,
                        status TEXT DEFAULT 'inactive',
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT 0,
                        inactive_config TEXT,  -- JSON string
                        inactive_status TEXT,
                        inactive_color TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(server, name)
                    )
                ''')
                
                # Create indexes for better performance
                conn.execute('CREATE INDEX IF NOT EXISTS idx_server_name ON inactive_containers(server, name)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_last_seen ON inactive_containers(last_seen)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_is_active ON inactive_containers(is_active)')
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error initializing inactive containers database: {e}")

    def save_containers(self, containers: List[Dict[str, Any]]):
        """Save inactive containers to SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Clear existing data
                conn.execute('DELETE FROM inactive_containers')
                
                # Insert new data
                for container in containers:
                    conn.execute('''
                        INSERT INTO inactive_containers (
                            server, name, container_id, image, image_size, stack, source_url, custom_url,
                            tags, ports, traefik_routes, port_range_grouping, status,
                            first_seen, last_seen, is_active, inactive_config,
                            inactive_status, inactive_color
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        container.get('server', ''),
                        container.get('name', ''),
                        container.get('container_id', ''),
                        container.get('image', ''),
                        container.get('image_size', ''),
                        container.get('stack', ''),
                        container.get('source_url', ''),
                        container.get('custom_url', ''),
                        json.dumps(container.get('tags', [])),
                        json.dumps(container.get('ports', [])),
                        json.dumps(container.get('traefik_routes', [])),
                        container.get('port_range_grouping', True),
                        container.get('status', 'inactive'),
                        container.get('first_seen', ''),
                        container.get('last_seen', ''),
                        container.get('is_active', False),
                        json.dumps(container.get('inactive_config', {})),
                        container.get('inactive_status', ''),
                        container.get('inactive_color', '')
                    ))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving inactive containers to database: {e}")

    def load_containers(self) -> List[Dict[str, Any]]:
        """Load inactive containers from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM inactive_containers
                    ORDER BY last_seen DESC
                ''')
                
                containers = []
                for row in cursor.fetchall():
                    container = dict(row)
                    
                    # Parse JSON fields
                    container['tags'] = json.loads(container['tags'] or '[]')
                    container['ports'] = json.loads(container['ports'] or '[]')
                    container['traefik_routes'] = json.loads(container['traefik_routes'] or '[]')
                    container['inactive_config'] = json.loads(container['inactive_config'] or '{}')
                    
                    # Remove database-specific fields
                    container.pop('id', None)
                    container.pop('created_at', None)
                    container.pop('updated_at', None)
                    
                    containers.append(container)
                
                return containers
        except Exception as e:
            logger.error(f"Error loading inactive containers from database: {e}")
            return []

    def delete_container(self, server: str, name: str) -> bool:
        """Delete a specific inactive container from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'DELETE FROM inactive_containers WHERE server = ? AND name = ?',
                    (server, name)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting inactive container from database: {e}")
            return False

    def clear_containers(self, inactive_only: bool = True) -> int:
        """Clear inactive containers from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if inactive_only:
                    cursor = conn.execute('DELETE FROM inactive_containers WHERE is_active = 0')
                else:
                    cursor = conn.execute('DELETE FROM inactive_containers')
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Error clearing inactive containers from database: {e}")
            return 0

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about inactive containers in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT COUNT(*) as total FROM inactive_containers')
                total = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) as inactive FROM inactive_containers WHERE is_active = 0')
                inactive = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) as active FROM inactive_containers WHERE is_active = 1')
                active = cursor.fetchone()[0]
                
                return {
                    'total': total,
                    'inactive': inactive,
                    'active': active
                }
        except Exception as e:
            logger.error(f"Error getting inactive containers stats: {e}")
            return {'total': 0, 'inactive': 0, 'active': 0}