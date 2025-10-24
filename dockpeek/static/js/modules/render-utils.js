import { state } from './state.js';

let tableRenderer = null;

export function initTableRenderer(renderer) {
  tableRenderer = renderer;
}

export function renderTable() {
  if (!tableRenderer) {
    console.error('TableRenderer not initialized. Call initTableRenderer() first.');
    return;
  }
  tableRenderer.renderTable(state.filteredAndSortedContainers);
}