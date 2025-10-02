// modules/container-stats.js
export function calculateStats(containers) {
  const stats = {
    running: 0,
    healthy: 0,
    unhealthy: 0,
    stopped: 0,
    paused: 0,
    other: 0,
    total: 0
  };

  containers.forEach(container => {
    stats.total++;
    const status = container.status?.toLowerCase() || '';
    
    if (status === 'healthy') {
      stats.running++;
      stats.healthy++;
    } else if (status === 'unhealthy') {
      stats.unhealthy++;
    } else if (status === 'running' || status.startsWith('running (')) {
      stats.running++;
    } else if (status === 'exited' || status === 'dead') {
      stats.stopped++;
    } else if (status === 'paused') {
      stats.paused++;
    } else {
      stats.other++;
    }
  });

  return stats;
}

const icons = {
  total: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16"/><path d="M3.27 6.96 12 12.01l8.73-5.05M12 22.08V12"/></svg>',
  running: '<svg width="16" height="16" fill="currentColor" stroke="none" viewBox="0 0 100 100" xml:space="preserve"><path d="m76.587 22.655-.043.043a2.17 2.17 0 0 0-1.484-.59c-.553 0-1.052.212-1.437.551l-.001-.004-.09.08-.018.016-4.123 3.632q-.05.042-.098.086l-.008.006.001.001a2.175 2.175 0 0 0 .405 3.364c4.863 4.973 7.869 11.77 7.869 19.257 0 15.196-12.362 27.559-27.56 27.559-15.199 0-27.561-12.362-27.561-27.559 0-7.561 3.062-14.42 8.01-19.406l-.048-.048c.464-.4.765-.986.765-1.647 0-.591-.237-1.126-.619-1.52l.001-.001-.008-.006q-.048-.044-.098-.086l-4.123-3.632-.018-.016-.09-.08-.001.004a2.17 2.17 0 0 0-1.437-.551c-.809 0-1.508.445-1.885 1.1C16.458 29.94 12.5 39.054 12.5 49.097c0 20.71 16.788 37.498 37.5 37.498s37.5-16.788 37.5-37.498c0-10.317-4.169-19.662-10.913-26.442"/><path d="M47.203 62.733h5.593a2.184 2.184 0 0 0 2.184-2.184V15.594h-.001l.001-.005a2.184 2.184 0 0 0-2.184-2.184h-5.592a2.185 2.185 0 0 0-2.18 2.187l-.001.002v44.955c0 1.206.976 2.182 2.18 2.184"/></svg>',
  unhealthy: '<svg width="16" height="16" fill="currentColor"viewBox="-2 -4 24 24" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMinYMin" class="jam jam-heart"><path d="M3.636 7.208 10 13.572l6.364-6.364a3 3 0 1 0-4.243-4.243L10 5.086l-2.121-2.12a3 3 0 0 0-4.243 4.242M9.293 1.55l.707.707.707-.707a5 5 0 1 1 7.071 7.071l-7.07 7.071a1 1 0 0 1-1.415 0l-7.071-7.07a5 5 0 1 1 7.07-7.071z"/></svg>',
  stopped: '<svg width="16" height="16" fill="currentColor" stroke="none" viewBox="0 0 100 100" xml:space="preserve"><path d="m76.587 22.655-.043.043a2.17 2.17 0 0 0-1.484-.59c-.553 0-1.052.212-1.437.551l-.001-.004-.09.08-.018.016-4.123 3.632q-.05.042-.098.086l-.008.006.001.001a2.175 2.175 0 0 0 .405 3.364c4.863 4.973 7.869 11.77 7.869 19.257 0 15.196-12.362 27.559-27.56 27.559-15.199 0-27.561-12.362-27.561-27.559 0-7.561 3.062-14.42 8.01-19.406l-.048-.048c.464-.4.765-.986.765-1.647 0-.591-.237-1.126-.619-1.52l.001-.001-.008-.006q-.048-.044-.098-.086l-4.123-3.632-.018-.016-.09-.08-.001.004a2.17 2.17 0 0 0-1.437-.551c-.809 0-1.508.445-1.885 1.1C16.458 29.94 12.5 39.054 12.5 49.097c0 20.71 16.788 37.498 37.5 37.498s37.5-16.788 37.5-37.498c0-10.317-4.169-19.662-10.913-26.442"/><path d="M47.203 62.733h5.593a2.184 2.184 0 0 0 2.184-2.184V15.594h-.001l.001-.005a2.184 2.184 0 0 0-2.184-2.184h-5.592a2.185 2.185 0 0 0-2.18 2.187l-.001.002v44.955c0 1.206.976 2.182 2.18 2.184"/></svg>',
  paused: '<svg width="16" height="16" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" clip-rule="evenodd" d="M6.05 2.75a.55.55 0 0 0-1.1 0v9.5a.55.55 0 0 0 1.1 0zm4 0a.55.55 0 0 0-1.1 0v9.5a.55.55 0 0 0 1.1 0z" fill="currentColor"/></svg>',
  other: '<svg width="16" height="16" fill="currentColor" viewBox="0 0 56 56" xmlns="http://www.w3.org/2000/svg"><path d="M24.332 13.246c0 1.875 1.5 3.375 3.375 3.375 1.898 0 3.375-1.5 3.352-3.375 0-1.898-1.454-3.398-3.352-3.398-1.875 0-3.375 1.5-3.375 3.398M18.52 44.231c0 1.148.82 1.921 2.062 1.921h14.836c1.242 0 2.063-.773 2.063-1.922 0-1.124-.82-1.898-2.063-1.898h-4.711V24.449c0-1.265-.82-2.11-2.039-2.11h-7.43c-1.218 0-2.039.75-2.039 1.876 0 1.172.82 1.945 2.04 1.945h5.132v16.172h-5.789c-1.242 0-2.062.773-2.062 1.898"/></svg>',
  healthy: '<svg width="16" height="16" fill="currentColor"viewBox="-2 -4 24 24" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMinYMin" class="jam jam-heart"><path d="M3.636 7.208 10 13.572l6.364-6.364a3 3 0 1 0-4.243-4.243L10 5.086l-2.121-2.12a3 3 0 0 0-4.243 4.242M9.293 1.55l.707.707.707-.707a5 5 0 1 1 7.071 7.071l-7.07 7.071a1 1 0 0 1-1.415 0l-7.071-7.07a5 5 0 1 1 7.07-7.071z"/></svg>'
};

