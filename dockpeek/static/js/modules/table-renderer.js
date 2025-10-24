import * as CellRenderer from './cell-renderer.js';
import { renderStatus } from './status-renderer.js';
import { updateColumnVisibility, updateFirstAndLastVisibleColumns } from './column-visibility.js';
import { updateTableOrder } from './column-order.js';
import { updateContainerStats } from './container-stats.js';
import { updateInactiveBadge } from './inactive-manager.js';
import { humanizeTimestamp, formatFullTimestamp } from './time-utils.js';


export class TableRenderer {
  constructor(templateId, bodyId) {
    this.template = document.getElementById(templateId);
    this.body = document.getElementById(bodyId);
  }

  render(containers) {
    this.body.innerHTML = '';

    if (!containers.length) {
      this.body.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-gray-500">No containers found matching your criteria.</td></tr>`;
      return;
    }

    const hasAnyTraefikRoutes = window.traefikEnabled !== false &&
      containers.some(c => c.traefik_routes?.length);

    const fragment = document.createDocumentFragment();

    const isInactiveContainer = (container) => container.hasOwnProperty('first_seen') && container.hasOwnProperty('last_seen');
    const regularContainers = containers.filter(container => !isInactiveContainer(container));
    const inactiveContainers = containers.filter(container => isInactiveContainer(container));
    
    for (const container of regularContainers) {
      const row = this._renderRow(container, hasAnyTraefikRoutes);
      fragment.appendChild(row);
    }

    for (const container of inactiveContainers) {
      const row = this._renderRow(container, hasAnyTraefikRoutes, true);
      fragment.appendChild(row);
    }

    this.body.appendChild(fragment);
    updateTableOrder();
    updateColumnVisibility();
    updateFirstAndLastVisibleColumns();
  }

  renderTable(containers) {
    this.render(containers);
    updateContainerStats(containers);
    updateInactiveBadge();
  }

  _renderRow(container, hasAnyTraefikRoutes, isInactive = false) {
    const clone = this.template.content.cloneNode(true);

    if (isInactive) {
      const row = clone.querySelector('tr');
      row.classList.add('inactive-container-row', 'opacity-75');
      row.dataset.containerName = container.name;
      row.dataset.server = container.server;
    }

    const nameCell = clone.querySelector('[data-content="name"]');
    nameCell.classList.add('table-cell-name');
    CellRenderer.renderName(container, nameCell);

    CellRenderer.renderServer(container, clone);

    const stackCell = clone.querySelector('[data-content="stack"]');
    stackCell.classList.add('table-cell-stack');
    CellRenderer.renderStack(container, stackCell);

    const imageCell = clone.querySelector('[data-content="image"]');
    imageCell.classList.add('table-cell-image');
    CellRenderer.renderImage(container, imageCell, clone);

    const imageSizeCell = clone.querySelector('[data-content="image-size"]');
    imageSizeCell.classList.add('table-cell-image-size');
    CellRenderer.renderImageSize(container, imageSizeCell);

    CellRenderer.renderUpdateIndicator(container, clone);

    const tagsCell = clone.querySelector('[data-content="tags"]');
    tagsCell.classList.add('table-cell-tags');
    CellRenderer.renderTags(container, tagsCell);

    const statusCell = clone.querySelector('[data-content="status"]');
    statusCell.classList.add('table-cell-status');
    
    if (isInactive) {
      const humanizedTime = humanizeTimestamp(container.last_seen);
      const fullTimestamp = formatFullTimestamp(container.last_seen);
      
      if (container.inactive_status && container.inactive_color) {
        statusCell.innerHTML = `<span class="status-inactive" style="color: ${container.inactive_color}" data-tooltip="Inactive, Last seen: ${fullTimestamp}">${humanizedTime}</span>`;
        statusCell.className = `py-3 px-4 border-b border-gray-200 table-cell-status status-inactive`;
      } else {
        statusCell.innerHTML = `<span class="status-inactive" data-tooltip="Inactive, Last seen: ${fullTimestamp}">${humanizedTime}</span>`;
        statusCell.className = `py-3 px-4 border-b border-gray-200 table-cell-status status-inactive`;
      }
    } else {
      if (container.status) {
        const { span, className } = renderStatus(container);
        statusCell.className = `py-3 px-4 border-b border-gray-200 table-cell-status ${className}`;
        statusCell.appendChild(span);
      } else {
        statusCell.innerHTML = `<span class="status-unknown">unknown</span>`;
        statusCell.className = `py-3 px-4 border-b border-gray-200 table-cell-status status-unknown`;
      }
    }

    const logsCell = clone.querySelector('[data-content="logs"]');
    logsCell.classList.add('table-cell-logs');
    
    if (isInactive) {
      CellRenderer.renderInactiveDelete(container, logsCell);
    } else {
      CellRenderer.renderLogs(container, logsCell);
    }

    const portsCell = clone.querySelector('[data-content="ports"]');
    portsCell.classList.add('table-cell-ports');
    CellRenderer.renderPorts(container, portsCell);

    const traefikCell = clone.querySelector('[data-content="traefik-routes"]');
    traefikCell.classList.add('table-cell-traefik');
    CellRenderer.renderTraefik(container, traefikCell, hasAnyTraefikRoutes);

    return clone;
  }
}