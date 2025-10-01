import { state } from '../app.js';

const UPTIME_UNITS = [
  { name: 'year', divisor: 365 * 24 * 60 },
  { name: 'month', divisor: 30 * 24 * 60 },
  { name: 'week', divisor: 7 * 24 * 60 },
  { name: 'day', divisor: 24 * 60 },
  { name: 'hour', divisor: 60 },
  { name: 'minute', divisor: 1 }
];

const STATUS_CLASSES = {
  running: 'status-running',
  healthy: 'status-healthy',
  unhealthy: 'status-unhealthy',
  starting: 'status-starting',
  exited: 'status-exited',
  paused: 'status-paused',
  restarting: 'status-restarting',
  removing: 'status-removing',
  dead: 'status-dead',
  created: 'status-created'
};

const EXIT_CODE_MESSAGES = {
  0: 'normal',
  1: 'General application error',
  2: 'Misuse of shell command',
  125: 'Docker daemon error',
  126: 'Container command not executable',
  127: 'Container command not found',
  128: 'Invalid exit argument',
  130: 'SIGINT - interrupted',
  134: 'SIGABRT - aborted',
  137: 'SIGKILL - killed',
  139: 'SIGSEGV - segmentation fault',
  143: 'SIGTERM - terminated'
};

const COLUMN_MAPPINGS = {
  name: { selector: '[data-sort-column="name"]', cellClass: 'table-cell-name' },
  server: { selector: '.server-column', cellClass: 'table-cell-server' },
  stack: { selector: '[data-sort-column="stack"]', cellClass: 'table-cell-stack' },
  image: { selector: '[data-sort-column="image"]', cellClass: 'table-cell-image' },
  tags: { selector: '[data-sort-column="tags"]', cellClass: 'table-cell-tags' },
  status: { selector: '[data-sort-column="status"]', cellClass: 'table-cell-status' },
  ports: { selector: '[data-sort-column="ports"]', cellClass: 'table-cell-ports' },
  traefik: { selector: '.traefik-column', cellClass: 'table-cell-traefik' }
};


class UptimeCalculator {
  static calculate(startedAt) {
    if (!startedAt) return '';

    const uptimeMinutes = Math.floor((Date.now() - new Date(startedAt)) / (1000 * 60));

    for (const unit of UPTIME_UNITS) {
      const value = Math.floor(uptimeMinutes / unit.divisor);
      if (value > 0) {
        return value === 1 ? `1 ${unit.name}` : `${value} ${unit.name}s`;
      }
    }

    return 'less than 1 minute';
  }
}


class StatusRenderer {
  static render(container) {
    const span = document.createElement('span');
    span.textContent = container.status;

    if (container.exit_code != null) {
      span.setAttribute('data-tooltip', this._getExitCodeTooltip(container.exit_code));
    } else {
      span.setAttribute('data-tooltip', this._getStatusTooltip(container));
    }

    return { span, className: this._getStatusClass(container) };
  }

  static _getExitCodeTooltip(exitCode) {
    const message = EXIT_CODE_MESSAGES[exitCode];
    return message ? `Exit code: ${exitCode} (${message})` : `Exit code: ${exitCode}`;
  }

  static _getStatusTooltip(container) {
    const uptime = UptimeCalculator.calculate(container.started_at);
    const baseMessages = {
      running: 'Container is running',
      healthy: 'Health check passed',
      unhealthy: 'Health check failed',
      starting: 'Container is starting up',
      paused: 'Container is paused',
      restarting: 'Container is restarting',
      removing: 'Container is being removed',
      dead: 'Container is dead (cannot be restarted)',
      created: 'Container created but not started'
    };

    let message = baseMessages[container.status] || `Container status: ${container.status}`;

    if (uptime) {
      if (container.status === 'starting') {
        message += ` (starting for: ${uptime})`;
      } else if (container.status === 'paused') {
        message += ` (was up: ${uptime})`;
      } else if (['running', 'healthy', 'unhealthy'].includes(container.status)) {
        message += ` (up: ${uptime})`;
      }
    }

    return message;
  }

  static _getStatusClass(container) {
    const swarmMatch = container.status?.match(/^running \((\d+)\/(\d+)\)$/);
    if (swarmMatch) {
      const [, running, desired] = swarmMatch.map(Number);
      return running === desired ? STATUS_CLASSES.running : STATUS_CLASSES.unhealthy;
    }

    if (container.status?.includes('exited')) return STATUS_CLASSES.exited;
    if (container.status?.includes('health unknown')) return STATUS_CLASSES.running;

    return STATUS_CLASSES[container.status] || 'status-unknown';
  }
}


