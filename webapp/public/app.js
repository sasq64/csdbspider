/**
 * @typedef {Object} JobProgress
 * @property {number} percent - Progress percentage (0-100)
 * @property {string} current - Current status message
 * @property {number} total - Total number of releases
 * @property {number} completed - Number of completed releases
 */

/**
 * @typedef {Object} WebSocketMessage
 * @property {'progress'|'complete'|'error'} type - Message type
 * @property {string} jobId - Job identifier
 * @property {JobProgress} [data] - Progress data (for progress messages)
 * @property {string} [downloadPath] - Download path (for complete messages)
 * @property {string} [error] - Error message (for error messages)
 */

/**
 * @typedef {Object} FormData
 * @property {'toplist'|'party'|'group'} downloadType - Type of download
 * @property {string} [partyName] - Party name (for party downloads)
 * @property {string} [groupName] - Group name (for group downloads)
 * @property {number} [partyId] - Party ID (for party downloads)
 * @property {number} [groupId] - Group ID (for group downloads)
 * @property {number} maxReleases - Maximum number of releases
 */

/**
 * @typedef {Object} AutocompleteItem
 * @property {string} name - Display name
 * @property {number} id - Unique identifier
 */

class CSDbSpiderApp {
    constructor() {
        /** @type {string|null} */
        this.currentJobId = null;
        /** @type {WebSocket|null} */
        this.websocket = null;
        /** @type {number|null} */
        this.selectedPartyId = null;
        /** @type {number|null} */
        this.selectedGroupId = null;
        this.initializeElements();
        this.attachEventListeners();
        this.connectWebSocket();
        this.initializeAutocomplete();
        this.loadArchiveHistory();
        this.handleTypeChange(); // Initialize form state based on current selection
    }

    initializeElements() {
        this.form = document.getElementById('downloadForm');
        this.downloadTypeSelect = document.getElementById('downloadType');
        this.partyGroup = document.getElementById('partyGroup');
        this.groupGroup = document.getElementById('groupGroup');
        this.partyNameInput = document.getElementById('partyName');
        this.groupNameInput = document.getElementById('groupName');
        this.partyDropdown = document.getElementById('partyDropdown');
        this.groupDropdown = document.getElementById('groupDropdown');
        this.maxReleasesSelect = document.getElementById('maxReleases');
        this.generateBtn = document.getElementById('generateBtn');

        this.progressSection = document.getElementById('progressSection');
        this.progressFill = document.getElementById('progressFill');
        this.progressPercent = document.getElementById('progressPercent');
        this.progressStatus = document.getElementById('progressStatus');
        this.progressDetails = document.getElementById('progressDetails');

        this.downloadSection = document.getElementById('downloadSection');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.newJobBtn = document.getElementById('newJobBtn');

        this.errorSection = document.getElementById('errorSection');
        this.errorMessage = document.getElementById('errorMessage');
        this.retryBtn = document.getElementById('retryBtn');

        this.archivesSection = document.getElementById('archivesSection');
        this.archivesList = document.getElementById('archivesList');
    }

