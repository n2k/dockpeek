import { state } from '../app.js';

export function renderTable() {
  const containerRowsBody = document.getElementById("container-rows");
  const rowTemplate = document.getElementById("container-row-template");
  containerRowsBody.innerHTML = "";
  const pageItems = state.filteredAndSortedContainers;

  if (pageItems.length === 0) {
    containerRowsBody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-gray-500">No containers found matching your criteria.</td></tr>`;
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const c of pageItems) {
    const clone = rowTemplate.content.cloneNode(true);

    const nameCell = clone.querySelector('[data-content="name"]');
    nameCell.classList.add('table-cell-name');

    const nameSpan = nameCell.querySelector('[data-content="container-name"]');
    const tagsContainer = nameCell.querySelector('[data-content="tags"]');

    if (c.custom_url) {
      function normalizeUrl(url) {
        if (url.match(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//)) {
          return url;
        }
        return `https://${url}`;
      }

      const url = normalizeUrl(c.custom_url);
      const tooltipUrl = url.replace(/^https:\/\//, '');
      nameSpan.innerHTML = `<a href="${url}" target="_blank" class="text-blue-600 hover:text-blue-800" data-tooltip="${tooltipUrl}">${c.name}</a>`;
    } else {
      nameSpan.textContent = c.name;
    }

    const serverNameSpan = clone.querySelector('[data-content="server-name"]');
    serverNameSpan.closest('td').classList.add('table-cell-server');
    serverNameSpan.textContent = c.server;
    const serverData = state.allContainersData.find(s => s.name === c.server);
    if (serverData && serverData.url) {
      serverNameSpan.setAttribute('data-tooltip', serverData.url);
    }

    const stackCell = clone.querySelector('[data-content="stack"]');
    stackCell.classList.add('table-cell-stack');
    if (c.stack) {
      stackCell.innerHTML = `<a href="#" class="stack-link text-blue-600 hover:text-blue-800 cursor-pointer" data-stack="${c.stack}" data-server="${c.server}">${c.stack}</a>`;
    } else {
      stackCell.textContent = '';
    }

    clone.querySelector('[data-content="image"]').textContent = c.image;
    clone.querySelector('[data-content="image"]').closest('td').classList.add('table-cell-image');

    const sourceLink = clone.querySelector('[data-content="source-link"]');
    if (c.source_url) {
      sourceLink.href = c.source_url;
      sourceLink.classList.remove('hidden');
      sourceLink.setAttribute('data-tooltip', c.source_url);
    } else {
      sourceLink.classList.add('hidden');
    }

    const updateIndicator = clone.querySelector('[data-content="update-indicator"]');
    if (c.update_available) {
      updateIndicator.classList.remove('hidden');
      updateIndicator.setAttribute('data-tooltip', 'Update available');
    } else {
      updateIndicator.classList.add('hidden');
    }

    const tagsCell = clone.querySelector('[data-content="tags"]');
    tagsCell.classList.add('table-cell-tags');
    if (c.tags && c.tags.length > 0) {
      const sortedTags = [...c.tags].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
      tagsCell.innerHTML = `<div class="tags-container">${sortedTags.map(tag =>
        `<span class="tag-badge" data-tag="${tag}">${tag}</span>`
      ).join('')}</div>`;
    } else {
      tagsCell.innerHTML = '';
    }

    const statusCell = clone.querySelector('[data-content="status"]');
    const statusSpan = document.createElement('span');
    statusSpan.textContent = c.status;

    if (c.exit_code !== null && c.exit_code !== undefined) {
      let exitCodeText;
      if (c.exit_code === 0) {
        exitCodeText = 'Exit code: 0 (normal)';
      } else {
        exitCodeText = `Exit code: ${c.exit_code}`;
        if (c.exit_code === 137) exitCodeText += ' (SIGKILL - killed)';
        else if (c.exit_code === 143) exitCodeText += ' (SIGTERM - terminated)';
        else if (c.exit_code === 125) exitCodeText += ' (Docker daemon error)';
        else if (c.exit_code === 126) exitCodeText += ' (Container command not executable)';
        else if (c.exit_code === 127) exitCodeText += ' (Container command not found)';
        else if (c.exit_code === 1) exitCodeText += ' (General application error)';
        else if (c.exit_code === 2) exitCodeText += ' (Misuse of shell command)';
        else if (c.exit_code === 128) exitCodeText += ' (Invalid exit argument)';
        else if (c.exit_code === 130) exitCodeText += ' (SIGINT - interrupted)';
        else if (c.exit_code === 134) exitCodeText += ' (SIGABRT - aborted)';
        else if (c.exit_code === 139) exitCodeText += ' (SIGSEGV - segmentation fault)';
      }
      statusSpan.setAttribute('data-tooltip', exitCodeText);
    } else {
      let tooltipText;
      switch (c.status) {
        case 'running':
          tooltipText = 'Container is running';
          break;
        case 'healthy':
          tooltipText = 'Health check passed';
          break;
        case 'unhealthy':
          tooltipText = 'Health check failed';
          break;
        case 'starting':
          tooltipText = 'Container is starting up';
          break;
        case 'paused':
          tooltipText = 'Container is paused';
          break;
        case 'restarting':
          tooltipText = 'Container is restarting';
          break;
        case 'removing':
          tooltipText = 'Container is being removed';
          break;
        case 'dead':
          tooltipText = 'Container is dead (cannot be restarted)';
          break;
        case 'created':
          tooltipText = 'Container created but not started';
          break;
        default:
          if (c.status.includes('health unknown')) {
            tooltipText = 'Container running, health status unknown';
          } else {
            tooltipText = `Container status: ${c.status}`;
          }
      }
      statusSpan.setAttribute('data-tooltip', tooltipText);
    }

    let statusClass = 'status-unknown';

 // Swarm: running (x/y) should be green if x==y, else default
      const swarmRunningMatch = typeof c.status === 'string' && c.status.match(/^running \((\d+)\/(\d+)\)$/);
      if (swarmRunningMatch) {
        const running = parseInt(swarmRunningMatch[1], 10);
        const desired = parseInt(swarmRunningMatch[2], 10);
        if (running === desired) {
          statusClass = 'status-running';
        } else {
          statusClass = 'status-unhealthy'; // or keep as-is for problem color
        }
      } else {
    switch (c.status) {
      case 'running':
        statusClass = 'status-running';
        break;
      case 'healthy':
        statusClass = 'status-healthy';
        break;
      case 'unhealthy':
        statusClass = 'status-unhealthy';
        break;
      case 'starting':
        statusClass = 'status-starting';
        break;
      case 'exited':
        statusClass = 'status-exited';
        break;
      case 'paused':
        statusClass = 'status-paused';
        break;
      case 'restarting':
        statusClass = 'status-restarting';
        break;
      case 'removing':
        statusClass = 'status-removing';
        break;
      case 'dead':
        statusClass = 'status-dead';
        break;
      case 'created':
        statusClass = 'status-created';
        break;
      default:
        if (c.status.includes('exited')) {
          statusClass = 'status-exited';
        } else if (c.status.includes('health unknown')) {
          statusClass = 'status-running';
        } else {
          statusClass = 'status-unknown';
        }
      }
    }

    statusCell.className = `py-3 px-4 border-b border-gray-200 table-cell-status ${statusClass}`;
    statusCell.innerHTML = '';
    statusCell.appendChild(statusSpan);

    const portsCell = clone.querySelector('[data-content="ports"]');
    portsCell.classList.add('table-cell-ports');
    if (c.ports.length > 0) {
      const arrowSvg =
        `<svg width="12" height="12" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" class="align-middle">
         <path d="M19 12L31 24L19 36" stroke="currentColor" fill="none" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
         </svg>`;

      portsCell.innerHTML = c.ports.map(p => {
        if (p.is_custom || (!p.container_port || p.container_port === '')) {
          return `<div class="custom-port flex items-center mb-1">
            <a href="${p.link}" data-tooltip="${p.link}" target="_blank" class="badge text-bg-dark rounded">${p.host_port}</a>
          </div>`;
        } else {
          return `<div class="flex items-center mb-1">
            <a href="${p.link}" data-tooltip="${p.link}" target="_blank" class="badge text-bg-dark rounded">${p.host_port}</a>
            ${arrowSvg}
            <small class="text-secondary">${p.container_port}</small>
          </div>`;
        }
      }).join('');
    } else {
      portsCell.innerHTML = `<span class="status-none" style="padding-left: 5px;">none</span>`;
    }

    const isTraefikGloballyEnabled = window.traefikEnabled !== false;
    const hasTraefikRoutes = isTraefikGloballyEnabled && pageItems.some(c => c.traefik_routes && c.traefik_routes.length > 0);

    const traefikCell = clone.querySelector('[data-content="traefik-routes"]');
    traefikCell.classList.add('table-cell-traefik');
    if (hasTraefikRoutes) {
      traefikCell.classList.remove('hidden');

      if (c.traefik_routes && c.traefik_routes.length > 0) {
        traefikCell.innerHTML = c.traefik_routes.map(route => {
          const displayUrl = route.url.replace(/^https?:\/\//, '');
          return `<div class="traefik-route mb-1">
            <div class="inline-block">
              <a href="${route.url}" target="_blank" class="text-blue-600 hover:text-blue-800 text-sm">
                <span class="traefik-text">${displayUrl}</span>             
              </a>
            </div>
          </div>`;
        }).join('');
      } else {
        traefikCell.innerHTML = `<span class="status-none text-sm">none</span>`;
      }
    } else {
      traefikCell.classList.add('hidden');
    }
    fragment.appendChild(clone);
  }
  containerRowsBody.appendChild(fragment);
  updateTableColumnOrder();
  updateColumnVisibility();
}

export function updateColumnVisibility() {
  document.querySelectorAll(`[data-sort-column="name"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.name);
  });

  document.querySelectorAll('.server-column').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.server);
  });

  document.querySelectorAll(`[data-sort-column="stack"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.stack);
  });

  document.querySelectorAll(`[data-sort-column="image"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.image);
  });

  document.querySelectorAll(`[data-sort-column="tags"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.tags);
  });

  document.querySelectorAll(`[data-sort-column="status"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.status);
  });

  document.querySelectorAll(`[data-sort-column="ports"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.ports);
  });

  document.querySelectorAll('.traefik-column').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.traefik);
  });

  document.querySelectorAll('.table-cell-name').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.name);
  });

  document.querySelectorAll('.table-cell-server').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.server);
  });

  document.querySelectorAll('.table-cell-stack').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.stack);
  });

  document.querySelectorAll('.table-cell-image').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.image);
  });

  document.querySelectorAll('.table-cell-tags').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.tags);
  });
  document.querySelectorAll('.table-cell-status').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.status);
  });

  document.querySelectorAll('.table-cell-ports').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.ports);
  });

  document.querySelectorAll('.table-cell-traefik').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.traefik);
  });

  const hasTags = state.filteredAndSortedContainers.some(c => c.tags && c.tags.length > 0);
  document.querySelectorAll('.tags-column').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.tags || !hasTags);
  });
  document.querySelectorAll('.table-cell-tags').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.tags || !hasTags);
  });
}