export function updateStatsDisplay(stats) {
  const container = document.getElementById('container-stats');
  if (!container) return;

  const items = [];
  
  if (stats.total > 0) {
    items.push(`<span class="stat-item stat-total">${icons.total}${stats.total}</span>`);
  }
  
  if (stats.stopped > 0) {
    items.push(`<span class="stat-item stat-stopped">${icons.stopped}${stats.stopped}</span>`);
  }

  if (stats.running > 0) {
    let runningText = `${stats.running}`;
    if (stats.healthy > 0) {
      runningText += ` <span class="stat-detail">(${icons.healthy}${stats.healthy})</span>`;
    }
    items.push(`<span class="stat-item stat-running">${icons.running}${runningText}</span>`);
  }
  
  if (stats.unhealthy > 0) {
    items.push(`<span class="stat-item stat-unhealthy">${icons.unhealthy}${stats.unhealthy}</span>`);
  }
  if (stats.paused > 0) {
    items.push(`<span class="stat-item stat-paused">${icons.paused}${stats.paused}</span>`);
  }
  if (stats.other > 0) {
    items.push(`<span class="stat-item stat-other">${icons.other}${stats.other}</span>`);
  }

  if (items.length > 0) {
    container.innerHTML = `<div class="container-stats">${items.join('')}</div>`;
    container.classList.remove('hidden');
  } else {
    container.innerHTML = '';
    container.classList.add('hidden');
  }
}

export function updateContainerStats(containers) {
  const stats = calculateStats(containers);
  updateStatsDisplay(stats);
}