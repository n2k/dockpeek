import { state } from '../app.js';
import { renderTable } from './table-render.js';

export function setupServerUI() {
  const serverFilterContainer = document.getElementById("server-filter-container");
  const mainTable = document.getElementById("main-table");
  serverFilterContainer.innerHTML = '';
  const servers = [...state.allServersData];

  if (servers.length > 1) {
    mainTable.classList.remove('table-single-server');

    servers.sort((a, b) => {
      if (a.status !== 'inactive' && b.status === 'inactive') return -1;
      if (a.status === 'inactive' && b.status !== 'inactive') return 1;
      if (a.order !== b.order) return a.order - b.order;
      return a.name.localeCompare(b.name);
    });

    const allButton = document.createElement('button');
    allButton.textContent = 'All';
    allButton.dataset.server = 'all';
    allButton.className = 'filter-button';
    serverFilterContainer.appendChild(allButton);

    servers.forEach(server => {
      const button = document.createElement('button');
      button.textContent = server.name;
      button.dataset.server = server.name;
      button.className = 'filter-button';

      if (server.status === 'inactive') {
        button.classList.add('inactive');
        button.disabled = true;
        button.setAttribute('data-tooltip', `${server.url || 'URL unknown'} is offline`);
      } else {
        button.setAttribute('data-tooltip', server.url || 'URL unknown');
      }
      serverFilterContainer.appendChild(button);
    });

    serverFilterContainer.querySelectorAll('.filter-button:not(:disabled)').forEach(button => {
      button.addEventListener('click', () => {
        state.currentServerFilter = button.dataset.server;
        updateDisplay();
      });
    });
  } else {
    mainTable.classList.add('table-single-server');
  }

  updateActiveButton();
}

export function updateActiveButton() {
  const serverFilterContainer = document.getElementById("server-filter-container");
  serverFilterContainer.querySelectorAll('.filter-button').forEach(button => {
    button.classList.toggle('active', button.dataset.server === state.currentServerFilter);
  });
}