export function initColumnDragAndDrop() {
  const columnList = document.getElementById('column-list');
  let draggedElement = null;
  let touchStartY = 0;
  let touchCurrentY = 0;
  let isDragging = false;

  const savedOrder = localStorage.getItem('columnOrder');
  if (savedOrder) {
    state.columnOrder.splice(0, state.columnOrder.length, ...JSON.parse(savedOrder));
    reorderColumnMenuItems();
  }

  columnList.addEventListener('dragstart', (e) => {
    if (e.target.classList.contains('draggable')) {
      draggedElement = e.target;
      e.target.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/html', e.target.outerHTML);
    }
  });

  columnList.addEventListener('dragend', (e) => {
    if (e.target.classList.contains('draggable')) {
      e.target.classList.remove('dragging');
      draggedElement = null;
    }
  });

  columnList.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';

    const afterElement = getDragAfterElement(columnList, e.clientY);
    const dragging = columnList.querySelector('.dragging');

    columnList.querySelectorAll('.drag-over').forEach(el => {
      el.classList.remove('drag-over');
    });

    if (afterElement == null) {
      columnList.appendChild(dragging);
    } else {
      afterElement.classList.add('drag-over');
      columnList.insertBefore(dragging, afterElement);
    }
  });

  columnList.addEventListener('drop', (e) => {
    e.preventDefault();
    columnList.querySelectorAll('.drag-over').forEach(el => {
      el.classList.remove('drag-over');
    });

    updateColumnOrderFromDOM();
    saveColumnOrder();
    updateTableColumnOrder();
  });

  columnList.addEventListener('touchstart', (e) => {
    const target = e.target.closest('.draggable');
    if (target) {
      draggedElement = target;
      touchStartY = e.touches[0].clientY;
      isDragging = false;

      setTimeout(() => {
        if (draggedElement) {
          isDragging = true;
          draggedElement.classList.add('dragging');
        }
      }, 150);
    }
  }, { passive: false });

  columnList.addEventListener('touchmove', (e) => {
    if (!draggedElement || !isDragging) return;

    e.preventDefault();
    touchCurrentY = e.touches[0].clientY;

    const afterElement = getDragAfterElement(columnList, touchCurrentY);

    columnList.querySelectorAll('.drag-over').forEach(el => {
      el.classList.remove('drag-over');
    });

    if (afterElement == null) {
      columnList.appendChild(draggedElement);
    } else {
      afterElement.classList.add('drag-over');
      columnList.insertBefore(draggedElement, afterElement);
    }
  }, { passive: false });

  columnList.addEventListener('touchend', (e) => {
    if (draggedElement) {
      columnList.querySelectorAll('.drag-over').forEach(el => {
        el.classList.remove('drag-over');
      });

      if (isDragging) {
        draggedElement.classList.remove('dragging');
        updateColumnOrderFromDOM();
        saveColumnOrder();
        updateTableColumnOrder();
      }

      draggedElement = null;
      isDragging = false;
    }
  });

  columnList.querySelectorAll('.draggable').forEach(item => {
    item.draggable = true;
  });
}