class CellRenderer {
  static renderName(container, cell) {
    const nameSpan = cell.querySelector('[data-content="container-name"]');
    
    if (container.custom_url) {
      const url = this._normalizeUrl(container.custom_url);
      const tooltipUrl = url.replace(/^https?:\/\//, '');
      nameSpan.innerHTML = `<a href="${url}" target="_blank" class="text-blue-600 hover:text-blue-800" data-tooltip="${tooltipUrl}">${container.name}</a>`;
    } else {
      nameSpan.textContent = container.name;
    }
  }

  static renderServer(container, clone) {
    const serverCell = clone.querySelector('[data-content="server-name"]').closest('td');
    const serverSpan = serverCell.querySelector('[data-content="server-name"]');
    serverSpan.textContent = container.server;

    const serverData = state.allContainersData.find(s => s.name === container.server);
    if (serverData?.url) {
      serverSpan.setAttribute('data-tooltip', serverData.url);
    }
  }

  static renderStack(container, cell) {
    if (container.stack) {
      cell.innerHTML = `<a href="#" class="stack-link text-blue-600 hover:text-blue-800 cursor-pointer" data-stack="${container.stack}" data-server="${container.server}">${container.stack}</a>`;
    } else {
      cell.textContent = '';
    }
  }

  static renderImage(container, cell) {
    cell.textContent = container.image;

    const sourceLink = cell.nextElementSibling?.querySelector('[data-content="source-link"]');
    if (sourceLink) {
      if (container.source_url) {
        sourceLink.href = container.source_url;
        sourceLink.classList.remove('hidden');
        sourceLink.setAttribute('data-tooltip', container.source_url);
      } else {
        sourceLink.classList.add('hidden');
      }
    }
  }

  static renderUpdateIndicator(container, clone) {
    const indicator = clone.querySelector('[data-content="update-indicator"]');
    
    if (container.update_available) {
      indicator.classList.remove('hidden');
      indicator.classList.add('update-available-indicator');
      indicator.setAttribute('data-server', container.server);
      indicator.setAttribute('data-container', container.name);
      indicator.setAttribute('data-tooltip', `Click to update ${container.name}`);
      indicator.style.cursor = 'pointer';
    } else {
      indicator.classList.add('hidden');
      indicator.classList.remove('update-available-indicator');
      indicator.removeAttribute('data-server');
      indicator.removeAttribute('data-container');
      indicator.removeAttribute('data-tooltip');
      indicator.style.cursor = '';
    }
  }

  static renderTags(container, cell) {
    if (container.tags?.length) {
      const sortedTags = [...container.tags].sort((a, b) => 
        a.toLowerCase().localeCompare(b.toLowerCase())
      );
      cell.innerHTML = `<div class="tags-container">${sortedTags.map(tag =>
        `<span class="tag-badge" data-tag="${tag}">${tag}</span>`
      ).join('')}</div>`;
    } else {
      cell.innerHTML = '';
    }
  }

  static renderPorts(container, cell) {
    if (!container.ports.length) {
      cell.innerHTML = `<span class="status-none" style="padding-left: 5px;">none</span>`;
      return;
    }

    const arrowSvg = `<svg width="12" height="12" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" class="align-middle"><path d="M19 12L31 24L19 36" stroke="currentColor" fill="none" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

    cell.innerHTML = container.ports.map(p => {
      const badge = `<a href="${p.link}" data-tooltip="${p.link}" target="_blank" class="badge text-bg-dark rounded">${p.host_port}</a>`;
      
      if (p.is_custom || !p.container_port) {
        return `<div class="custom-port flex items-center mb-1">${badge}</div>`;
      }
      
      return `<div class="flex items-center mb-1">${badge}${arrowSvg}<small class="text-secondary">${p.container_port}</small></div>`;
    }).join('');
  }

  static renderTraefik(container, cell, hasAnyRoutes) {
    if (!hasAnyRoutes) {
      cell.classList.add('hidden');
      return;
    }

    cell.classList.remove('hidden');

    if (container.traefik_routes?.length) {
      cell.innerHTML = container.traefik_routes.map(route => {
        const displayUrl = route.url.replace(/^https?:\/\//, '');
        return `<div class="traefik-route mb-1"><div class="inline-block"><a href="${route.url}" target="_blank" class="text-blue-600 hover:text-blue-800 text-sm"><span class="traefik-text">${displayUrl}</span></a></div></div>`;
      }).join('');
    } else {
      cell.innerHTML = `<span class="status-none text-sm">none</span>`;
    }
  }

  static _normalizeUrl(url) {
    return url.match(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//) ? url : `https://${url}`;
  }
}


class TableRenderer {
  constructor(templateId, bodyId) {
    this.template = document.getElementById(templateId);
    this.body = document.getElementById(bodyId);
  }

