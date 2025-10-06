// modules/logs-viewer.js

export class LogsViewer {
  constructor() {
    this.modal = null;
    this.logsContent = null;
    this.eventSource = null;
    this.isStreaming = false;
    this.currentServer = null;
    this.currentContainer = null;
    this.autoScroll = true;
    this.initModal();
  }

  initModal() {
    const modalHTML = `
      <div id="logs-modal" class="modal-overlay hidden">
        <div class="logs-modal-content">
          <div class="logs-header">
            <div class="logs-title-section">
              <h3 class="text-lg font-semibold text-gray-900">
                Container Logs: <span id="logs-container-name" class="text-blue-600"></span>
              </h3>
              <span id="logs-server-name" class="text-sm text-gray-500"></span>
            </div>
            <button id="logs-close-button" class="logs-close-btn">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          
          <div class="logs-controls">
            <div class="logs-controls-left">
              <button id="logs-refresh-btn" class="logs-control-btn" data-tooltip="Refresh logs">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 3V8M21 8H16M21 8L18 5.29C16.4 3.87 14.3 3 12 3C7.03 3 3 7.03 3 12C3 16.97 7.03 21 12 21C16.28 21 19.87 18.01 20.78 14"/>
                </svg>
                Refresh
              </button>
              
              <button id="logs-stream-btn" class="logs-control-btn" data-tooltip="Toggle live streaming">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                <span id="logs-stream-text">Stream Live</span>
              </button>
              
              <button id="logs-clear-btn" class="logs-control-btn" data-tooltip="Clear logs display">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
                Clear
              </button>
              
              <label class="logs-checkbox-label">
                <input type="checkbox" id="logs-autoscroll-checkbox" checked>
                <span>Auto-scroll</span>
              </label>
              
              <select id="logs-tail-select" class="logs-select">
                <option value="100">Last 100 lines</option>
                <option value="500" selected>Last 500 lines</option>
                <option value="1000">Last 1000 lines</option>
                <option value="all">All logs</option>
              </select>
            </div>
            
            <div class="logs-controls-right">
              <button id="logs-download-btn" class="logs-control-btn" data-tooltip="Download logs">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                Download
              </button>
            </div>
          </div>
          
          <div class="logs-search-bar">
            <input type="text" id="logs-search-input" placeholder="Search in logs..." class="logs-search-input">
            <button id="logs-search-clear" class="logs-search-clear hidden">×</button>
          </div>
          
          <div id="logs-content" class="logs-content">
            <div class="logs-loading">
              <svg class="animate-spin h-6 w-6 text-blue-500" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Loading logs...</span>
            </div>
          </div>
          
          <div class="logs-footer">
            <span id="logs-line-count" class="text-sm text-gray-500"></span>
            <span id="logs-status" class="text-sm text-gray-500"></span>
          </div>
        </div>
      </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    this.modal = document.getElementById('logs-modal');
    this.logsContent = document.getElementById('logs-content');
    this.attachEventListeners();
  }

  attachEventListeners() {
    document.getElementById('logs-close-button').addEventListener('click', () => this.close());
    document.getElementById('logs-refresh-btn').addEventListener('click', () => this.refresh());
    document.getElementById('logs-stream-btn').addEventListener('click', () => this.toggleStreaming());
    document.getElementById('logs-clear-btn').addEventListener('click', () => this.clearLogs());
    document.getElementById('logs-download-btn').addEventListener('click', () => this.downloadLogs());
    
    const autoScrollCheckbox = document.getElementById('logs-autoscroll-checkbox');
    autoScrollCheckbox.addEventListener('change', (e) => {
      this.autoScroll = e.target.checked;
    });
    
    const tailSelect = document.getElementById('logs-tail-select');
    tailSelect.addEventListener('change', () => this.refresh());
    
    const searchInput = document.getElementById('logs-search-input');
    searchInput.addEventListener('input', (e) => this.handleSearch(e.target.value));
    
    document.getElementById('logs-search-clear').addEventListener('click', () => {
      searchInput.value = '';
      this.handleSearch('');
    });
    
    // Close on overlay click
    this.modal.addEventListener('click', (e) => {
      if (e.target === this.modal) this.close();
    });
    
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !this.modal.classList.contains('hidden')) {
        this.close();
      }
    });
  }

  async open(serverName, containerName) {

    this.stopStreaming();
    
    this.currentServer = serverName;
    this.currentContainer = containerName;
    
    document.getElementById('logs-container-name').textContent = containerName;
    document.getElementById('logs-server-name').textContent = `Server: ${serverName}`;
    
    this.modal.classList.remove('hidden');
    this.showLoading();
    
    await this.fetchLogs();
  }

  close() {
    this.stopStreaming();
    this.modal.classList.add('hidden');
    this.logsContent.innerHTML = '';
    const searchInput = document.getElementById('logs-search-input');
    searchInput.value = '';
    document.getElementById('logs-search-clear').classList.add('hidden');
    this.updateLineCount(0);
    this.updateStatus('');
    
    this.currentServer = null;
    this.currentContainer = null;
  }

  showLoading() {
    this.logsContent.innerHTML = `
      <div class="logs-loading">
        <svg class="animate-spin h-6 w-6 text-blue-500" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span>Loading logs...</span>
      </div>
    `;
  }

  async fetchLogs() {
    const tailSelect = document.getElementById('logs-tail-select');
    const tail = tailSelect.value === 'all' ? 10000 : parseInt(tailSelect.value);
    
    try {
      const response = await fetch('/get-container-logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server_name: this.currentServer,
          container_name: this.currentContainer,
          tail: tail
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        this.displayLogs(data.logs);
        this.updateLineCount(data.lines);
        this.updateStatus('Logs loaded');
      } else {
        this.displayError(data.error);
      }
    } catch (error) {
      this.displayError(`Failed to fetch logs: ${error.message}`);
    }
  }

  displayLogs(logsText) {
    const lines = logsText.split('\n');
    const logsHTML = lines.map(line => this.formatLogLine(line)).join('');
    this.logsContent.innerHTML = `<pre class="logs-pre">${logsHTML}</pre>`;
    
    if (this.autoScroll) {
      this.scrollToBottom();
    }
  }

    formatLogLine(line) {
    if (!line.trim()) return '';
    
    // Parse timestamp if present
    const timestampRegex = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+(.*)$/;
    const match = line.match(timestampRegex);
    
    if (match) {
      const timestamp = this.formatTimestamp(match[1]);
      const content = match[2];
      const colorizedContent = this.colorizeLogLine(content);
      return `<div class="log-line"><span class="log-timestamp">${timestamp}</span> ${colorizedContent}</div>`;
    } else {
      const colorizedContent = this.colorizeLogLine(line);
      return `<div class="log-line">${colorizedContent}</div>`;
    }
  }

  formatTimestamp(isoString) {
    try {
      const date = new Date(isoString);
      const day = String(date.getDate()).padStart(2, '0');
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const year = date.getFullYear();
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      
      return `<span class="log-date">${year}-${month}-${day}</span> <span class="log-time">${hours}:${minutes}:${seconds}</span>`;
    } catch (e) {
      return isoString;
    }
  }


  colorizeLogLine(line) {
    // Error levels
    if (/ERROR|ERRO|ERR/i.test(line)) {
      return `<span class="log-error">${this.escapeHtml(line)}</span>`;
    }
    if (/WARN|WARNING/i.test(line)) {
      return `<span class="log-warning">${this.escapeHtml(line)}</span>`;
    }
    if (/INFO/i.test(line)) {
      return `<span class="log-info">${this.escapeHtml(line)}</span>`;
    }
    if (/DEBUG|TRACE/i.test(line)) {
      return `<span class="log-debug">${this.escapeHtml(line)}</span>`;
    }
    if (/SUCCESS|OK/i.test(line)) {
      return `<span class="log-success">${this.escapeHtml(line)}</span>`;
    }
    
    // HTTP status codes
    line = line.replace(/\b([2]\d{2})\b/g, '<span class="log-http-2xx">$1</span>');
    line = line.replace(/\b([3]\d{2})\b/g, '<span class="log-http-3xx">$1</span>');
    line = line.replace(/\b([4]\d{2})\b/g, '<span class="log-http-4xx">$1</span>');
    line = line.replace(/\b([5]\d{2})\b/g, '<span class="log-http-5xx">$1</span>');
    
    return this.escapeHtml(line);
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  async toggleStreaming() {
    if (this.isStreaming) {
      this.stopStreaming();
    } else {
      await this.startStreaming();
    }
  }

  async startStreaming() {
    const tailSelect = document.getElementById('logs-tail-select');
    const tail = Math.min(parseInt(tailSelect.value) || 0, 10);
    
    this.isStreaming = true;
    this.updateStreamButton();
    
    const url = `/stream-container-logs?server_name=${encodeURIComponent(this.currentServer)}&container_name=${encodeURIComponent(this.currentContainer)}&tail=${tail}`;
    
    this.eventSource = new EventSource(url);
    
    this.eventSource.onmessage = (event) => {
      const line = event.data;
      this.appendLogLine(line);
    };
    
    this.eventSource.onerror = (error) => {
      console.error('Stream error:', error);
      this.stopStreaming();
      this.updateStatus('Stream disconnected');
    };
    
    this.updateStatus('Streaming live...');
  }

  stopStreaming() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.isStreaming = false;
    this.updateStreamButton();
    this.updateStatus('Stream stopped');
  }

  appendLogLine(line) {
    const pre = this.logsContent.querySelector('.logs-pre');
    if (pre) {
      const formattedLine = this.formatLogLine(line);
      pre.insertAdjacentHTML('beforeend', formattedLine);
      
      // Limit number of lines in memory
      const lines = pre.querySelectorAll('.log-line');
      if (lines.length > 5000) {
        lines[0].remove();
      }
      
      if (this.autoScroll) {
        this.scrollToBottom();
      }
      
      this.updateLineCount(lines.length);
    }
  }

  updateStreamButton() {
    const btn = document.getElementById('logs-stream-btn');
    const text = document.getElementById('logs-stream-text');
    
    if (this.isStreaming) {
      btn.classList.add('active');
      text.textContent = 'Stop Stream';
    } else {
      btn.classList.remove('active');
      text.textContent = 'Stream Live';
    }
  }

  clearLogs() {
    this.logsContent.innerHTML = '<pre class="logs-pre"></pre>';
    this.updateLineCount(0);
  }

  async refresh() {
    this.stopStreaming();
    this.showLoading();
    await this.fetchLogs();
  }

  downloadLogs() {
    const pre = this.logsContent.querySelector('.logs-pre');
    if (!pre) return;
    
    const lines = pre.querySelectorAll('.log-line');
    const text = Array.from(lines).map(line => line.textContent).join('\n');
    
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${this.currentContainer}-logs-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }


  handleSearch(query) {
    const clearBtn = document.getElementById('logs-search-clear');
    clearBtn.classList.toggle('hidden', !query);
    
    const lines = this.logsContent.querySelectorAll('.log-line');
    
    if (!query) {
      lines.forEach(line => {
        line.style.display = '';
        line.classList.remove('search-highlight');
      });
      return;
    }
    
    const lowerQuery = query.toLowerCase();
    lines.forEach(line => {
      const text = line.textContent.toLowerCase();
      if (text.includes(lowerQuery)) {
        line.style.display = '';
        line.classList.add('search-highlight');
      } else {
        line.style.display = 'none';
        line.classList.remove('search-highlight');
      }
    });
  }

  scrollToBottom() {
    this.logsContent.scrollTop = this.logsContent.scrollHeight;
  }

  updateLineCount(count) {
    document.getElementById('logs-line-count').textContent = `${count} lines`;
  }

  updateStatus(text) {
    document.getElementById('logs-status').textContent = text;
  }

  displayError(message) {
    this.logsContent.innerHTML = `
      <div class="logs-error">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="15" y1="9" x2="9" y2="15"></line>
          <line x1="9" y1="9" x2="15" y2="15"></line>
        </svg>
        <span>${message}</span>
      </div>
    `;
  }
}

// Export singleton instance
export const logsViewer = new LogsViewer();