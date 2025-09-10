import { showLoadingIndicator, hideLoadingIndicator, displayError, initCustomTooltips, applyTheme } from './modules/ui-utils.js';
import { renderTable, updateColumnVisibility, initColumnDragAndDrop, updateTableColumnOrder } from './modules/table-render.js';
import { fetchContainerData, checkForUpdates, updateExportLink } from './modules/data-fetch.js';
import { updateDisplay, parseAdvancedSearch, filterByStackAndServer, toggleClearButton, clearSearch, setupServerUI, updateActiveButton } from './modules/filters.js';
import { showUpdatesModal, showNoUpdatesModal, showConfirmationModal } from './modules/modals.js';
import { initEventListeners } from './modules/events.js';

// Centralized state object
const state = {
  allContainersData: [],
  allServersData: [],
  filteredAndSortedContainers: [],
  currentSortColumn: "name",
  currentSortDirection: "asc",
  currentServerFilter: "all",
  isDataLoaded: false,
  columnOrder: ['name', 'stack', 'server', 'ports', 'traefik', 'image', 'tags', 'status'],
  columnVisibility: {
    name: true,
    server: true,
    stack: true,
    image: true,
    tags: true,
    status: true,
    ports: true,
    traefik: true
  }
};

// Export state for use in other modules
export { state };

// Initialize after DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  initCustomTooltips();
  applyTheme(localStorage.getItem("theme") || "dark");
  initColumnDragAndDrop();
  fetchContainerData();
  initEventListeners();
});