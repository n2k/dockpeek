import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
import logging
from timelength import TimeLength

logger = logging.getLogger(__name__)

def parse_duration(duration_str: str) -> Tuple[timedelta, str]:
    """Parse duration string using TimeLength library, returns (duration, operator)."""
    if not duration_str:
        return timedelta(0), '='
    
    duration_str = duration_str.strip()
    
    # Extract comparison operator
    operator = '='
    if duration_str.startswith(('<=', '>=')):
        operator = duration_str[:2]
        duration_part = duration_str[2:].strip()
    elif duration_str.startswith(('<', '>')):
        operator = duration_str[0]
        duration_part = duration_str[1:].strip()
    else:
        duration_part = duration_str
    
    try:
        # TimeLength supports many formats: "5min", "30 minutes", "1h", "2d", "1.5 hours", etc.
        time_length = TimeLength(duration_part)
        # Convert milliseconds to seconds
        seconds = time_length.to_milliseconds() / 1000
        return timedelta(seconds=seconds), operator
    except Exception as e:
        logger.warning(f"Invalid duration format '{duration_str}': {e}")
        return timedelta(0), '='

def parse_multiple_durations(duration_str: str) -> List[Tuple[timedelta, str]]:
    """Parse multiple duration conditions separated by commas, returns list of (duration, operator)."""
    if not duration_str:
        return [(timedelta(0), '=')]
    
    conditions = []
    for condition in duration_str.split(','):
        condition = condition.strip()
        if condition:
            duration, operator = parse_duration(condition)
            conditions.append((duration, operator))
    
    return conditions if conditions else [(timedelta(0), '=')]

def parse_color(color_str: str) -> str:
    """Parse color string, return default if invalid."""
    if not color_str:
        return "#6c757d"  # Default gray
    
    # Basic validation for hex colors
    if color_str.startswith('#') and len(color_str) in [4, 7]:
        return color_str
    
    # Try to parse as hex without #
    if re.match(r'^[0-9a-fA-F]{3}$', color_str):
        return f"#{color_str}"
    if re.match(r'^[0-9a-fA-F]{6}$', color_str):
        return f"#{color_str}"
    
    logger.warning(f"Invalid color format: {color_str}")
    return "#6c757d"

def parse_inactive_config(container_labels: Dict[str, str], global_config: Dict[str, Any]) -> Dict[str, Any]:
    """Parse inactive container configuration from container labels and global config."""
    ignore_conditions = parse_multiple_durations(global_config.get('INACTIVE_IGNORE_THRESHOLD', '5min'))
    warn_duration, warn_op = parse_duration(global_config.get('INACTIVE_WARN_THRESHOLD', '30min'))
    critical_duration, critical_op = parse_duration(global_config.get('INACTIVE_CRITICAL_THRESHOLD', '1h'))
    
    config = {
        'enabled': global_config.get('INACTIVE_TRACKING_ENABLE', True),
        'ignore_conditions': [(int(duration.total_seconds()), operator) for duration, operator in ignore_conditions],
        'warn_threshold_seconds': int(warn_duration.total_seconds()),
        'warn_operator': warn_op,
        'critical_threshold_seconds': int(critical_duration.total_seconds()),
        'critical_operator': critical_op,
        'warn_color': parse_color(global_config.get('INACTIVE_WARN_COLOR', '#ff9e00')),
        'critical_color': parse_color(global_config.get('INACTIVE_CRITICAL_COLOR', '#ff0000')),
        'persist_enabled': bool(global_config.get('PERSIST_INACTIVE', '')),
    }
    
    # Override with container-specific labels
    if 'dockpeek.inactive-ignore' in container_labels:
        ignore_conditions = parse_multiple_durations(container_labels['dockpeek.inactive-ignore'])
        config['ignore_conditions'] = [(int(duration.total_seconds()), operator) for duration, operator in ignore_conditions]
    
    if 'dockpeek.inactive-warn' in container_labels:
        warn_parts = container_labels['dockpeek.inactive-warn'].split(',')
        if len(warn_parts) >= 1:
            warn_duration, warn_op = parse_duration(warn_parts[0].strip())
            config['warn_threshold_seconds'] = int(warn_duration.total_seconds())
            config['warn_operator'] = warn_op
        if len(warn_parts) >= 2:
            config['warn_color'] = parse_color(warn_parts[1].strip())
    
    if 'dockpeek.inactive-critical' in container_labels:
        critical_parts = container_labels['dockpeek.inactive-critical'].split(',')
        if len(critical_parts) >= 1:
            critical_duration, critical_op = parse_duration(critical_parts[0].strip())
            config['critical_threshold_seconds'] = int(critical_duration.total_seconds())
            config['critical_operator'] = critical_op
        if len(critical_parts) >= 2:
            config['critical_color'] = parse_color(critical_parts[1].strip())
    
    # Container-specific enable/disable
    if 'dockpeek.inactive-tracking' in container_labels:
        config['enabled'] = container_labels['dockpeek.inactive-tracking'].lower() in ['true', '1', 'yes', 'on']
    
    return config

def get_inactive_status(last_seen: datetime, config: Dict[str, Any]) -> Tuple[str, str]:
    """Get inactive status and color based on last seen time and configuration."""
    if not config['enabled']:
        return 'disabled', '#6c757d'
    
    now = datetime.now(last_seen.tzinfo)
    time_since_seconds = int((now - last_seen).total_seconds())
    
    # Helper function to check if time matches the threshold with operator
    def matches_threshold(time_seconds, threshold_seconds, operator):
        if operator == '<':
            return time_seconds < threshold_seconds
        elif operator == '<=':
            return time_seconds <= threshold_seconds
        elif operator == '>':
            return time_seconds > threshold_seconds
        elif operator == '>=':
            return time_seconds >= threshold_seconds
        else:  # '=' or default
            return time_seconds <= threshold_seconds
    
    # Check ignore conditions - if ANY condition matches, container is ignored
    for threshold_seconds, operator in config['ignore_conditions']:
        if matches_threshold(time_since_seconds, threshold_seconds, operator):
            return 'ignored', '#6c757d'
    
    # Check warn threshold
    if matches_threshold(time_since_seconds, config['warn_threshold_seconds'], config['warn_operator']):
        return 'warn', config['warn_color']
    
    # Check critical threshold
    if matches_threshold(time_since_seconds, config['critical_threshold_seconds'], config['critical_operator']):
        return 'critical', config['critical_color']
    
    # No status if no conditions match
    return None, None

def should_track_inactive(container_labels: Dict[str, str], global_config: Dict[str, Any]) -> bool:
    """Determine if a container should be tracked for inactive status."""
    config = parse_inactive_config(container_labels, global_config)
    return config['enabled']