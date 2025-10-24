import { humanizeTimestamp, formatFullTimestamp } from './time-utils.js';
import { state } from './state.js';

let lastSeenTimer = null;

export function startLastSeenTimer() {
    stopLastSeenTimer();
    
    if (state.inactiveContainers && state.inactiveContainers.length > 0) {
        lastSeenTimer = setTimeout(() => {
            updateLastSeenDisplay();
            startLastSeenTimer();
        }, 60000);
    }
}

export function stopLastSeenTimer() {
    if (lastSeenTimer) {
        clearTimeout(lastSeenTimer);
        lastSeenTimer = null;
    }
}

function updateLastSeenDisplay() {
    const inactiveRows = document.querySelectorAll('.inactive-container-row');
    
    inactiveRows.forEach(row => {
        const statusCell = row.querySelector('[data-content="status"]');
        if (statusCell) {
            const containerName = row.dataset.containerName;
            const server = row.dataset.server;
            
            if (containerName && server) {
                const container = state.inactiveContainers.find(c => 
                    c.name === containerName && c.server === server
                );
                
                if (container && container.last_seen) {
                    const humanizedTime = humanizeTimestamp(container.last_seen);
                    const fullTimestamp = formatFullTimestamp(container.last_seen);
                    
                    const statusSpan = statusCell.querySelector('.status-inactive');
                    if (statusSpan) {
                        statusSpan.textContent = humanizedTime;
                        statusSpan.setAttribute('data-tooltip', `Inactive, Last seen: ${fullTimestamp}`);
                    }
                }
            }
        }
    });
}