export function parseAdvancedSearch(searchTerm) {
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

export function isSwarmMode() {
  // Heuristic: if any container has a status like 'running (x/y)' or 'no-tasks', it's a Swarm service
  return state.allContainersData.some(c => typeof c.status === 'string' && (c.status.match(/^running \(\d+\/\d+\)$/) || c.status === 'no-tasks'));
}
export function updateDisplay() {
  const searchInput = document.getElementById("search-input");
  const filterRunningCheckbox = document.getElementById("filter-running-checkbox");
  const filterUpdatesCheckbox = document.getElementById("filter-updates-checkbox");
  const mainTable = document.getElementById("main-table");

  let workingData = [...state.allContainersData];

  if (state.currentServerFilter !== "all") {
    workingData = workingData.filter(c => c.server === state.currentServerFilter);
  }

  // Swarm mode: repurpose toggle to "Show Problems"
  const swarmMode = isSwarmMode();
  const filterLabel = document.getElementById('filter-running-label');
  if (swarmMode) {
    filterLabel.textContent = 'Show Problems';
    filterLabel.setAttribute('data-tooltip', 'Show only services where not all replicas are running');
    filterRunningCheckbox.parentElement.classList.remove('hidden');
  } else {
    filterLabel.textContent = 'Running only';
    filterLabel.removeAttribute('data-tooltip');
    filterRunningCheckbox.parentElement.classList.remove('hidden');
  }


  if (filterRunningCheckbox.checked) {
    if (swarmMode) {
      // Only show services where running < desired replicas
      workingData = workingData.filter(c => {
        if (typeof c.status === 'string') {
          const m = c.status.match(/^running \((\d+)\/(\d+)\)$/);
          if (m) {
            const running = parseInt(m[1], 10);
            const desired = parseInt(m[2], 10);
            return running < desired;
          }
          // Also show 'no-tasks' as a problem
          if (c.status === 'no-tasks') return true;
        }
        return false;
      });
    } else {
      workingData = workingData.filter(c => c.status === 'running' || c.status === 'healthy');
    }
  }

  if (filterUpdatesCheckbox.checked) {
    workingData = workingData.filter(c => c.update_available);
  }

  const searchTerm = searchInput.value.trim();

  if (searchTerm) {
    const filters = parseAdvancedSearch(searchTerm);

    workingData = workingData.filter(container => {
      if (filters.tags.length > 0) {
        const hasAllTags = filters.tags.every(searchTag =>
          container.tags && container.tags.some(containerTag =>
            containerTag.toLowerCase().includes(searchTag)
          )
        );
        if (!hasAllTags) return false;
      }

      if (filters.ports.length > 0) {
        const hasAllPorts = filters.ports.every(searchPort =>
          container.ports.some(p =>
            p.host_port.includes(searchPort)
          )
        );
        if (!hasAllPorts) return false;
      }

      if (filters.stacks.length > 0) {
        const hasAllStacks = filters.stacks.every(searchStack =>
          container.stack && container.stack.toLowerCase().includes(searchStack)
        );
        if (!hasAllStacks) return false;
      }

      if (filters.general.length > 0) {
        const hasAllGeneral = filters.general.every(searchTerm => {
          return (
            container.name.toLowerCase().includes(searchTerm) ||
            container.image.toLowerCase().includes(searchTerm) ||
            (container.stack && container.stack.toLowerCase().includes(searchTerm)) ||
            container.ports.some(p =>
              p.host_port.includes(searchTerm) ||
              p.container_port.includes(searchTerm)
            )
          );
        });
        if (!hasAllGeneral) return false;
      }

      return true;
    });
  }

  workingData.sort((a, b) => {
    let valA = a[state.currentSortColumn];
    let valB = b[state.currentSortColumn];

    if (state.currentSortColumn === "status") {
      const statusOrder = {
        'starting': 1,
        'restarting': 2,
        'unhealthy': 3,
        'removing': 4,
        'created': 5,
        'paused': 6,
        'exited': 7,
        'dead': 8,
        'running': 9,
        'healthy': 10
      };

      valA = statusOrder[valA] || 99;
      valB = statusOrder[valB] || 99;
    } else if (state.currentSortColumn === "ports") {
      const getFirstPort = (container) => {
        if (container.ports.length === 0) {
          return state.currentSortDirection === "asc" ? Number.MAX_SAFE_INTEGER : -1;
        }
        return parseInt(container.ports[0].host_port, 10);
      };
      valA = getFirstPort(a);
      valB = getFirstPort(b);
    } else if (state.currentSortColumn === "traefik") {
      const getTraefikRoutes = (container) => {
        if (!container.traefik_routes || container.traefik_routes.length === 0) {
          return state.currentSortDirection === "asc" ? "zzz_none" : "";
        }
        return container.traefik_routes[0].url.toLowerCase();
      };
      valA = getTraefikRoutes(a);
      valB = getTraefikRoutes(b);
    } else if (typeof valA === "string" && typeof valB === "string") {
      valA = valA.toLowerCase();
      valB = valB.toLowerCase();
    }

    if (valA < valB) return state.currentSortDirection === "asc" ? -1 : 1;
    if (valA > valB) return state.currentSortDirection === "asc" ? 1 : -1;
    return 0;
  });

  const isTraefikGloballyEnabled = window.traefikEnabled !== false;
  const hasTraefikRoutes = isTraefikGloballyEnabled && workingData.some(c => c.traefik_routes && c.traefik_routes.length > 0);

  const traefikHeaders = document.querySelectorAll('.traefik-column');
  traefikHeaders.forEach(header => {
    if (hasTraefikRoutes) {
      header.classList.remove('hidden');
    } else {
      header.classList.add('hidden');
    }
  });

  const hasTags = workingData.some(c => c.tags && c.tags.length > 0);
  const tagsHeaders = document.querySelectorAll('.tags-column');
  tagsHeaders.forEach(header => {
    if (hasTags) {
      header.classList.remove('hidden');
    } else {
      header.classList.add('hidden');
    }
  });

  document.querySelectorAll('.table-cell-tags').forEach(cell => {
    if (hasTags) {
      cell.classList.remove('hidden');
    } else {
      cell.classList.add('hidden');
    }
  });

  const uniqueServers = [...new Set(workingData.map(c => c.server))];
  const serverHeaders = document.querySelectorAll('.server-column');
  serverHeaders.forEach(header => {
    if (uniqueServers.length <= 1) {
      header.classList.add('hidden');
    } else {
      header.classList.remove('hidden');
    }
  });

  if (uniqueServers.length <= 1) {
    mainTable.classList.add('table-single-server');
  } else {
    mainTable.classList.remove('table-single-server');
  }

  state.filteredAndSortedContainers.splice(0, state.filteredAndSortedContainers.length, ...workingData);
  renderTable();
  updateActiveButton();
}

export function filterByStackAndServer(stack, server) {
  const searchInput = document.getElementById("search-input");
  state.currentServerFilter = server;
  updateActiveButton();
  let stackTerm = stack.includes(" ") ? `"${stack}"` : stack;
  searchInput.value = `stack:${stackTerm}`;
  toggleClearButton();
  updateDisplay();
  searchInput.focus();
}

export function toggleClearButton() {
  const searchInput = document.getElementById("search-input");
  const clearSearchButton = document.getElementById("clear-search-button");
  if (searchInput.value.trim() !== '') {
    clearSearchButton.classList.remove('hidden');
  } else {
    clearSearchButton.classList.add('hidden');
  }
}

export function clearSearch() {
  const searchInput = document.getElementById("search-input");
  const clearSearchButton = document.getElementById("clear-search-button");
  searchInput.value = '';
  clearSearchButton.classList.add('hidden');
  searchInput.focus();
  updateDisplay();
}