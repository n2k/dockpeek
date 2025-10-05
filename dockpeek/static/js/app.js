import { state } from './modules/state.js';
import { showLoadingIndicator, hideLoadingIndicator, displayError, initCustomTooltips, initTheme } from './modules/ui-utils.js';
import { TableRenderer } from './modules/table-renderer.js';
import { DragDropHandler } from './modules/drag-drop.js';
import * as ColumnOrder from './modules/column-order.js';
import { updateColumnVisibility } from './modules/column-visibility.js';
import { fetchContainerData, checkForUpdates, updateExportLink } from './modules/data-fetch.js';
import { updateDisplay, parseAdvancedSearch, filterByStackAndServer, toggleClearButton, clearSearch, setupServerUI, updateActiveButton } from './modules/filters.js';
import { showUpdatesModal, showNoUpdatesModal, showConfirmationModal } from './modules/modals.js';
import { initEventListeners } from './modules/events.js';
import { updateSwarmIndicator, initSwarmIndicator, isSwarmMode } from './modules/swarm-indicator.js';
import { updateContainerStats } from './modules/container-stats.js';
import { logsViewer } from './modules/logs-viewer.js';

const tableRenderer = new TableRenderer('container-row-template', 'container-rows');
let dragDropHandler = null;

export function renderTable() {
  tableRenderer.render(state.filteredAndSortedContainers);
  updateContainerStats(state.filteredAndSortedContainers);
}


export function initLogsButtons() {
  document.addEventListener('click', (e) => {
    const logsButton = e.target.closest('.logs-button');
    if (logsButton) {
      e.preventDefault();
      const serverName = logsButton.dataset.server;
      const containerName = logsButton.dataset.container;
      
      if (serverName && containerName) {
        logsViewer.open(serverName, containerName);
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initCustomTooltips();
  initTheme();
  
  ColumnOrder.load();
  ColumnOrder.reorderMenuItems();
  dragDropHandler = new DragDropHandler('column-list');
  
  initSwarmIndicator();
  fetchContainerData();
  initEventListeners();
  initLogsButtons();
});