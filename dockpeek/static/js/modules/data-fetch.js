import { state } from '../app.js';
import { showLoadingIndicator, hideLoadingIndicator, displayError } from './ui-utils.js';
import { updateDisplay, setupServerUI, toggleClearButton, clearSearch } from './filters.js';
import { showConfirmationModal, showUpdatesModal, showNoUpdatesModal } from './modals.js';

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

  const checkUpdatesButton = document.getElementById('check-updates-button');
  checkUpdatesButton.classList.add('loading');
  checkUpdatesButton.disabled = true;

  try {
    const requestData = {
      server_filter: state.currentServerFilter
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