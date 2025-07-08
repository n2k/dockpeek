document.addEventListener("DOMContentLoaded", () => {
  // --- STATE MANAGEMENT ---
  let allContainersData = []; // Raw data from the server
  let filteredAndSortedContainers = []; // Data after filtering and sorting
  let currentSortColumn = "name";
  let currentSortDirection = "asc";
  let currentServerFilter = "all";

  // --- DOM ELEMENT SELECTORS ---
  const searchInput = document.getElementById("search-input");
  const containerRowsBody = document.getElementById("container-rows");
  const body = document.body;
  const rowTemplate = document.getElementById("container-row-template");
  const serverFilterContainer = document.getElementById("server-filter-container");
  const mainTable = document.getElementById("main-table");
  const refreshButton = document.getElementById('refresh-button');

  /**
   * Shows a loading indicator in the table body.
   */
  function showLoadingIndicator() {
    refreshButton.classList.add('loading');
    containerRowsBody.innerHTML = `<tr><td colspan="5"><div class="loader"></div></td></tr>`;
  }
  
  /**
   * Hides loading indicators.
   */
  function hideLoadingIndicator() {
    refreshButton.classList.remove('loading');
  }

  /**
   * Displays an error message in the table body.
   * @param {string} message - The error message to display.
   */
  function displayError(message) {
    hideLoadingIndicator();
    containerRowsBody.innerHTML = `<tr><td colspan="5" class="text-center py-8 text-red-500">${message}</td></tr>`;
  }

  /**
   * Renders the container table using the HTML template.
   */
  function renderTable() {
    containerRowsBody.innerHTML = "";

    const pageItems = filteredAndSortedContainers;

    if (pageItems.length === 0) {
      const colspan = mainTable.classList.contains('table-single-server') ? 4 : 5;
      if (searchInput.value || currentServerFilter !== 'all') {
        containerRowsBody.innerHTML = `<tr><td colspan="${colspan}" class="text-center py-8 text-gray-500">No containers found matching your criteria.</td></tr>`;
      } else {
        containerRowsBody.innerHTML = `<tr><td colspan="${colspan}" class="text-center py-8 text-gray-500">No containers to display.</td></tr>`;
      }
      return;
    }

    const fragment = document.createDocumentFragment();
    for (const c of pageItems) {
      const clone = rowTemplate.content.cloneNode(true);

      clone.querySelector('[data-content="name"]').textContent = c.name;
      clone.querySelector('[data-content="server"]').textContent = c.server;
      clone.querySelector('[data-content="image"]').textContent = c.image;

      const statusCell = clone.querySelector('[data-content="status"]');
      statusCell.textContent = c.status;
      statusCell.className = `py-3 px-4 border-b border-gray-200 table-cell-status ${c.status === "running" ? "status-running" : "status-exited"}`;

      const portsCell = clone.querySelector('[data-content="ports"]');
      if (c.ports.length > 0) {
        portsCell.innerHTML = c.ports.map(p =>
          `<a href="${p.link}" target="_blank" class="badge text-bg-dark me-1 rounded">${p.host_port}</a> <small class="text-secondary">→ ${p.container_port}</small>`
        ).join('<br>');
      } else {
        portsCell.innerHTML = `<span class="status-none" style="padding-left: 15px;">none</span>`;
      }
      fragment.appendChild(clone);
    }
    containerRowsBody.appendChild(fragment);
  }
  
  /**
   * Renders server filter buttons and manages server column visibility.
   */
  function setupServerUI() {
    serverFilterContainer.innerHTML = '';
    const serverNames = [...new Set(allContainersData.map(c => c.server))];
    
    if (serverNames.length > 1) {
        mainTable.classList.remove('table-single-server');

        const allButton = document.createElement('button');
        allButton.textContent = 'All';
        allButton.dataset.server = 'all';
        allButton.className = 'filter-button';
        serverFilterContainer.appendChild(allButton);

        serverNames.forEach(name => {
            const button = document.createElement('button');
            button.textContent = name;
            button.dataset.server = name;
            button.className = 'filter-button';
            serverFilterContainer.appendChild(button);
        });

        serverFilterContainer.querySelectorAll('.filter-button').forEach(button => {
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
  
  /**
   * Updates the visual state of the active filter button.
   */
  function updateActiveButton() {
      serverFilterContainer.querySelectorAll('.filter-button').forEach(button => {
          if (button.dataset.server === currentServerFilter) {
              button.classList.add('active');
          } else {
              button.classList.remove('active');
          }
      });
  }

  /**
   * Sorts and filters the container list, then triggers a re-render.
   */
  function updateDisplay() {
    let workingData = [...allContainersData];

    if (currentServerFilter !== "all") {
        workingData = workingData.filter(c => c.server === currentServerFilter);
    }

    const searchTerm = searchInput.value.toLowerCase().trim();
    if (searchTerm) {
        workingData = workingData.filter(c =>
          c.name.toLowerCase().includes(searchTerm) ||
          c.image.toLowerCase().includes(searchTerm) ||
          c.ports.some(p => p.host_port.includes(searchTerm))
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

  /**
   * Fetches container data from the backend with improved error handling.
   */
  async function fetchContainerData() {
    showLoadingIndicator();
    try {
      const response = await fetch("/data");
      if (!response.ok) {
        let errorMsg;
        switch (response.status) {
          case 401:
          case 403:
            errorMsg = `Authorization Error (${response.status}): You might need to log in again.`;
            break;
          case 500:
            errorMsg = `Server Error (${response.status}): The server encountered an issue. Please try again later.`;
            break;
          default:
            errorMsg = `HTTP Error: ${response.status} ${response.statusText}`;
        }
        throw new Error(errorMsg);
      }
      allContainersData = await response.json();
      setupServerUI();
      updateDisplay();
    } catch (error) {
      console.error("Error fetching container data:", error);
      const finalMessage = error.message.includes('Failed to fetch')
        ? `Network Error: Could not connect to the backend. Is it running?`
        : error.message;
      displayError(finalMessage);
    }
  }

      // --- THEME SWITCHER LOGIC ---
      function applyTheme(theme) {
        const themeIcon = document.getElementById("theme-icon");
        if (theme === "dark") {
          body.classList.add("dark-mode");
          themeIcon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 0111.21 3 7 7 0 0012 21c4.97 0 9-4.03 9-9 0-.07 0-.14-.01-.21z" /></svg>`;
        } else {
          body.classList.remove("dark-mode");
          themeIcon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="4" /><line x1="12" y1="2" x2="12" y2="4" /><line x1="12" y1="20" x2="12" y2="22" /><line x1="5" y1="5" x2="6.5" y2="6.5" /><line x1="17.5" y1="17.5" x2="19" y2="19" /><line x1="2" y1="12" x2="4" y2="12" /><line x1="20" y1="12" x2="22" y2="12" /><line x1="5" y1="19" x2="6.5" y2="17.5" /><line x1="17.5" y1="6.5" x2="19" y2="5" /></svg>`;
        }
        localStorage.setItem("theme", theme);
      }

      // --- MODAL LOGIC ---
      const modal = document.getElementById("confirmation-modal");
      const modalConfirmBtn = document.getElementById("modal-confirm-button");
      const modalCancelBtn = document.getElementById("modal-cancel-button");

      /**
       * Displays a confirmation modal and returns a Promise that resolves or rejects based on user action.
       * @param {string} title - The title for the modal.
       * @param {string} message - The confirmation message.
       * @param {string} confirmText - The text for the confirm button.
       */
      function showConfirmationModal(title, message, confirmText = 'Confirm') {
        return new Promise((resolve, reject) => {
          document.getElementById('modal-title').textContent = title;
          document.getElementById('modal-message').textContent = message;
          modalConfirmBtn.textContent = confirmText;
          modal.classList.remove('hidden');

          const confirmHandler = () => {
            modal.classList.add('hidden');
            cleanup();
            resolve();
          };

          const cancelHandler = () => {
            modal.classList.add('hidden');
            cleanup();
            reject();
          };

          const backdropClickHandler = (e) => {
            if (e.target === modal) {
              cancelHandler();
            }
          };

          const cleanup = () => {
            modalConfirmBtn.removeEventListener('click', confirmHandler);
            modalCancelBtn.removeEventListener('click', cancelHandler);
            modal.removeEventListener('click', backdropClickHandler);
          };

          modalConfirmBtn.addEventListener('click', confirmHandler, { once: true });
          modalCancelBtn.addEventListener('click', cancelHandler, { once: true });
          modal.addEventListener('click', backdropClickHandler, { once: true });
        });
      }



      // --- INITIALIZATION & EVENT LISTENERS ---

      // Initial data fetch
      fetchContainerData();

      // Apply saved theme
      applyTheme(localStorage.getItem("theme") || "dark");

      // Refresh button
      refreshButton.addEventListener("click", fetchContainerData);

      // Theme switcher
      document.getElementById("theme-switcher").addEventListener("click", () => {
        applyTheme(body.classList.contains("dark-mode") ? "light" : "dark");
      });

      // Search input
      searchInput.addEventListener("input", updateDisplay);

      // Sorting headers
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

      // Export to JSON button
      document.getElementById("export-json-button").addEventListener("click", async () => {
        if (filteredAndSortedContainers.length === 0) {
          alert("No data to export.");
          return;
        }

        try {
          await showConfirmationModal('Export to JSON', 'Are you sure you want to download the currently displayed container data as a JSON file?', 'Download');
          const jsonContent = JSON.stringify(filteredAndSortedContainers, null, 2);
          const blob = new Blob([jsonContent], { type: "application/json" });
          const link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = "dockpeek_containers.json";
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } catch {
          console.log('Export cancelled by user.');
        }
      });
    });