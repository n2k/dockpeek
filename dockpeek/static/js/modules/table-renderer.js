import * as CellRenderer from './cell-renderer.js';
import { renderStatus } from './status-renderer.js';
import { updateColumnVisibility, updateFirstAndLastVisibleColumns } from './column-visibility.js';
import { updateTableOrder } from './column-order.js';

export class TableRenderer {
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
    updateTableOrder();
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
    CellRenderer.renderImage(container, imageCell, clone);

    CellRenderer.renderUpdateIndicator(container, clone);

    const tagsCell = clone.querySelector('[data-content="tags"]');
    tagsCell.classList.add('table-cell-tags');
    CellRenderer.renderTags(container, tagsCell);

    const statusCell = clone.querySelector('[data-content="status"]');
    statusCell.classList.add('table-cell-status');
    const { span, className } = renderStatus(container);
    statusCell.className = `py-3 px-4 border-b border-gray-200 table-cell-status ${className}`;
      
    // Create wrapper for status and logs button
    const statusWrapper = document.createElement('div');
    statusWrapper.className = 'flex items-center justify-between gap-2';
      
    // Add logs button
    const logsButton = document.createElement('button');
    logsButton.className = 'logs-button text-gray-500 hover:text-blue-600 p-1 rounded transition-colors';
    logsButton.setAttribute('data-server', container.server);
    logsButton.setAttribute('data-container', container.name);
    logsButton.setAttribute('data-tooltip', 'View logs');
    logsButton.setAttribute('aria-label', 'View container logs');
    logsButton.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
        <polyline points="10 9 9 9 8 9"></polyline>
      </svg>
    `;
    statusWrapper.appendChild(logsButton);
    statusWrapper.appendChild(span);
      
    statusCell.appendChild(statusWrapper);

    const portsCell = clone.querySelector('[data-content="ports"]');
    portsCell.classList.add('table-cell-ports');
    CellRenderer.renderPorts(container, portsCell);

    const traefikCell = clone.querySelector('[data-content="traefik-routes"]');
    traefikCell.classList.add('table-cell-traefik');
    CellRenderer.renderTraefik(container, traefikCell, hasAnyTraefikRoutes);

    return clone;
  }
}