  render(containers) {
    this.body.innerHTML = '';

    if (!containers.length) {
      this.body.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-gray-500">No containers found matching your criteria.</td></tr>`;
      return;
    }

    const hasAnyTraefikRoutes = window.traefikEnabled !== false && 
      containers.some(c => c.traefik_routes?.length);

    const fragment = document.createDocumentFragment();

    for (const container of containers) {
      const row = this._renderRow(container, hasAnyTraefikRoutes);
      fragment.appendChild(row);
    }

    this.body.appendChild(fragment);
    updateTableColumnOrder();
    updateColumnVisibility();
    updateFirstAndLastVisibleColumns();
  }

  _renderRow(container, hasAnyTraefikRoutes) {
    const clone = this.template.content.cloneNode(true);

    const nameCell = clone.querySelector('[data-content="name"]');
    nameCell.classList.add('table-cell-name');
    CellRenderer.renderName(container, nameCell);

    CellRenderer.renderServer(container, clone);

    const stackCell = clone.querySelector('[data-content="stack"]');
    stackCell.classList.add('table-cell-stack');
    CellRenderer.renderStack(container, stackCell);

    const imageCell = clone.querySelector('[data-content="image"]');
    imageCell.classList.add('table-cell-image');
    CellRenderer.renderImage(container, imageCell);

    CellRenderer.renderUpdateIndicator(container, clone);

    const tagsCell = clone.querySelector('[data-content="tags"]');
    tagsCell.classList.add('table-cell-tags');
    CellRenderer.renderTags(container, tagsCell);

    const statusCell = clone.querySelector('[data-content="status"]');
    const { span, className } = StatusRenderer.render(container);
    statusCell.className = `py-3 px-4 border-b border-gray-200 table-cell-status ${className}`;
    statusCell.appendChild(span);

    const portsCell = clone.querySelector('[data-content="ports"]');
    portsCell.classList.add('table-cell-ports');
    CellRenderer.renderPorts(container, portsCell);

    const traefikCell = clone.querySelector('[data-content="traefik-routes"]');
    traefikCell.classList.add('table-cell-traefik');
    CellRenderer.renderTraefik(container, traefikCell, hasAnyTraefikRoutes);

    return clone;
  }
}


class ColumnVisibilityManager {
  static update() {
    for (const [columnName, mapping] of Object.entries(COLUMN_MAPPINGS)) {
      const isVisible = state.columnVisibility[columnName];
      
      document.querySelectorAll(mapping.selector).forEach(el => {
        el.classList.toggle('column-hidden', !isVisible);
      });
      
      document.querySelectorAll(`.${mapping.cellClass}`).forEach(el => {
        el.classList.toggle('column-hidden', !isVisible);
      });
    }

    const hasTags = state.filteredAndSortedContainers.some(c => c.tags?.length);
    document.querySelectorAll('.tags-column, .table-cell-tags').forEach(el => {
      el.classList.toggle('column-hidden', !state.columnVisibility.tags || !hasTags);
    });

    updateFirstAndLastVisibleColumns();
  }
}


class ColumnOrderManager {
  static updateFromDOM() {
    const items = document.querySelectorAll('#column-list .draggable');
    state.columnOrder.splice(0, state.columnOrder.length, 
      ...Array.from(items).map(item => item.dataset.column));
  }

  static reorderMenuItems() {
    const columnList = document.getElementById('column-list');
    const items = Array.from(columnList.children);

    items.sort((a, b) => {
      const aIndex = state.columnOrder.indexOf(a.dataset.column);
      const bIndex = state.columnOrder.indexOf(b.dataset.column);
      return aIndex - bIndex;
    });

    items.forEach(item => columnList.appendChild(item));
  }

  static save() {
    localStorage.setItem('columnOrder', JSON.stringify(state.columnOrder));
  }

  static load() {
    const saved = localStorage.getItem('columnOrder');
    if (saved) {
      state.columnOrder.splice(0, state.columnOrder.length, ...JSON.parse(saved));
    }
  }

  static updateTableOrder() {
    const thead = document.querySelector('#main-table thead tr');
    const headers = Array.from(thead.children);

    state.columnOrder.forEach(columnName => {
      const header = headers.find(h =>
        h.dataset.sortColumn === columnName ||
        h.classList.contains(`${columnName}-column`) ||
        h.classList.contains(`table-cell-${columnName}`)
      );
      if (header) thead.appendChild(header);
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
        if (cell) row.appendChild(cell);
      });
    });

    updateFirstAndLastVisibleColumns();
  }
}


class DragDropHandler {
  constructor(listId) {
    this.list = document.getElementById(listId);
    this.draggedElement = null;
    this.touchStartY = 0;
    this.isDragging = false;
    this._setupEventListeners();
  }

