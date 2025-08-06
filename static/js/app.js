document.addEventListener("DOMContentLoaded", () => {
  let allContainersData = [];
  let allServersData = [];
  let filteredAndSortedContainers = [];
  let currentSortColumn = "name";
  let currentSortDirection = "asc";
  let currentServerFilter = "all";
  let isDataLoaded = false;

  const searchInput = document.getElementById("search-input");
  const containerRowsBody = document.getElementById("container-rows");
  const body = document.body;
  const rowTemplate = document.getElementById("container-row-template");
  const serverFilterContainer = document.getElementById("server-filter-container");
  const mainTable = document.getElementById("main-table");
  const refreshButton = document.getElementById('refresh-button');
  const checkUpdatesButton = document.getElementById('check-updates-button');
  checkUpdatesButton.disabled = true;
  const updatesModal = document.getElementById("updates-modal");
  const updatesModalOkBtn = document.getElementById("updates-modal-ok-button");
  const modal = document.getElementById("confirmation-modal");
  const modalConfirmBtn = document.getElementById("modal-confirm-button");
  const modalCancelBtn = document.getElementById("modal-cancel-button");
  const filterUpdatesCheckbox = document.getElementById("filter-updates-checkbox");

  function showLoadingIndicator() {
    refreshButton.classList.add('loading');
    containerRowsBody.innerHTML = `<tr><td colspan="5"><div class="loader"></div></td></tr>`;
  }

  function hideLoadingIndicator() {
    refreshButton.classList.remove('loading');
  }

  function displayError(message) {
    hideLoadingIndicator();
    containerRowsBody.innerHTML = `<tr><td colspan="5" class="text-center py-8 text-red-500">${message}</td></tr>`;
  }

  async function checkForUpdates() {
    if (!isDataLoaded) {
      return;
    }
    const activeServers = allServersData.filter(s => s.status === 'active');
    const serversToCheck = currentServerFilter === 'all'
      ? activeServers
      : activeServers.filter(s => s.name === currentServerFilter);

    if (serversToCheck.length > 1) {
      try {
        await showConfirmationModal(
          'Check Updates on Multiple Servers',
          `You are about to check for updates on ${serversToCheck.length} servers:\n\n${serversToCheck.map(s => `• ${s.name}`).join('\n')}\n\nThis operation may take longer and will pull images from registries. Do you want to continue?`,
          'Check Updates'
        );
      } catch (error) {
        console.log('Multi-server update check cancelled by user');
        return;
      }
    }

    checkUpdatesButton.classList.add('loading');
    checkUpdatesButton.disabled = true;

    try {
      const requestData = {
        server_filter: currentServerFilter
      };

      const response = await fetch("/check-updates", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(requestData)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const { updates } = await response.json();
      const updatedContainers = [];

      allContainersData.forEach(container => {
        const key = `${container.server}:${container.name}`;
        if (updates.hasOwnProperty(key)) {
          container.update_available = updates[key];
          if (updates[key]) {
            updatedContainers.push(container);
          }
        }
      });

      updateDisplay();

      if (updatedContainers.length > 0) {
        showUpdatesModal(updatedContainers);
      } else {
        showNoUpdatesModal();
      }

    } catch (error) {
      console.error("Update check failed:", error);
      alert("Failed to check for updates. Please try again.");
    } finally {
      checkUpdatesButton.classList.remove('loading');
      checkUpdatesButton.disabled = false;
    }
  }

  checkUpdatesButton.addEventListener("click", checkForUpdates);

  function renderTable() {
    containerRowsBody.innerHTML = "";
    const pageItems = filteredAndSortedContainers;

    if (pageItems.length === 0) {
      const colspan = mainTable.classList.contains('table-single-server') ? 4 : 5;
      containerRowsBody.innerHTML = `<tr><td colspan="${colspan}" class="text-center py-8 text-gray-500">No containers found matching your criteria.</td></tr>`;
      return;
    }

    const fragment = document.createDocumentFragment();
    for (const c of pageItems) {
      const clone = rowTemplate.content.cloneNode(true);

      clone.querySelector('[data-content="name"]').textContent = c.name;

      const serverNameSpan = clone.querySelector('[data-content="server-name"]');
      serverNameSpan.textContent = c.server;
      const serverData = allServersData.find(s => s.name === c.server);
      if (serverData && serverData.url) {
        serverNameSpan.setAttribute('data-tooltip', serverData.url);
      }

      clone.querySelector('[data-content="image"]').textContent = c.image;

      const updateIndicator = clone.querySelector('[data-content="update-indicator"]');
      if (c.update_available) {
        updateIndicator.classList.remove('hidden');
        updateIndicator.setAttribute('data-tooltip', 'Update available');
      } else {
        updateIndicator.classList.add('hidden');
      }

      const statusCell = clone.querySelector('[data-content="status"]');
      statusCell.textContent = c.status;
      statusCell.className = `py-3 px-4 border-b border-gray-200 table-cell-status ${c.status === "running" ? "status-running" : "status-exited"}`;

      const portsCell = clone.querySelector('[data-content="ports"]');
      if (c.ports.length > 0) {
        portsCell.innerHTML = c.ports.map(p =>
          `<a href="${p.link}" data-tooltip="${p.link}" target="_blank" class="badge text-bg-dark me-1 rounded">${p.host_port}</a> <small class="text-secondary">→ ${p.container_port}</small>`
        ).join('<br>');
      } else {
        portsCell.innerHTML = `<span class="status-none" style="padding-left: 15px;">none</span>`;
      }
      fragment.appendChild(clone);
    }
    containerRowsBody.appendChild(fragment);
  }

  function setupServerUI() {
    serverFilterContainer.innerHTML = '';
    const servers = [...allServersData];

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
          currentServerFilter = button.dataset.server;
          updateDisplay();
        });
      });
    } else {
      mainTable.classList.add('table-single-server');
    }

    updateActiveButton();
  }

  function updateActiveButton() {
    serverFilterContainer.querySelectorAll('.filter-button').forEach(button => {
      button.classList.toggle('active', button.dataset.server === currentServerFilter);
    });
  }

  function updateDisplay() {
    let workingData = [...allContainersData];

    if (currentServerFilter !== "all") {
      workingData = workingData.filter(c => c.server === currentServerFilter);
    }

    if (filterUpdatesCheckbox.checked) {
      workingData = workingData.filter(c => c.update_available);
    }

    const searchTerm = searchInput.value.toLowerCase().trim();
    if (searchTerm) {
      workingData = workingData.filter(c =>
        c.name.toLowerCase().includes(searchTerm) ||
        c.image.toLowerCase().includes(searchTerm) ||
        c.ports.some(p => p.host_port.includes(searchTerm) || p.container_port.includes(searchTerm))
      );
    }

    workingData.sort((a, b) => {
      let valA = a[currentSortColumn];
      let valB = b[currentSortColumn];

      if (currentSortColumn === "status") {
        const statusOrder = { running: 1, exited: 2 };
        valA = statusOrder[valA] || 0;
        valB = statusOrder[valB] || 0;
      } else if (currentSortColumn === "ports") {
        const getFirstPort = (container) => container.ports.length > 0 ? parseInt(container.ports[0].host_port, 10) : 0;
        valA = getFirstPort(a);
        valB = getFirstPort(b);
      } else if (typeof valA === "string" && typeof valB === "string") {
        valA = valA.toLowerCase();
        valB = valB.toLowerCase();
      }

      if (valA < valB) return currentSortDirection === "asc" ? -1 : 1;
      if (valA > valB) return currentSortDirection === "asc" ? 1 : -1;
      return 0;
    });

    filteredAndSortedContainers = workingData;
    hideLoadingIndicator();
    renderTable();
    updateActiveButton();
  }

  async function fetchContainerData() {
    showLoadingIndicator();
    try {
      const response = await fetch("/data");
      if (!response.ok) throw createResponseError(response);

      const { servers = [], containers = [] } = await response.json();
      [allServersData, allContainersData] = [servers, containers];

      isDataLoaded = true;
      checkUpdatesButton.disabled = false;

      handleServerFilterReset();
      setupServerUI();
      updateDisplay();

    } catch (error) {
      handleFetchError(error);
    } finally {
      hideLoadingIndicator();
    }
  }

  function createResponseError(response) {
    const status = response.status;
    const messages = {
      401: `Authorization Error (${status}): Please log in again`,
      500: `Server Error (${status}): Please try again later`,
      default: `HTTP Error: ${status} ${response.statusText}`
    };
    return new Error(messages[status] || messages.default);
  }

  function handleServerFilterReset() {
    const shouldReset = !allServersData.some(s => s.name === currentServerFilter) ||
      (allServersData.find(s => s.name === currentServerFilter)?.status === 'inactive');
    if (shouldReset) {
      currentServerFilter = 'all';
    }
  }

  function handleFetchError(error) {
    isDataLoaded = false;
    checkUpdatesButton.disabled = true;
    console.error("Data fetch error:", error);
    const message = error.message.includes('Failed to fetch')
      ? "Network Error: Could not connect to backend service"
      : error.message;
    displayError(message);
  }

  function applyTheme(theme) {
    const themeIcon = document.getElementById("theme-icon");
    if (theme === "dark") {
      body.classList.add("dark-mode");
      themeIcon.innerHTML = `<svg fill="currentColor" viewBox="0 0 24 24" stroke="currentColor"><path d="M12 22C17.5228 22 22 17.5228 22 12C22 11.5373 21.3065 11.4608 21.0672 11.8568C19.9289 13.7406 17.8615 15 15.5 15C11.9101 15 9 12.0899 9 8.5C9 6.13845 10.2594 4.07105 12.1432 2.93276C12.5392 2.69347 12.4627 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z"/></svg>`;
    } else {
      body.classList.remove("dark-mode");
      themeIcon.innerHTML = `<svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M12 3V4M12 20V21M4 12H3M6.31412 6.31412L5.5 5.5M17.6859 6.31412L18.5 5.5M6.31412 17.69L5.5 18.5001M17.6859 17.69L18.5 18.5001M21 12H20M16 12C16 14.2091 14.2091 16 12 16C9.79086 16 8 14.2091 8 12C8 9.79086 9.79086 8 12 8C14.2091 8 16 9.79086 16 12Z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    }
    localStorage.setItem("theme", theme);
  }

  function showUpdatesModal(updatedContainers) {
    const updatesList = document.getElementById("updates-list");
    updatesList.innerHTML = "";

    updatedContainers.forEach(container => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${container.name}</strong> <span class="server-name">(${container.server})</span> <span class="image-name">${container.image}</span>`;
      updatesList.appendChild(li);
    });

    updatesModal.classList.remove('hidden');
    const okHandler = () => updatesModal.classList.add('hidden');
    updatesModalOkBtn.addEventListener('click', okHandler, { once: true });
    updatesModal.addEventListener('click', e => e.target === updatesModal && okHandler(), { once: true });
  }

  function showNoUpdatesModal() {
    const updatesList = document.getElementById("updates-list");
    updatesList.innerHTML = "<li class='no-updates-message'>All containers are up to date!</li>";
    updatesModal.classList.remove('hidden');
    const okHandler = () => updatesModal.classList.add('hidden');
    updatesModalOkBtn.addEventListener('click', okHandler, { once: true });
    updatesModal.addEventListener('click', e => e.target === updatesModal && okHandler(), { once: true });
  }

  function showConfirmationModal(title, message, confirmText = 'Confirm') {
    return new Promise((resolve, reject) => {
      document.getElementById('modal-title').textContent = title;
      document.getElementById('modal-message').innerHTML = message.replace(/\n/g, '<br>');
      modalConfirmBtn.textContent = confirmText;
      modal.classList.remove('hidden');

      const confirmHandler = () => {
        modal.classList.add('hidden');
        removeListeners();
        resolve();
      };

      const cancelHandler = () => {
        modal.classList.add('hidden');
        removeListeners();
        reject(new Error('User cancelled'));
      };

      const backdropHandler = (e) => {
        if (e.target === modal) {
          cancelHandler();
        }
      };

      const removeListeners = () => {
        modalConfirmBtn.removeEventListener('click', confirmHandler);
        modalCancelBtn.removeEventListener('click', cancelHandler);
        modal.removeEventListener('click', backdropHandler);
      };

      modalConfirmBtn.addEventListener('click', confirmHandler);
      modalCancelBtn.addEventListener('click', cancelHandler);
      modal.addEventListener('click', backdropHandler);
    });
  }

  fetchContainerData();
  applyTheme(localStorage.getItem("theme") || "dark");

  refreshButton.addEventListener("click", fetchContainerData);
  document.getElementById("theme-switcher").addEventListener("click", () => {
    applyTheme(body.classList.contains("dark-mode") ? "light" : "dark");
  });

  filterUpdatesCheckbox.addEventListener("change", updateDisplay);
  searchInput.addEventListener("input", updateDisplay);

  document.querySelectorAll(".sortable-header").forEach((header) => {
    header.addEventListener("click", () => {
      const column = header.dataset.sortColumn;
      if (column === currentSortColumn) {
        currentSortDirection = currentSortDirection === "asc" ? "desc" : "asc";
      } else {
        currentSortColumn = column;
        currentSortDirection = "asc";
      }
      document.querySelectorAll(".sortable-header").forEach(h => h.classList.remove('asc', 'desc'));
      header.classList.add(currentSortDirection);
      updateDisplay();
    });
  });
});