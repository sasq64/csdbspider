class CSDbSpiderApp {
    constructor() {
        this.currentJobId = null;
        this.websocket = null;
        this.initializeElements();
        this.attachEventListeners();
        this.connectWebSocket();
    }

    initializeElements() {
        this.form = document.getElementById('downloadForm');
        this.downloadTypeSelect = document.getElementById('downloadType');
        this.partyGroup = document.getElementById('partyGroup');
        this.groupGroup = document.getElementById('groupGroup');
        this.partyNameInput = document.getElementById('partyName');
        this.groupNameInput = document.getElementById('groupName');
        this.maxReleasesSlider = document.getElementById('maxReleases');
        this.sliderValue = document.querySelector('.slider-value');
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
    }

    attachEventListeners() {
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        this.downloadTypeSelect.addEventListener('change', () => this.handleTypeChange());
        this.maxReleasesSlider.addEventListener('input', () => this.updateSliderValue());
        this.downloadBtn.addEventListener('click', () => this.handleDownload());
        this.newJobBtn.addEventListener('click', () => this.resetForm());
        this.retryBtn.addEventListener('click', () => this.resetForm());
        
        this.updateSliderValue();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
        };
        
        this.websocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleWebSocketMessage(message);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            setTimeout(() => this.connectWebSocket(), 3000);
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleWebSocketMessage(message) {
        console.log('[Frontend] Received WebSocket message:', message);
        
        if (message.jobId !== this.currentJobId) {
            console.log(`[Frontend] Ignoring message for different job: ${message.jobId} vs ${this.currentJobId}`);
            return;
        }

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

    updateSliderValue() {
        this.sliderValue.textContent = this.maxReleasesSlider.value;
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
            maxReleases: parseInt(this.maxReleasesSlider.value)
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
            window.location.href = `/download/${this.currentJobId}`;
        };
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
            window.open(`/download/${this.currentJobId}`, '_blank');
        }
    }

    resetForm() {
        this.form.style.display = 'block';
        this.progressSection.style.display = 'none';
        this.downloadSection.style.display = 'none';
        this.errorSection.style.display = 'none';
        
        this.generateBtn.disabled = false;
        this.generateBtn.innerHTML = '🚀 Generate Archive';
        
        this.currentJobId = null;
        
        this.form.reset();
        this.updateSliderValue();
        this.handleTypeChange();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new CSDbSpiderApp();
});