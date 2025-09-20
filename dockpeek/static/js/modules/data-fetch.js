import { state } from '../app.js';
import { showLoadingIndicator, hideLoadingIndicator, displayError } from './ui-utils.js';
import { updateDisplay, setupServerUI, toggleClearButton, clearSearch } from './filters.js';
import { showConfirmationModal, showUpdatesModal, showNoUpdatesModal, showProgressModal, updateProgressModal, hideProgressModal } from './modals.js';

let originalButtonHTML = '';
document.addEventListener('DOMContentLoaded', () => {
    const checkUpdatesButton = document.getElementById('check-updates-button');
    if (checkUpdatesButton) {
        originalButtonHTML = checkUpdatesButton.innerHTML;
    }
});

export async function fetchContainerData() {
  showLoadingIndicator();
  loadFilterStates();
  try {
    const response = await fetch("/data");
    if (!response.ok) throw createResponseError(response);

    const { servers = [], containers = [], traefik_enabled = true } = await response.json();
    state.allServersData.splice(0, state.allServersData.length, ...servers);
    state.allContainersData.splice(0, state.allContainersData.length, ...containers);
    window.traefikEnabled = traefik_enabled;

    state.isDataLoaded = true;
    document.getElementById('check-updates-button').disabled = false;

    handleServerFilterReset();
    setupServerUI();
    clearSearch();
    toggleClearButton();
    updateDisplay();
  } catch (error) {
    handleFetchError(error);
  } finally {
    hideLoadingIndicator();
  }
}

export function createResponseError(response) {
  const status = response.status;
  const messages = {
    401: `Authorization Error (${status}): Please log in again`,
    500: `Server Error (${status}): Please try again later`,
    default: `HTTP Error: ${status} ${response.statusText}`
  };
  return new Error(messages[status] || messages.default);
}

export function handleServerFilterReset() {
  const shouldReset = !state.allServersData.some(s => s.name === state.currentServerFilter) ||
    (state.allServersData.find(s => s.name === state.currentServerFilter)?.status === 'inactive');
  if (shouldReset) {
    state.currentServerFilter = 'all';
  }
}

export function handleFetchError(error) {
  state.isDataLoaded = false;
  document.getElementById('check-updates-button').disabled = true;
  console.error("Data fetch error:", error);
  const message = error.message.includes('Failed to fetch')
    ? "Network Error: Could not connect to backend service"
    : error.message;
  displayError(message);
}

export async function checkForUpdates() {
  const checkUpdatesButton = document.getElementById('check-updates-button');

  if (state.isCheckingForUpdates) {
      console.log('Cancelling update check...');
      try {
          await fetch("/cancel-updates", { method: "POST" });
          // Reset stanu po anulowaniu
          state.isCheckingForUpdates = false;
          hideProgressModal();
          resetUpdateButton();
      } catch (error) {
          console.error("Failed to send cancellation request to server:", error);
      }
      return;
  }

  if (!state.isDataLoaded) {
    return;
  }
  
  const activeServers = state.allServersData.filter(s => s.status === 'active');
  const serversToCheck = state.currentServerFilter === 'all'
    ? activeServers
    : activeServers.filter(s => s.name === state.currentServerFilter);

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

  // Użyj nowej metody sprawdzania pojedynczych kontenerów
  await checkUpdatesIndividually();
}

async function checkUpdatesIndividually() {
  const checkUpdatesButton = document.getElementById('check-updates-button');
  
  state.isCheckingForUpdates = true;

  // Zmień przycisk na "Cancel"
  checkUpdatesButton.classList.add('loading');
  checkUpdatesButton.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
      </svg>
      Cancel
  `;
  checkUpdatesButton.disabled = false;

  try {
    // Pobierz listę kontenerów do sprawdzenia
    console.log('Fetching containers list...');
    const containersResponse = await fetch("/get-containers-list", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        server_filter: state.currentServerFilter
      })
    });

    if (!containersResponse.ok) {
      throw new Error(`Failed to get containers list: ${containersResponse.status}`);
    }

    const { containers, total } = await containersResponse.json();
    console.log(`Found ${total} containers to check`);

    if (total === 0) {
      showNoUpdatesModal();
      return;
    }

    // Pokaż progress modal
    showProgressModal(total);

    const updates = {};
    const updatedContainers = [];
    let processed = 0;
    let cancelled = false;

    // Sprawdzaj kontenery pojedynczo
    for (const container of containers) {
      // Sprawdź czy anulowano
      if (!state.isCheckingForUpdates) {
        console.log('Update check cancelled by user');
        cancelled = true;
        break;
      }

      console.log(`Checking ${container.key} (${processed + 1}/${total})`);
      
      try {
        const response = await fetch("/check-single-update", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            server_name: container.server_name,
            container_name: container.container_name
          })
        });

        if (!response.ok) {
          console.error(`Failed to check ${container.key}: ${response.status}`);
          updates[container.key] = false;
        } else {
          const result = await response.json();
          
          if (result.cancelled) {
            console.log('Server reported operation was cancelled');
            cancelled = true;
            break;
          }
          
          updates[container.key] = result.update_available;
          console.log(`${container.key}: ${result.update_available ? 'UPDATE AVAILABLE' : 'up to date'}`);
        }
      } catch (error) {
        console.error(`Error checking ${container.key}:`, error);
        updates[container.key] = false;
      }

      processed++;
      
      // Aktualizuj progress
      updateProgressModal(processed, total, container.key);
      
      // Krótkie opóźnienie żeby dać szansę na anulowanie
      await new Promise(resolve => setTimeout(resolve, 50));
    }

    // Aktualizuj dane kontenerów
    state.allContainersData.forEach(container => {
      const key = `${container.server}:${container.name}`;
      if (updates.hasOwnProperty(key)) {
        container.update_available = updates[key];
        if (updates[key]) {
          updatedContainers.push(container);
        }
      }
    });

    updateDisplay();
    hideProgressModal();
    
    if (!cancelled) {
        if (updatedContainers.length > 0) {
          showUpdatesModal(updatedContainers);
        } else {
          showNoUpdatesModal();
        }
    } else {
        console.log("Update check was cancelled");
    }

  } catch (error) {
    console.error("Update check failed:", error);
    hideProgressModal();
    alert("Failed to check for updates. Please try again.");
  } finally {
    resetUpdateButton();
  }
}

function resetUpdateButton() {
  const checkUpdatesButton = document.getElementById('check-updates-button');
  if (originalButtonHTML) {
      checkUpdatesButton.innerHTML = originalButtonHTML;
  }
  checkUpdatesButton.classList.remove('loading');
  checkUpdatesButton.disabled = false;
  state.isCheckingForUpdates = false;
}

// Funkcje dla progress modal - teraz importowane z modals.js
// Usunięto lokalne funkcje showProgressModal, updateProgressModal, hideProgressModal

export function updateExportLink() {
  const exportLink = document.getElementById('export-json-link');
  if (exportLink) {
    const serverParam = state.currentServerFilter === 'all' ? 'all' : encodeURIComponent(state.currentServerFilter);
    exportLink.href = `/export/json?server=${serverParam}`;
  }
}

function loadFilterStates() {
  const savedRunningFilter = localStorage.getItem('filterRunningChecked');
  if (savedRunningFilter !== null) {
    document.getElementById('filter-running-checkbox').checked = JSON.parse(savedRunningFilter);
  }
}