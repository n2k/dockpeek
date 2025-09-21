import { fetchContainerData, checkForUpdates, updateExportLink, installUpdate } from './data-fetch.js';
import { updateDisplay, clearSearch, filterByStackAndServer } from './filters.js';
import { applyTheme } from './ui-utils.js';
import { state } from '../app.js';
import { updateColumnVisibility, updateTableColumnOrder, reorderColumnMenuItems, saveColumnOrder } from './table-render.js';

export function initEventListeners() {
  const refreshButton = document.getElementById('refresh-button');
  const checkUpdatesButton = document.getElementById('check-updates-button');
  const filterUpdatesCheckbox = document.getElementById("filter-updates-checkbox");
  const filterRunningCheckbox = document.getElementById("filter-running-checkbox");
  const searchInput = document.getElementById("search-input");
  const clearSearchButton = document.getElementById("clear-search-button");
  const columnMenuButton = document.getElementById('column-menu-button');
  const columnMenu = document.getElementById('column-menu');
  const resetColumnsButton = document.getElementById('reset-columns-button');
  const containerRowsBody = document.getElementById("container-rows");

  refreshButton.addEventListener("click", fetchContainerData);
  checkUpdatesButton.addEventListener("click", checkForUpdates);

  document.getElementById("theme-switcher").addEventListener("click", () => {
    applyTheme(document.body.classList.contains("dark-mode") ? "light" : "dark");
  });

  filterUpdatesCheckbox.addEventListener("change", updateDisplay);

  filterRunningCheckbox.addEventListener("change", () => {
    localStorage.setItem('filterRunningChecked', JSON.stringify(filterRunningCheckbox.checked));
    updateDisplay();
  });

  searchInput.addEventListener("input", function () {
    toggleClearButton();
    updateDisplay();
  });

  clearSearchButton.addEventListener('click', clearSearch);

  searchInput.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      clearSearch();
    }
  });

  document.querySelectorAll(".sortable-header").forEach((header) => {
    header.addEventListener("click", () => {
      const column = header.dataset.sortColumn;
      if (column === state.currentSortColumn) {
        state.currentSortDirection = state.currentSortDirection === "asc" ? "desc" : "asc";
      } else {
        state.currentSortColumn = column;
        state.currentSortDirection = "asc";
      }
      document.querySelectorAll(".sortable-header").forEach(h => h.classList.remove('asc', 'desc'));
      header.classList.add(state.currentSortDirection);
      updateDisplay();
    });
  });

  document.querySelector('.logo-title').addEventListener('click', () => {
    filterUpdatesCheckbox.checked = false;
    clearSearch();
    updateDisplay();
  });

  containerRowsBody.addEventListener('click', function (e) {
    // Obsługa kliknięcia na wskaźnik aktualizacji
    if (e.target.classList.contains('update-available-indicator') || e.target.closest('.update-available-indicator')) {
      e.preventDefault();
      e.stopPropagation();
      
      const indicator = e.target.classList.contains('update-available-indicator') ? e.target : e.target.closest('.update-available-indicator');
      const serverName = indicator.dataset.server;
      const containerName = indicator.dataset.container;
      
      if (serverName && containerName) {
        console.log(`Initiating update for ${containerName} on ${serverName}`);
        installUpdate(serverName, containerName);
      } else {
        console.error('Missing server or container name in update indicator');
      }
      return;
    }

    if (e.target.classList.contains('tag-badge')) {
      e.preventDefault();
      const tag = e.target.dataset.tag;
      const tagSearch = `#${tag}`;

      let currentSearch = searchInput.value.trim();
      const filters = parseAdvancedSearch(currentSearch);

      const tagAlreadyExists = filters.tags.some(existingTag =>
        existingTag.toLowerCase() === tag.toLowerCase()
      );

      if (!tagAlreadyExists) {
        if (currentSearch) {
          searchInput.value = `${currentSearch} ${tagSearch}`;
        } else {
          searchInput.value = tagSearch;
        }

        toggleClearButton();
        updateDisplay();
        searchInput.focus();
      }
    }

    if (e.target.classList.contains('stack-link')) {
      e.preventDefault();
      e.stopPropagation();
      const stack = e.target.dataset.stack;
      const server = e.target.dataset.server;
      filterByStackAndServer(stack, server);
    }
  });

  if (resetColumnsButton) {
    resetColumnsButton.addEventListener('click', (e) => {
      e.stopPropagation();
      console.log('Resetting all columns to visible');
      Object.keys(state.columnVisibility).forEach(column => {
        state.columnVisibility[column] = true;
        const toggle = document.getElementById(`toggle-${column}`);
        if (toggle) {
          toggle.checked = true;
        }
      });

      state.columnOrder.splice(0, state.columnOrder.length, 'name', 'stack', 'server', 'ports', 'traefik', 'image', 'tags', 'status');
      reorderColumnMenuItems();
      saveColumnOrder();
      updateTableColumnOrder();
      localStorage.setItem('columnVisibility', JSON.stringify(state.columnVisibility));
      updateColumnVisibility();
      console.log('Columns reset complete:', state.columnVisibility);
    });
  }

  const savedVisibility = localStorage.getItem('columnVisibility');
  if (savedVisibility) {
    Object.assign(state.columnVisibility, JSON.parse(savedVisibility));
  }

  Object.keys(state.columnVisibility).forEach(column => {
    const toggle = document.getElementById(`toggle-${column}`);
    if (toggle) {
      toggle.checked = state.columnVisibility[column];
      toggle.addEventListener('change', () => {
        state.columnVisibility[column] = toggle.checked;
        localStorage.setItem('columnVisibility', JSON.stringify(state.columnVisibility));
        updateColumnVisibility();
      });
    }
  });

  columnMenuButton.addEventListener('click', (e) => {
    e.stopPropagation();
    columnMenu.classList.toggle('hidden');
  });

  document.addEventListener('click', () => {
    columnMenu.classList.add('hidden');
  });

  columnMenu.addEventListener('click', (e) => {
    e.stopPropagation();
  });

  updateExportLink();
}

function toggleClearButton() {
  const searchInput = document.getElementById("search-input");
  const clearSearchButton = document.getElementById("clear-search-button");
  if (searchInput.value.trim() !== '') {
    clearSearchButton.classList.remove('hidden');
  } else {
    clearSearchButton.classList.add('hidden');
  }
}

function parseAdvancedSearch(searchTerm) {
  const filters = {
    tags: [],
    ports: [],
    stacks: [],
    general: []
  };

  const terms = searchTerm.match(/(?:[^\s"]+|"[^"]*")+/g) || [];

  terms.forEach(term => {
    term = term.trim();
    if (!term) return;

    if (term.startsWith('#')) {
      filters.tags.push(term.substring(1).toLowerCase());
    } else if (term.startsWith(':')) {
      filters.ports.push(term.substring(1));
    } else if (term.startsWith('stack:')) {
      let stackValue = term.substring(6);
      if (stackValue.startsWith('"') && stackValue.endsWith('"')) {
        stackValue = stackValue.slice(1, -1);
      }
      filters.stacks.push(stackValue.toLowerCase());
    } else {
      if (term.startsWith('"') && term.endsWith('"')) {
        term = term.slice(1, -1);
      }
      filters.general.push(term.toLowerCase());
    }
  });

  return filters;
}