import { updateDisplay } from './filters.js';

export function showUpdatesModal(updatedContainers) {
  const updatesList = document.getElementById("updates-list");
  const updatesModal = document.getElementById("updates-modal");
  const updatesModalOkBtn = document.getElementById("updates-modal-ok-button");
  updatesList.innerHTML = "";

  updatedContainers.forEach(container => {
    const li = document.createElement("li");
    li.innerHTML = `<strong class="container-name">${container.name}</strong> <span class="stack-name">[${container.stack}]</span> <span class="server-name">(${container.server})</span> <span class="image-name">${container.image}</span>`;
    updatesList.appendChild(li);
  });

  updatesModal.classList.remove('hidden');

  const okHandler = () => {
    updatesModal.classList.add('hidden');
    updateDisplay();
  };

  updatesModalOkBtn.addEventListener('click', okHandler, { once: true });
  updatesModal.addEventListener('click', e => e.target === updatesModal && okHandler(), { once: true });
}

export function showNoUpdatesModal() {
  const updatesModal = document.getElementById("updates-modal");
  const updatesModalTitle = document.getElementById("updates-modal-title");
  const updatesList = document.getElementById("updates-list");
  const updatesModalOkBtn = document.getElementById("updates-modal-ok-button");

  updatesModalTitle.textContent = "No Updates Available";
  updatesList.innerHTML = "<li class='no-updates-message'>All containers are up to date!</li>";
  updatesModal.classList.remove('hidden');

  const okHandler = () => {
    updatesModal.classList.add('hidden');
    updatesModalTitle.textContent = "Updates Found";
  };

  updatesModalOkBtn.addEventListener('click', okHandler, { once: true });
  updatesModal.addEventListener('click', e => e.target === updatesModal && okHandler(), { once: true });
}

export function showConfirmationModal(title, message, confirmText = 'Confirm') {
  return new Promise((resolve, reject) => {
    const modal = document.getElementById("confirmation-modal");
    const modalConfirmBtn = document.getElementById("modal-confirm-button");
    const modalCancelBtn = document.getElementById("modal-cancel-button");
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