  _setupEventListeners() {
    this.list.addEventListener('dragstart', this._onDragStart.bind(this));
    this.list.addEventListener('dragend', this._onDragEnd.bind(this));
    this.list.addEventListener('dragover', this._onDragOver.bind(this));
    this.list.addEventListener('drop', this._onDrop.bind(this));
    this.list.addEventListener('touchstart', this._onTouchStart.bind(this), { passive: false });
    this.list.addEventListener('touchmove', this._onTouchMove.bind(this), { passive: false });
    this.list.addEventListener('touchend', this._onTouchEnd.bind(this));

    this.list.querySelectorAll('.draggable').forEach(item => {
      item.draggable = true;
    });
  }

  _onDragStart(e) {
    if (e.target.classList.contains('draggable')) {
      this.draggedElement = e.target;
      e.target.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/html', e.target.outerHTML);
    }
  }

  _onDragEnd(e) {
    if (e.target.classList.contains('draggable')) {
      e.target.classList.remove('dragging');
      this.draggedElement = null;
    }
  }

  _onDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';

    const afterElement = this._getDragAfterElement(e.clientY);
    const dragging = this.list.querySelector('.dragging');

    this.list.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));

    if (afterElement == null) {
      this.list.appendChild(dragging);
    } else {
      afterElement.classList.add('drag-over');
      this.list.insertBefore(dragging, afterElement);
    }
  }

  _onDrop(e) {
    e.preventDefault();
    this.list.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
    this._saveOrder();
  }

  _onTouchStart(e) {
    const target = e.target.closest('.draggable');
    if (target) {
      this.draggedElement = target;
      this.touchStartY = e.touches[0].clientY;
      this.isDragging = false;

      setTimeout(() => {
        if (this.draggedElement) {
          this.isDragging = true;
          this.draggedElement.classList.add('dragging');
        }
      }, 150);
    }
  }

  _onTouchMove(e) {
    if (!this.draggedElement || !this.isDragging) return;

    e.preventDefault();
    const touchY = e.touches[0].clientY;
    const afterElement = this._getDragAfterElement(touchY);

    this.list.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));

    if (afterElement == null) {
      this.list.appendChild(this.draggedElement);
    } else {
      afterElement.classList.add('drag-over');
      this.list.insertBefore(this.draggedElement, afterElement);
    }
  }

  _onTouchEnd(e) {
    if (this.draggedElement) {
      this.list.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));

      if (this.isDragging) {
        this.draggedElement.classList.remove('dragging');
        this._saveOrder();
      }

      this.draggedElement = null;
      this.isDragging = false;
    }
  }

  _getDragAfterElement(y) {
    const draggableElements = [...this.list.querySelectorAll('.draggable:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;

      if (offset < 0 && offset > closest.offset) {
        return { offset, element: child };
      }
      return closest;
    }, { offset: Number.NEGATIVE_INFINITY }).element;
  }

  _saveOrder() {
    ColumnOrderManager.updateFromDOM();
    ColumnOrderManager.save();
    ColumnOrderManager.updateTableOrder();
  }
}


let dragDropHandler = null;
const tableRenderer = new TableRenderer('container-row-template', 'container-rows');


export function renderTable() {
  tableRenderer.render(state.filteredAndSortedContainers);
}

export function updateColumnVisibility() {
  ColumnVisibilityManager.update();
}

export function initColumnDragAndDrop() {
  ColumnOrderManager.load();
  ColumnOrderManager.reorderMenuItems();
  
  if (dragDropHandler) {
    dragDropHandler = null;
  }
  dragDropHandler = new DragDropHandler('column-list');
}

export function updateFirstAndLastVisibleColumns() {
  const table = document.querySelector('#main-table');
  const rows = Array.from(table.querySelectorAll('tr'));

  rows.forEach(row => {
    row.querySelectorAll('th, td').forEach(cell => {
      cell.classList.remove('first-visible', 'last-visible');
    });
  });

  if (!rows.length) return;

  const columnsCount = rows[0].children.length;
  let firstIndex = -1;
  let lastIndex = -1;

  for (let i = 0; i < columnsCount; i++) {
    const cell = rows[0].children[i];
    if (cell.offsetParent !== null) {
      if (firstIndex === -1) firstIndex = i;
      lastIndex = i;
    }
  }

  rows.forEach(row => {
    if (firstIndex !== -1) row.children[firstIndex].classList.add('first-visible');
    if (lastIndex !== -1) row.children[lastIndex].classList.add('last-visible');
  });
}

export const updateColumnOrderFromDOM = ColumnOrderManager.updateFromDOM.bind(ColumnOrderManager);
export const reorderColumnMenuItems = ColumnOrderManager.reorderMenuItems.bind(ColumnOrderManager);
export const saveColumnOrder = ColumnOrderManager.save.bind(ColumnOrderManager);
export const updateTableColumnOrder = ColumnOrderManager.updateTableOrder.bind(ColumnOrderManager);
export function getDragAfterElement(container, y) {
  return dragDropHandler?._getDragAfterElement(y);
}