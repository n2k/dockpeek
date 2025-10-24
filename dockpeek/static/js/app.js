import { initCustomTooltips, initTheme } from './modules/ui-utils.js';
import { TableRenderer } from './modules/table-renderer.js';
import { DragDropHandler } from './modules/drag-drop.js';
import * as ColumnOrder from './modules/column-order.js';
import { fetchContainerData } from './modules/data-fetch.js';
import { initEventListeners, initLogsButtons } from './modules/events.js';
import { initSwarmIndicator } from './modules/swarm-indicator.js';
import { initTableRenderer } from './modules/render-utils.js';
import { stopLastSeenTimer } from './modules/last-seen-timer.js';

const tableRenderer = new TableRenderer('container-row-template', 'container-rows');
let dragDropHandler = null;

initTableRenderer(tableRenderer);

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
  
  window.addEventListener('beforeunload', () => {
    stopLastSeenTimer();
  });
});