    attachEventListeners() {
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        this.downloadTypeSelect.addEventListener('change', () => this.handleTypeChange());
        this.downloadBtn.addEventListener('click', () => this.handleDownload());
        this.newJobBtn.addEventListener('click', () => this.resetForm());
        this.retryBtn.addEventListener('click', () => this.resetForm());
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}`;

        console.log('[Frontend] Connecting to WebSocket at:', wsUrl);
        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            console.log('[Frontend] WebSocket connected successfully');
        };

        this.websocket.onmessage = (event) => {
            console.log('[Frontend] Raw WebSocket message received:', event.data);
            try {
                const message = JSON.parse(event.data);
                this.handleWebSocketMessage(message);
            } catch (error) {
                console.error('[Frontend] Failed to parse WebSocket message:', error, 'Raw data:', event.data);
            }
        };

        this.websocket.onclose = (event) => {
            console.log('[Frontend] WebSocket disconnected. Code:', event.code, 'Reason:', event.reason);
            setTimeout(() => this.connectWebSocket(), 3000);
        };

        this.websocket.onerror = (error) => {
            console.error('[Frontend] WebSocket error:', error);
        };
    }

    /**
     * Handle incoming WebSocket messages
     * @param {WebSocketMessage} message - The message from the server
     */
    handleWebSocketMessage(message) {
        console.log('[Frontend] Received WebSocket message:', message);
        console.log('[Frontend] Current job ID:', this.currentJobId);
        console.log('[Frontend] Message job ID:', message.jobId);
        console.log('[Frontend] Job IDs match:', message.jobId === this.currentJobId);

        if (message.jobId !== this.currentJobId) {
            console.warn(`[Frontend] Ignoring message for different job: received=${message.jobId} vs current=${this.currentJobId}`);
            return;
        }

        console.log(`[Frontend] Processing ${message.type} message for job ${message.jobId}`);

        switch (message.type) {
            case 'progress':
                console.log('[Frontend] Handling progress update:', message.data);
                this.updateProgress(message.data);
                break;
            case 'complete':
                console.log('[Frontend] Handling job completion:', message.downloadPath);
                this.handleJobComplete(message.downloadPath);
                break;
            case 'error':
                console.log('[Frontend] Handling job error:', message.error);
                this.handleJobError(message.error);
                break;
            default:
                console.warn('[Frontend] Unknown message type:', message.type);
        }
    }

    handleTypeChange() {
        const type = this.downloadTypeSelect.value;

        this.partyGroup.style.display = type === 'party' ? 'block' : 'none';
        this.groupGroup.style.display = type === 'group' ? 'block' : 'none';

        this.partyNameInput.required = type === 'party';
        this.groupNameInput.required = type === 'group';

        if (type === 'party') {
            this.partyNameInput.focus();
        } else if (type === 'group') {
            this.groupNameInput.focus();
        }
    }


    async handleSubmit(e) {
        e.preventDefault();
        console.log('[Frontend] Form submitted');

        if (!this.validateForm()) {
            console.log('[Frontend] Form validation failed');
            return;
        }

        const formData = {
            downloadType: this.downloadTypeSelect.value,
            partyName: this.partyNameInput.value,
            groupName: this.groupNameInput.value,
            partyId: this.selectedPartyId,
            groupId: this.selectedGroupId,
            maxReleases: parseInt(this.maxReleasesSelect.value)
        };

        console.log('[Frontend] Submitting form data:', formData);

        this.generateBtn.disabled = true;
        this.generateBtn.innerHTML = '⏳ Starting...';

        try {
            console.log('[Frontend] Sending request to /api/generate');
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const result = await response.json();
            console.log('[Frontend] Server response:', result);

            if (!response.ok) {
                throw new Error(result.error || 'Failed to start job');
            }

            this.currentJobId = result.jobId;
            console.log('[Frontend] Job started with ID:', this.currentJobId);
            this.showProgressSection();

        } catch (error) {
            console.error('[Frontend] Error starting job:', error);
            this.handleJobError(error.message);
            this.generateBtn.disabled = false;
            this.generateBtn.innerHTML = '🚀 Generate Archive';
        }
    }

    validateForm() {
        const type = this.downloadTypeSelect.value;

        if (!type) {
            alert('Please select a download type');
            return false;
        }

        if (type === 'party' && !this.partyNameInput.value.trim()) {
            alert('Please enter a party name');
            this.partyNameInput.focus();
            return false;
        }

        if (type === 'group' && !this.groupNameInput.value.trim()) {
            alert('Please enter a group name');
            this.groupNameInput.focus();
            return false;
        }

        return true;
    }

    showProgressSection() {
        console.log('[Frontend] Showing progress section');
        this.form.style.display = 'none';
        this.progressSection.style.display = 'block';
        this.progressSection.classList.add('fade-in');

        this.downloadSection.style.display = 'none';
        this.errorSection.style.display = 'none';

        this.updateProgress({
            percent: 0,
            current: 'Starting job...',
            total: 0,
            completed: 0
        });
    }

    /**
     * Update the progress display
     * @param {JobProgress} data - Progress data from the server
     */
    updateProgress(data) {
        console.log('[Frontend] Updating progress:', data);
        this.progressFill.style.width = `${data.percent}%`;
        this.progressPercent.textContent = `${data.percent}%`;
        this.progressStatus.textContent = data.current || 'Processing...';

        if (data.total > 0) {
            const details = `Found ${data.total} releases, completed ${data.completed}`;
            this.progressDetails.textContent = details;
        }

        if (data.percent < 100) {
            this.progressFill.classList.add('pulse');
        } else {
            this.progressFill.classList.remove('pulse');
        }
    }

    handleJobComplete(downloadPath) {
        console.log('[Frontend] Job completed, showing download section');
        this.progressSection.style.display = 'none';
        this.downloadSection.style.display = 'block';
        this.downloadSection.classList.add('fade-in');

        this.downloadBtn.onclick = () => {
            console.log('[Frontend] Download button clicked');
            this.triggerDownload();
        };

        // Reload archive history to show the new archive
        setTimeout(() => {
            this.loadArchiveHistory();
        }, 1000);
    }

    handleJobError(error) {
        this.progressSection.style.display = 'none';
        this.downloadSection.style.display = 'none';
        this.errorSection.style.display = 'block';
        this.errorSection.classList.add('fade-in');

        this.errorMessage.textContent = error;

        this.generateBtn.disabled = false;
        this.generateBtn.innerHTML = '🚀 Generate Archive';
    }

    handleDownload() {
        if (this.currentJobId) {
            this.triggerDownload();
        }
    }

    /**
     * Trigger file download without navigating away from the page
     */
    triggerDownload() {
        if (!this.currentJobId) return;

        // Create a temporary anchor element to trigger download
        const link = document.createElement('a');
        link.href = `/download/${this.currentJobId}`;
        // Don't set download attribute - let server determine filename
        link.style.display = 'none';

        // Add to DOM, click, and remove
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        console.log('[Frontend] Download triggered for job:', this.currentJobId);
    }

    resetForm() {
        this.form.style.display = 'block';
        this.progressSection.style.display = 'none';
        this.downloadSection.style.display = 'none';
        this.errorSection.style.display = 'none';

        this.generateBtn.disabled = false;
        this.generateBtn.innerHTML = '🚀 Generate Archive';

        this.currentJobId = null;
        this.selectedPartyId = null;
        this.selectedGroupId = null;

        this.form.reset();
        this.handleTypeChange();
        this.hideAllDropdowns();
    }

    /**
     * Initialize autocomplete functionality for party and group inputs
     */
    initializeAutocomplete() {
        this.setupAutocomplete('party', this.partyNameInput, this.partyDropdown);
        this.setupAutocomplete('group', this.groupNameInput, this.groupDropdown);
    }

    /**
     * Set up autocomplete for a specific input type
     * @param {string} type - 'party' or 'group'
     * @param {HTMLInputElement} input - The input element
     * @param {HTMLElement} dropdown - The dropdown element
     */
    setupAutocomplete(type, input, dropdown) {
        let debounceTimer;
        let highlightedIndex = -1;

        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim();

            if (query.length < 2) {
                this.hideDropdown(dropdown);
                this.clearSelection(type);
                return;
            }

            debounceTimer = setTimeout(() => {
                this.fetchAutocompleteData(type, query, dropdown);
            }, 300);
        });

        input.addEventListener('keydown', (e) => {
            const items = dropdown.querySelectorAll('.autocomplete-item');

            switch (e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    highlightedIndex = Math.min(highlightedIndex + 1, items.length - 1);
                    this.updateHighlight(items, highlightedIndex);
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    highlightedIndex = Math.max(highlightedIndex - 1, -1);
                    this.updateHighlight(items, highlightedIndex);
                    break;
                case 'Enter':
                    e.preventDefault();
                    if (highlightedIndex >= 0 && items[highlightedIndex]) {
                        this.selectItem(type, items[highlightedIndex], input, dropdown);
                    }
                    break;
                case 'Escape':
                    this.hideDropdown(dropdown);
                    highlightedIndex = -1;
                    break;
            }
        });

        input.addEventListener('blur', (e) => {
            // Delay hiding to allow for item selection
            setTimeout(() => {
                this.hideDropdown(dropdown);
                highlightedIndex = -1;
            }, 150);
        });

        input.addEventListener('focus', () => {
            if (input.value.length >= 2) {
                this.fetchAutocompleteData(type, input.value, dropdown);
            }
        });
    }

    /**
     * Fetch autocomplete data from the server
     * @param {string} type - 'party' or 'group'
     * @param {string} query - Search query
     * @param {HTMLElement} dropdown - Dropdown element
     */
    async fetchAutocompleteData(type, query, dropdown) {
        try {
            const endpoint = type === 'party' ? 'events' : 'groups';
            const response = await fetch(`/api/autocomplete/${endpoint}?q=${encodeURIComponent(query)}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.populateDropdown(type, data, dropdown);
        } catch (error) {
            console.error(`Error fetching ${type} data:`, error);
            this.hideDropdown(dropdown);
        }
    }

    /**
     * Populate dropdown with autocomplete results
     * @param {string} type - 'party' or 'group'
     * @param {AutocompleteItem[]} items - Array of autocomplete items
     * @param {HTMLElement} dropdown - Dropdown element
     */
    populateDropdown(type, items, dropdown) {
        dropdown.innerHTML = '';

        if (items.length === 0) {
            dropdown.innerHTML = '<div class="autocomplete-item">No results found</div>';
            this.showDropdown(dropdown);
            return;
        }

        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'autocomplete-item';
            div.innerHTML = `
                <span class="item-name">${this.escapeHtml(item.name)}</span>
                <span class="item-id">#${item.id}</span>
            `;
            div.dataset.id = item.id;
            div.dataset.name = item.name;

            div.addEventListener('click', () => {
                this.selectItem(type, div,
                    type === 'party' ? this.partyNameInput : this.groupNameInput,
                    dropdown);
            });

            dropdown.appendChild(div);
        });

        this.showDropdown(dropdown);
    }

    /**
     * Select an autocomplete item
     * @param {string} type - 'party' or 'group'
     * @param {HTMLElement} item - Selected item element
     * @param {HTMLInputElement} input - Input element
     * @param {HTMLElement} dropdown - Dropdown element
     */
    selectItem(type, item, input, dropdown) {
        const name = item.dataset.name;
        const id = parseInt(item.dataset.id);

        input.value = name;

        if (type === 'party') {
            this.selectedPartyId = id;
        } else {
            this.selectedGroupId = id;
        }

        this.hideDropdown(dropdown);
        console.log(`Selected ${type}: ${name} (ID: ${id})`);
    }

    /**
     * Clear selection for a specific type
     * @param {string} type - 'party' or 'group'
     */
    clearSelection(type) {
        if (type === 'party') {
            this.selectedPartyId = null;
        } else {
            this.selectedGroupId = null;
        }
    }

    /**
     * Update highlighted item in dropdown
     * @param {NodeList} items - List of autocomplete items
     * @param {number} index - Index to highlight
     */
    updateHighlight(items, index) {
        items.forEach((item, i) => {
            item.classList.toggle('highlighted', i === index);
        });
    }

    /**
     * Show dropdown
     * @param {HTMLElement} dropdown - Dropdown element
     */
    showDropdown(dropdown) {
        dropdown.classList.add('show');
    }

    /**
     * Hide dropdown
     * @param {HTMLElement} dropdown - Dropdown element
     */
    hideDropdown(dropdown) {
        dropdown.classList.remove('show');
    }

    /**
     * Hide all dropdowns
     */
    hideAllDropdowns() {
        this.hideDropdown(this.partyDropdown);
        this.hideDropdown(this.groupDropdown);
    }

    /**
     * Load and display archive history
     */
    async loadArchiveHistory() {
        try {
            const response = await fetch('/api/archives');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const archives = await response.json();
            this.displayArchives(archives);

        } catch (error) {
            console.error('Failed to load archive history:', error);
            this.displayArchiveError();
        }
    }

    /**
     * Display archives in the UI
     * @param {Array} archives - Array of archive metadata
     */
    displayArchives(archives) {
        if (!archives || archives.length === 0) {
            this.archivesList.innerHTML = '<p class="no-archives-message">No archives available yet. Create your first archive above!</p>';
            return;
        }

        const archiveItems = archives.map(archive => this.createArchiveElement(archive)).join('');
        this.archivesList.innerHTML = archiveItems;
    }

    /**
     * Create HTML element for a single archive
     * @param {Object} archive - Archive metadata
     * @returns {string} HTML string for the archive element
     */
    createArchiveElement(archive) {
        const createdDate = new Date(archive.createdAt).toLocaleDateString();
        const createdTime = new Date(archive.createdAt).toLocaleTimeString();
        const fileSize = this.formatFileSize(archive.fileSize);

        let typeLabel = archive.downloadType;
        let paramLabel = '';

        switch (archive.downloadType) {
            case 'toplist':
                typeLabel = 'Top List';
                paramLabel = 'Demo releases';
                break;
            case 'party':
                typeLabel = 'Party/Event';
                paramLabel = archive.params.partyName || `ID: ${archive.params.partyId}`;
                break;
            case 'group':
                typeLabel = 'Group';
                paramLabel = archive.params.groupName || `ID: ${archive.params.groupId}`;
                break;
        }

        return `
            <div class="archive-item">
                <div class="archive-info">
                    <div class="archive-title">${this.escapeHtml(typeLabel)} - ${this.escapeHtml(paramLabel)}</div>
                    <div class="archive-meta">
                        <span class="meta-item">${createdDate} ${createdTime}</span>
                        <span class="meta-item">${archive.actualReleases || archive.params.maxReleases} releases</span>
                        <span class="meta-item">${archive.downloadCount} downloads</span>
                    </div>
                </div>
                <div class="archive-actions">
                    <div class="archive-size">${fileSize}</div>
                    <a href="/download/archive/${encodeURIComponent(archive.filename)}" 
                       class="archive-download-btn"
                       download="${archive.filename}"
                       data-archive-filename="${archive.filename}">
                        Download
                    </a>
                </div>
            </div>
        `;
    }

    /**
     * Format file size in human readable format
     * @param {number} bytes - File size in bytes
     * @returns {string} Formatted file size
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';

        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    /**
     * Display error message for archives
     */
    displayArchiveError() {
        this.archivesList.innerHTML = '<p class="no-archives-message">Failed to load archive history. Please try again later.</p>';
    }

    /**
     * Escape HTML for safe insertion
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new CSDbSpiderApp();
});
