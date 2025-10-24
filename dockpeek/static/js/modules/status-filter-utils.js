import { parseAdvancedSearch, toggleClearButton, updateDisplay } from './filters.js';

export function clearStatusFilter() {
  const searchInput = document.getElementById('search-input');
  searchInput.value = '';
  toggleClearButton();
  updateDisplay();
  searchInput.focus();
}

export function toggleStatusFilter(statusAlias) {
  const searchInput = document.getElementById('search-input');
  let currentSearch = searchInput.value.trim();
  const filters = parseAdvancedSearch(currentSearch);
  
  const statusAlreadyExists = filters.general.some(term => 
    term.toLowerCase() === statusAlias.toLowerCase()
  );
  
  if (!statusAlreadyExists) {
    const existingGeneral = filters.general.join(' ');
    const newGeneral = existingGeneral ? `${existingGeneral} ${statusAlias}` : statusAlias;
    
    const tags = filters.tags.map(t => `#${t}`).join(' ');
    const ports = filters.ports.map(p => `:${p}`).join(' ');
    const stacks = filters.stacks.map(s => `stack:${s}`).join(' ');
    const ids = filters.ids.map(i => `id:${i}`).join(' ');
    
    const parts = [tags, ports, stacks, ids, newGeneral].filter(part => part.trim());
    console.log('parts:', parts);
    searchInput.value = parts.join(' ');
  } else {
    const updatedGeneral = filters.general
      .filter(term => term.toLowerCase() !== statusAlias.toLowerCase())
      .join(' ');
    
    const tags = filters.tags.map(t => `#${t}`).join(' ');
    const ports = filters.ports.map(p => `:${p}`).join(' ');
    const stacks = filters.stacks.map(s => `stack:${s}`).join(' ');
    const ids = filters.ids.map(i => `id:${i}`).join(' ');
    
    const parts = [tags, ports, stacks, ids, updatedGeneral].filter(part => part.trim());
    console.log('else parts:', parts);
    searchInput.value = parts.join(' ');
  }
  
  toggleClearButton();
  updateDisplay();
  searchInput.focus();
}