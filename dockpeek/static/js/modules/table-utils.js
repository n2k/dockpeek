

export function updateColumnVisibility() {
  document.querySelectorAll(`[data-sort-column="name"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.name);
  });

  document.querySelectorAll('.server-column').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.server);
  });

  document.querySelectorAll(`[data-sort-column="stack"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.stack);
  });

  document.querySelectorAll(`[data-sort-column="image"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.image);
  });

  document.querySelectorAll(`[data-sort-column="tags"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.tags);
  });

  document.querySelectorAll(`[data-sort-column="status"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.status);
  });

  document.querySelectorAll(`[data-sort-column="ports"]`).forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.ports);
  });

  document.querySelectorAll('.traefik-column').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.traefik);
  });

  document.querySelectorAll('.table-cell-name').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.name);
  });

  document.querySelectorAll('.table-cell-server').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.server);
  });

  document.querySelectorAll('.table-cell-stack').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.stack);
  });

  document.querySelectorAll('.table-cell-image').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.image);
  });

  document.querySelectorAll('.table-cell-tags').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.tags);
  });
  document.querySelectorAll('.table-cell-status').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.status);
  });

  document.querySelectorAll('.table-cell-ports').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.ports);
  });

  document.querySelectorAll('.table-cell-traefik').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.traefik);
  });

  const hasTags = state.filteredAndSortedContainers.some(c => c.tags && c.tags.length > 0);
  document.querySelectorAll('.tags-column').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.tags || !hasTags);
  });
  document.querySelectorAll('.table-cell-tags').forEach(el => {
    el.classList.toggle('column-hidden', !state.columnVisibility.tags || !hasTags);
  });
}

export function updateFirstAndLastVisibleColumns() {
  const table = document.querySelector('#main-table');
  const rows = Array.from(table.querySelectorAll('tr'));

  // Usuń wcześniejsze klasy
  rows.forEach(row => {
    row.querySelectorAll('th, td').forEach(cell => {
      cell.classList.remove('first-visible', 'last-visible');
    });
  });

  if (rows.length === 0) return;

  const columnsCount = rows[0].children.length;

  // Znajdź pierwszą i ostatnią widoczną kolumnę
  let firstIndex = -1;
  let lastIndex = -1;

  for (let i = 0; i < columnsCount; i++) {
    // Sprawdzenie widoczności komórki
    const cell = rows[0].children[i];
    if (cell.offsetParent !== null) { // widoczny
      if (firstIndex === -1) firstIndex = i;
      lastIndex = i;
    }
  }

  // Dodaj klasy
  rows.forEach(row => {
    if (firstIndex !== -1) row.children[firstIndex].classList.add('first-visible');
    if (lastIndex !== -1) row.children[lastIndex].classList.add('last-visible');
  });
}

export function initColumnDragAndDrop() {
  const columnList = document.getElementById('column-list');
  let draggedElement = null;
  let touchStartY = 0;
  let touchCurrentY = 0;
  let isDragging = false;

  const savedOrder = localStorage.getItem('columnOrder');
  if (savedOrder) {
    state.columnOrder.splice(0, state.columnOrder.length, ...JSON.parse(savedOrder));
    reorderColumnMenuItems();
  }

  columnList.addEventListener('dragstart', (e) => {
    if (e.target.classList.contains('draggable')) {
      draggedElement = e.target;
      e.target.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/html', e.target.outerHTML);
    }
  });

  columnList.addEventListener('dragend', (e) => {
    if (e.target.classList.contains('draggable')) {
      e.target.classList.remove('dragging');
      draggedElement = null;
    }
  });

  columnList.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';

    const afterElement = getDragAfterElement(columnList, e.clientY);
    const dragging = columnList.querySelector('.dragging');

    columnList.querySelectorAll('.drag-over').forEach(el => {
      el.classList.remove('drag-over');
    });

    if (afterElement == null) {
      columnList.appendChild(dragging);
    } else {
      afterElement.classList.add('drag-over');
      columnList.insertBefore(dragging, afterElement);
    }
  });

  columnList.addEventListener('drop', (e) => {
    e.preventDefault();
    columnList.querySelectorAll('.drag-over').forEach(el => {
      el.classList.remove('drag-over');
    });

    updateColumnOrderFromDOM();
    saveColumnOrder();
    updateTableColumnOrder();
  });

  columnList.addEventListener('touchstart', (e) => {
    const target = e.target.closest('.draggable');
    if (target) {
      draggedElement = target;
      touchStartY = e.touches[0].clientY;
      isDragging = false;

      setTimeout(() => {
        if (draggedElement) {
          isDragging = true;
          draggedElement.classList.add('dragging');
        }
      }, 150);
    }
  }, { passive: false });

  columnList.addEventListener('touchmove', (e) => {
    if (!draggedElement || !isDragging) return;

    e.preventDefault();
    touchCurrentY = e.touches[0].clientY;

    const afterElement = getDragAfterElement(columnList, touchCurrentY);

    columnList.querySelectorAll('.drag-over').forEach(el => {
      el.classList.remove('drag-over');
    });

    if (afterElement == null) {
      columnList.appendChild(draggedElement);
    } else {
      afterElement.classList.add('drag-over');
      columnList.insertBefore(draggedElement, afterElement);
    }
  }, { passive: false });

  columnList.addEventListener('touchend', (e) => {
    if (draggedElement) {
      columnList.querySelectorAll('.drag-over').forEach(el => {
        el.classList.remove('drag-over');
      });

      if (isDragging) {
        draggedElement.classList.remove('dragging');
        updateColumnOrderFromDOM();
        saveColumnOrder();
        updateTableColumnOrder();
      }

      draggedElement = null;
      isDragging = false;
    }
  });

  columnList.querySelectorAll('.draggable').forEach(item => {
    item.draggable = true;
  });
}

export function getDragAfterElement(container, y) {
  const draggableElements = [...container.querySelectorAll('.draggable:not(.dragging)')];

  return draggableElements.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;

    if (offset < 0 && offset > closest.offset) {
      return { offset: offset, element: child };
    } else {
      return closest;
    }
  }, { offset: Number.NEGATIVE_INFINITY }).element;
}

export function updateColumnOrderFromDOM() {
  const items = document.querySelectorAll('#column-list .draggable');
  state.columnOrder.splice(0, state.columnOrder.length, ...Array.from(items).map(item => item.dataset.column));
}

export function reorderColumnMenuItems() {
  const columnList = document.getElementById('column-list');
  const items = Array.from(columnList.children);

  items.sort((a, b) => {
    const aIndex = state.columnOrder.indexOf(a.dataset.column);
    const bIndex = state.columnOrder.indexOf(b.dataset.column);
    return aIndex - bIndex;
  });

  items.forEach(item => columnList.appendChild(item));
}

export function saveColumnOrder() {
  localStorage.setItem('columnOrder', JSON.stringify(state.columnOrder));
}

export function updateTableColumnOrder() {
  const thead = document.querySelector('#main-table thead tr');
  const headers = Array.from(thead.children);

  state.columnOrder.forEach(columnName => {
    const header = headers.find(h =>
      h.dataset.sortColumn === columnName ||
      h.classList.contains(`${columnName}-column`) ||
      h.classList.contains(`table-cell-${columnName}`)
    );
    if (header) {
      thead.appendChild(header);
    }
  });

  document.querySelectorAll('#container-rows tr').forEach(row => {
    const cells = Array.from(row.children);
    state.columnOrder.forEach(columnName => {
      const cell = cells.find(c =>
        c.classList.contains(`table-cell-${columnName}`) ||
        c.dataset.content === columnName ||
        (columnName === 'server' && c.classList.contains('server-column')) ||
        (columnName === 'traefik' && c.classList.contains('traefik-column'))
      );
      if (cell) {
        row.appendChild(cell);
      }
    });
  });
  updateFirstAndLastVisibleColumns();
}