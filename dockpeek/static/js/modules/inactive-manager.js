import { state } from './state.js';
import { fetchContainerData } from './data-fetch.js';
import { showConfirmationModal } from './modals.js';
import { apiUrl } from './config.js';

export async function handleDeleteInactiveContainer(server, containerName) {
  try {
    await showConfirmationModal(
      'Delete Inactive Container',
      `Are you sure you want to delete the inactive container "${containerName}" from server "${server}"?\nThis will remove it from the inactive containers list.`
    );

    const response = await fetch(apiUrl(`/inactive-containers/${encodeURIComponent(server)}/${encodeURIComponent(containerName)}`), {
      method: 'DELETE'
    });

    if (response.ok) {
      await fetchContainerData();
    } else {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      console.error('Failed to delete inactive container:', error.message || 'Unknown error');
      throw new Error(error.message || 'Failed to delete inactive container');
    }
  } catch (error) {
    // If it's a user cancellation, don't log as an error
    if (error.message === 'User cancelled') {
      return;
    }
    console.error('Error deleting inactive container:', error);
  }
}

export async function handleClearInactiveContainers() {
  try {
    const inactiveContainers = state.inactiveContainers;
    
    if (inactiveContainers.length === 0) {
      console.warn('No inactive containers to clear.');
      return;
    }

    await showConfirmationModal(
      'Clear Inactive Containers',
      `Are you sure you want to clear all ${inactiveContainers.length} inactive containers?\nThis will remove them from the inactive containers list.`
    );

    const response = await fetch(apiUrl('/inactive-containers/clear'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inactive_only: true })
    });

    if (response.ok) {
      await fetchContainerData();
    } else {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      console.error('Failed to clear inactive containers:', error.message || 'Unknown error');
      throw new Error(error.message || 'Failed to clear inactive containers');
    }
  } catch (error) {
    // If it's a user cancellation, don't log as an error
    if (error.message === 'User cancelled') {
      return;
    }
    console.error('Error clearing inactive containers:', error);
  }
}

export function updateInactiveBadge() {
  const badge = document.getElementById('inactive-badge');
  const clearInactiveButton = document.getElementById('clear-inactive-button');
  const inactiveCount = state.inactiveContainers.length;
  
  if (badge) {
    if (inactiveCount > 0) {
      badge.textContent = inactiveCount;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  }
  
  if (clearInactiveButton) {
    if (inactiveCount > 0) {
      clearInactiveButton.classList.remove('hidden');
    } else {
      clearInactiveButton.classList.add('hidden');
    }
  }
}