export function getDragAfterElement(container, y) {
  const draggableElements = [...container.querySelectorAll('.draggable:not(.dragging)')];

  return draggableElements.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;

    if (offset < 0 && offset > closest.offset) {
      return { offset: offset, element: child };
    } else {
      return closest;
    }
  }, { offset: Number.NEGATIVE_INFINITY }).element;
}

export function updateColumnOrderFromDOM() {
  const items = document.querySelectorAll('#column-list .draggable');
  state.columnOrder.splice(0, state.columnOrder.length, ...Array.from(items).map(item => item.dataset.column));
}

export function reorderColumnMenuItems() {
  const columnList = document.getElementById('column-list');
  const items = Array.from(columnList.children);

  items.sort((a, b) => {
    const aIndex = state.columnOrder.indexOf(a.dataset.column);
    const bIndex = state.columnOrder.indexOf(b.dataset.column);
    return aIndex - bIndex;
  });

  items.forEach(item => columnList.appendChild(item));
}

export function saveColumnOrder() {
  localStorage.setItem('columnOrder', JSON.stringify(state.columnOrder));
}

export function updateTableColumnOrder() {
  const thead = document.querySelector('#main-table thead tr');
  const headers = Array.from(thead.children);

  state.columnOrder.forEach(columnName => {
    const header = headers.find(h =>
      h.dataset.sortColumn === columnName ||
      h.classList.contains(`${columnName}-column`) ||
      h.classList.contains(`table-cell-${columnName}`)
    );
    if (header) {
      thead.appendChild(header);
    }
  });

  document.querySelectorAll('#container-rows tr').forEach(row => {
    const cells = Array.from(row.children);
    state.columnOrder.forEach(columnName => {
      const cell = cells.find(c =>
        c.classList.contains(`table-cell-${columnName}`) ||
        c.dataset.content === columnName ||
        (columnName === 'server' && c.classList.contains('server-column')) ||
        (columnName === 'traefik' && c.classList.contains('traefik-column'))
      );
      if (cell) {
        row.appendChild(cell);
      }
    });
  });
}