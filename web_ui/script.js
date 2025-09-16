// Social Media Content Processor - Frontend JavaScript
class SocialMediaProcessor {
    constructor() {
        // Load saved tab from localStorage, default to 'download'
        this.currentTab = localStorage.getItem('currentTab') || 'download';
        this.selectedUrls = new Set();
        this.selectedVideos = new Set();
        this.selectedFinishedVideos = new Set();
        this.selectedThumbnails = new Set();
        this.isProcessing = false;
        this.progress = {
            download: 0,
            transcribe: 0,
            upload: 0
        };
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.restoreSavedTab();
        this.loadInitialData();
        this.updateStatusPanel();
    }

    setupEventListeners() {
        // Tab navigation
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tab = e.currentTarget.dataset.tab;
                this.switchTab(tab);
            });
        });

        // Theme toggle
        document.getElementById('themeToggle').addEventListener('click', () => {
            this.toggleTheme();
        });

        // Master run button
        document.getElementById('masterRunBtn').addEventListener('click', () => {
            this.runAllProcesses();
        });

        // Download tab events
        document.getElementById('refreshUrls').addEventListener('click', () => {
            this.loadUrls();
        });
        document.getElementById('selectAllUrls').addEventListener('click', () => {
            this.selectAllUrls();
        });
        document.getElementById('startDownload').addEventListener('click', () => {
            this.startDownload();
        });
        document.getElementById('nextToTranscribe').addEventListener('click', () => {
            this.switchTab('transcribe');
        });

        // Transcribe tab events
        document.getElementById('refreshVideos').addEventListener('click', () => {
            this.loadVideos();
        });
        document.getElementById('selectAllVideos').addEventListener('click', () => {
            this.selectAllVideos();
        });
        document.getElementById('startTranscribe').addEventListener('click', () => {
            this.startTranscribe();
        });
        document.getElementById('nextToUpload').addEventListener('click', () => {
            this.switchTab('upload');
        });

        // Upload tab events
        document.getElementById('refreshFinishedVideos').addEventListener('click', () => {
            this.loadFinishedVideos();
        });
        document.getElementById('selectAllFinishedVideos').addEventListener('click', () => {
            this.selectAllFinishedVideos();
        });
        document.getElementById('startUpload').addEventListener('click', () => {
            this.startUpload();
        });

        // Custom URL input
        document.getElementById('addCustomUrlBtn').addEventListener('click', () => {
            this.addCustomUrl();
        });
        document.getElementById('customUrlInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.addCustomUrl();
            }
        });

        // Thumbnails events
        document.getElementById('refreshThumbnails').addEventListener('click', () => {
            this.loadThumbnails();
        });
        document.getElementById('selectAllThumbnails').addEventListener('click', () => {
            this.selectAllThumbnails();
        });
        document.getElementById('toggleThumbnails').addEventListener('click', () => {
            this.toggleThumbnails();
        });

        // Data refresh events
        document.getElementById('refreshDownloadData').addEventListener('click', () => {
            this.loadDownloadData();
        });
        document.getElementById('refreshTranscribeData').addEventListener('click', () => {
            this.loadTranscribeData();
        });
        document.getElementById('refreshUploadData').addEventListener('click', () => {
            this.loadUploadData();
        });

        // View toggle events
        document.getElementById('downloadDbView').addEventListener('click', () => {
            this.toggleDataView('download', 'db');
        });
        document.getElementById('downloadSheetView').addEventListener('click', () => {
            this.toggleDataView('download', 'sheet');
        });
        document.getElementById('transcribeDbView').addEventListener('click', () => {
            this.toggleDataView('transcribe', 'db');
        });
        document.getElementById('transcribeSheetView').addEventListener('click', () => {
            this.toggleDataView('transcribe', 'sheet');
        });
        document.getElementById('uploadDbView').addEventListener('click', () => {
            this.toggleDataView('upload', 'db');
        });
        document.getElementById('uploadSheetView').addEventListener('click', () => {
            this.toggleDataView('upload', 'sheet');
        });
        document.getElementById('completeProcess').addEventListener('click', () => {
            this.completeProcess();
        });

        // Status panel toggles
        document.getElementById('toggleProcessStatus').addEventListener('click', () => {
            this.toggleStatusSection('processStatusContent', 'toggleProcessStatus');
        });
        document.getElementById('toggleSystemStatus').addEventListener('click', () => {
            this.toggleStatusSection('systemStatusContent', 'toggleSystemStatus');
        });
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        // Update tab panels
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        document.getElementById(`${tabName}Tab`).classList.add('active');

        this.currentTab = tabName;
        
        // Save current tab to localStorage
        localStorage.setItem('currentTab', tabName);

        // Load data for the new tab
        switch(tabName) {
            case 'download':
                this.loadUrls();
                break;
            case 'transcribe':
                this.loadVideos();
                break;
            case 'upload':
                this.loadFinishedVideos();
                break;
        }
    }

    restoreSavedTab() {
        // Restore the saved tab on page load
        const savedTab = localStorage.getItem('currentTab') || 'download';
        const validTabs = ['download', 'transcribe', 'upload'];
        
        // Validate the saved tab
        if (validTabs.includes(savedTab)) {
            this.switchTab(savedTab);
        } else {
            // If invalid tab, default to download
            this.switchTab('download');
        }
    }

    clearSavedTab() {
        // Clear the saved tab (useful for debugging)
        localStorage.removeItem('currentTab');
        this.switchTab('download');
    }

    async loadInitialData() {
        await this.loadUrls();
        await this.loadVideos();
        await this.loadFinishedVideos();
        await this.loadThumbnails();
        await this.loadDownloadData();
        await this.loadTranscribeData();
        await this.loadUploadData();
        this.updateStatusPanel();
    }

    async loadUrls() {
        try {
            const response = await fetch('/api/urls');
            const data = await response.json();
            this.displayUrls(data.urls);
        } catch (error) {
            this.showToast('Error loading URLs', 'error');
            console.error('Error loading URLs:', error);
        }
    }

    displayUrls(urls) {
        const urlList = document.getElementById('urlList');
        urlList.innerHTML = '';

        urls.forEach((url, index) => {
            const urlItem = document.createElement('div');
            urlItem.className = 'url-item';
            urlItem.innerHTML = `
                <input type="checkbox" class="url-checkbox" data-url="${url}" id="url-${index}">
                <div class="url-text">${url}</div>
                <div class="url-status">
                    <span class="status-badge pending">Pending</span>
                </div>
            `;

            // Add event listener for checkbox
            const checkbox = urlItem.querySelector('.url-checkbox');
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.selectedUrls.add(url);
                } else {
                    this.selectedUrls.delete(url);
                }
                this.updateSelectionInfo();
            });

            urlList.appendChild(urlItem);
        });

        this.updateSelectionInfo();
    }

    selectAllUrls() {
        const checkboxes = document.querySelectorAll('.url-checkbox');
        const allSelected = Array.from(checkboxes).every(cb => cb.checked);
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = !allSelected;
            const url = checkbox.dataset.url;
            if (!allSelected) {
                this.selectedUrls.add(url);
            } else {
                this.selectedUrls.delete(url);
            }
        });
        
        this.updateSelectionInfo();
    }

    updateSelectionInfo() {
        const count = this.selectedUrls.size;
        const maxWarning = count > 5 ? 'Maximum 5 videos per run' : '';
        
        document.querySelector('.selection-count').textContent = `${count} URLs selected`;
        document.querySelector('.max-warning').textContent = maxWarning;
        document.querySelector('.max-warning').style.color = count > 5 ? 'var(--error-color)' : 'var(--warning-color)';
    }

    async startDownload() {
        if (this.selectedUrls.size === 0) {
            this.showToast('Please select at least one URL', 'warning');
            return;
        }

        if (this.selectedUrls.size > 5) {
            this.showToast('Maximum 5 videos per run', 'error');
            return;
        }

        this.isProcessing = true;
        this.showLoadingOverlay('Starting download...');

        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    urls: Array.from(this.selectedUrls)
                })
            });

            const data = await response.json();
            
            if (data.success) {
                this.showToast('Download started successfully', 'success');
                this.updateDatabaseStatus('updating');
                this.trackDownloadProgress(data.taskId);
            } else {
                this.showToast(data.error || 'Download failed', 'error');
            }
        } catch (error) {
            this.showToast('Error starting download', 'error');
            console.error('Download error:', error);
        } finally {
            this.hideLoadingOverlay();
            this.isProcessing = false;
        }
    }

    async trackDownloadProgress(taskId) {
        const progressSection = document.getElementById('downloadProgressSection');
        const progressGrid = document.getElementById('downloadProgressGrid');
        
        progressSection.style.display = 'block';
        progressGrid.innerHTML = '';

        // Simulate progress tracking
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/progress/${taskId}`);
                const data = await response.json();
                
                this.updateDownloadProgress(data);
                
                if (data.completed) {
                    clearInterval(interval);
                    this.showToast('Download completed', 'success');
                    this.updateDatabaseStatus('updated');
                    this.loadVideos(); // Refresh video list
                }
            } catch (error) {
                console.error('Progress tracking error:', error);
                clearInterval(interval);
            }
        }, 1000);
    }

    updateDownloadProgress(progressData) {
        const progressGrid = document.getElementById('downloadProgressGrid');
        progressGrid.innerHTML = '';

        progressData.items.forEach(item => {
            const progressItem = document.createElement('div');
            progressItem.className = `progress-item ${item.status}`;
            progressItem.innerHTML = `
                <div class="progress-details">
                    <div class="progress-title">${item.title}</div>
                    <div class="progress-status">${item.status}</div>
                    <div class="progress-bar-item">
                        <div class="progress-bar-fill" style="width: ${item.progress}%"></div>
                    </div>
                </div>
                <div class="progress-percentage">${item.progress}%</div>
            `;
            progressGrid.appendChild(progressItem);
        });
    }

    async loadVideos() {
        try {
            const response = await fetch('/api/videos');
            const data = await response.json();
            this.displayVideos(data.videos);
            this.updateProcessStatus('download', data.videos.length);
        } catch (error) {
            this.showToast('Error loading videos', 'error');
            console.error('Error loading videos:', error);
        }
    }

    displayVideos(videos) {
        const videoList = document.getElementById('videoList');
        videoList.innerHTML = '';

        videos.forEach((video, index) => {
            const videoItem = document.createElement('div');
            videoItem.className = 'video-item';
            videoItem.innerHTML = `
                <input type="checkbox" class="video-checkbox" data-video-id="${video.id}" id="video-${index}">
                <img src="${video.thumbnail || '/placeholder-thumbnail.jpg'}" alt="Thumbnail" class="video-thumbnail">
                <div class="video-info">
                    <div class="video-title">${video.title}</div>
                    <div class="video-meta">
                        <span>Duration: ${video.duration}</span>
                        <span>Size: ${video.size}</span>
                        <span>Status: ${video.status}</span>
                    </div>
                </div>
                <div class="video-actions">
                    <span class="status-badge ${video.transcriptionStatus}">${video.transcriptionStatus}</span>
                </div>
            `;

            // Add event listener for checkbox
            const checkbox = videoItem.querySelector('.video-checkbox');
            checkbox.addEventListener('change', (e) => {
                this.toggleVideoSelection(video.id, e.target.checked);
            });

            videoList.appendChild(videoItem);
        });

        this.updateVideoSelectionInfo();
    }

    toggleVideoSelection(videoId, checked) {
        if (checked) {
            this.selectedVideos.add(videoId);
        } else {
            this.selectedVideos.delete(videoId);
        }
        this.updateVideoSelectionInfo();
    }

    selectAllVideos() {
        const checkboxes = document.querySelectorAll('.video-checkbox');
        const allSelected = Array.from(checkboxes).every(checkbox => checkbox.checked);
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = !allSelected;
            const videoId = checkbox.dataset.videoId;
            if (!allSelected) {
                this.selectedVideos.add(videoId);
            } else {
                this.selectedVideos.delete(videoId);
            }
        });
        
        this.updateVideoSelectionInfo();
    }

    updateVideoSelectionInfo() {
        const count = this.selectedVideos.size;
        document.querySelector('#transcribeTab .selection-count').textContent = `${count} videos selected`;
    }

    async startTranscribe() {
        if (this.selectedVideos.size === 0) {
            this.showToast('Please select at least one video', 'warning');
            return;
        }

        this.isProcessing = true;
        this.showLoadingOverlay('Starting transcription...');

        try {
            const response = await fetch('/api/transcribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    videoIds: Array.from(this.selectedVideos)
                })
            });

            const data = await response.json();
            
            if (data.success) {
                this.showToast('Transcription started successfully', 'success');
                this.updateDatabaseStatus('updating');
                this.trackTranscribeProgress(data.taskId);
            } else {
                this.showToast(data.error || 'Transcription failed', 'error');
            }
        } catch (error) {
            this.showToast('Error starting transcription', 'error');
            console.error('Transcription error:', error);
        } finally {
            this.hideLoadingOverlay();
            this.isProcessing = false;
        }
    }

    async trackTranscribeProgress(taskId) {
        const progressSection = document.getElementById('transcribeProgressSection');
        const progressGrid = document.getElementById('transcribeProgressGrid');
        
        progressSection.style.display = 'block';
        progressGrid.innerHTML = '';

        // Simulate progress tracking
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/progress/${taskId}`);
                const data = await response.json();
                
                this.updateTranscribeProgress(data);
                
                if (data.completed) {
                    clearInterval(interval);
                    this.showToast('Transcription completed', 'success');
                    this.updateDatabaseStatus('updated');
                    this.updateProcessStatus('transcribe', this.selectedVideos.size);
                    this.loadFinishedVideos(); // Refresh finished videos
                }
            } catch (error) {
                console.error('Progress tracking error:', error);
                clearInterval(interval);
            }
        }, 1000);
    }

    updateTranscribeProgress(progressData) {
        const progressGrid = document.getElementById('transcribeProgressGrid');
        progressGrid.innerHTML = '';

        // Check if progressData and items exist
        if (!progressData || !progressData.items || !Array.isArray(progressData.items)) {
            console.error('Invalid progress data:', progressData);
            progressGrid.innerHTML = '<div class="progress-item error">No progress data available</div>';
            return;
        }

        progressData.items.forEach(item => {
            const progressItem = document.createElement('div');
            progressItem.className = `progress-item ${item.status}`;
            progressItem.innerHTML = `
                <div class="progress-details">
                    <div class="progress-title">${item.title}</div>
                    <div class="progress-status">${item.status}</div>
                    <div class="progress-bar-item">
                        <div class="progress-bar-fill" style="width: ${item.progress}%"></div>
                    </div>
                </div>
                <div class="progress-percentage">${item.progress}%</div>
            `;
            progressGrid.appendChild(progressItem);
        });
    }

    async loadFinishedVideos() {
        try {
            const response = await fetch('/api/finished-videos');
            const data = await response.json();
            this.displayFinishedVideos(data.videos);
        } catch (error) {
            this.showToast('Error loading finished videos', 'error');
            console.error('Error loading finished videos:', error);
        }
    }

    displayFinishedVideos(videos) {
        const videoList = document.getElementById('finishedVideoList');
        videoList.innerHTML = '';

        videos.forEach((video, index) => {
            const videoItem = document.createElement('div');
            videoItem.className = 'video-item';
            videoItem.innerHTML = `
                <input type="checkbox" class="video-checkbox" data-video-id="${video.id}" id="finished-video-${index}">
                <img src="${video.thumbnail || '/placeholder-thumbnail.jpg'}" alt="Thumbnail" class="video-thumbnail">
                <div class="video-info">
                    <div class="video-title">${video.title}</div>
                    <div class="video-meta">
                        <span>Duration: ${video.duration}</span>
                        <span>Size: ${video.size}</span>
                        <span>Status: ${video.uploadStatus}</span>
                    </div>
                </div>
                <div class="video-actions">
                    <span class="status-badge ${video.uploadStatus}">${video.uploadStatus}</span>
                </div>
            `;

            // Add event listener for checkbox
            const checkbox = videoItem.querySelector('.video-checkbox');
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.selectedFinishedVideos.add(video.id);
                } else {
                    this.selectedFinishedVideos.delete(video.id);
                }
                this.updateFinishedVideoSelectionInfo();
            });

            videoList.appendChild(videoItem);
        });

        this.updateFinishedVideoSelectionInfo();
    }

    selectAllFinishedVideos() {
        const checkboxes = document.querySelectorAll('.video-checkbox');
        const allSelected = Array.from(checkboxes).every(cb => cb.checked);
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = !allSelected;
            const videoId = checkbox.dataset.videoId;
            if (!allSelected) {
                this.selectedFinishedVideos.add(videoId);
            } else {
                this.selectedFinishedVideos.delete(videoId);
            }
        });
        
        this.updateFinishedVideoSelectionInfo();
    }

    updateFinishedVideoSelectionInfo() {
        const count = this.selectedFinishedVideos.size;
        document.querySelector('#uploadTab .selection-count').textContent = `${count} videos selected`;
    }

    async startUpload() {
        if (this.selectedFinishedVideos.size === 0) {
            this.showToast('Please select at least one video', 'warning');
            return;
        }

        this.isProcessing = true;
        this.showLoadingOverlay('Starting upload...');

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    videoIds: Array.from(this.selectedFinishedVideos)
                })
            });

            const data = await response.json();
            
            if (data.success) {
                this.showToast('Upload started successfully', 'success');
                this.updateDatabaseStatus('updating');
                this.trackUploadProgress(data.taskId);
            } else {
                this.showToast(data.error || 'Upload failed', 'error');
            }
        } catch (error) {
            this.showToast('Error starting upload', 'error');
            console.error('Upload error:', error);
        } finally {
            this.hideLoadingOverlay();
            this.isProcessing = false;
        }
    }

    async trackUploadProgress(taskId) {
        const progressSection = document.getElementById('uploadProgressSection');
        const progressGrid = document.getElementById('uploadProgressGrid');
        
        progressSection.style.display = 'block';
        progressGrid.innerHTML = '';

        // Simulate progress tracking
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/progress/${taskId}`);
                const data = await response.json();
                
                this.updateUploadProgress(data);
                
                if (data.completed) {
                    clearInterval(interval);
                    this.showToast('Upload completed', 'success');
                    this.updateDatabaseStatus('updated');
                    this.updateProcessStatus('upload', this.selectedFinishedVideos.size);
                    this.updateStatusPanel();
                }
            } catch (error) {
                console.error('Progress tracking error:', error);
                clearInterval(interval);
            }
        }, 1000);
    }

    updateUploadProgress(progressData) {
        const progressGrid = document.getElementById('uploadProgressGrid');
        progressGrid.innerHTML = '';

        progressData.items.forEach(item => {
            const progressItem = document.createElement('div');
            progressItem.className = `progress-item ${item.status}`;
            progressItem.innerHTML = `
                <div class="progress-details">
                    <div class="progress-title">${item.title}</div>
                    <div class="progress-status">${item.status}</div>
                    <div class="progress-bar-item">
                        <div class="progress-bar-fill" style="width: ${item.progress}%"></div>
                    </div>
                </div>
                <div class="progress-percentage">${item.progress}%</div>
            `;
            progressGrid.appendChild(progressItem);
        });
    }

    async runAllProcesses() {
        if (this.isProcessing) {
            this.showToast('Process already running', 'warning');
            return;
        }

        this.isProcessing = true;
        this.showLoadingOverlay('Running all processes...');
        this.updateMasterProgress(0, 'Starting all processes...');

        try {
            // Step 1: Download
            this.updateMasterProgress(10, 'Starting download...');
            await this.startDownload();
            
            // Step 2: Transcribe
            this.updateMasterProgress(50, 'Starting transcription...');
            await this.startTranscribe();
            
            // Step 3: Upload
            this.updateMasterProgress(80, 'Starting upload...');
            await this.startUpload();
            
            this.updateMasterProgress(100, 'All processes completed!');
            this.showToast('All processes completed successfully', 'success');
            
        } catch (error) {
            this.showToast('Error running all processes', 'error');
            console.error('Master process error:', error);
        } finally {
            this.hideLoadingOverlay();
            this.isProcessing = false;
        }
    }

    updateMasterProgress(percentage, text) {
        const progressFill = document.getElementById('masterProgress');
        const progressText = document.getElementById('progressText');
        
        progressFill.style.width = `${percentage}%`;
        progressText.textContent = text;
    }

    // Custom URL functionality
    addCustomUrl() {
        const input = document.getElementById('customUrlInput');
        const url = input.value.trim();
        
        if (!url) {
            this.showToast('Please enter a valid URL', 'error');
            return;
        }
        
        // Add to URL list
        const urlList = document.getElementById('urlList');
        const urlItem = document.createElement('div');
        urlItem.className = 'url-item';
        urlItem.innerHTML = `
            <input type="checkbox" class="url-checkbox" value="${url}">
            <div class="url-content">
                <div class="url-text">${url}</div>
                <div class="url-source">Custom URL</div>
            </div>
        `;
        
        urlList.appendChild(urlItem);
        
        // Clear input
        input.value = '';
        
        // Add event listener for checkbox
        const checkbox = urlItem.querySelector('.url-checkbox');
        checkbox.addEventListener('change', (e) => {
            this.toggleUrlSelection(e.target.value, e.target.checked);
        });
        
        this.showToast('Custom URL added successfully!', 'success');
    }

    // Thumbnails functionality
    async loadThumbnails() {
        try {
            const response = await fetch('/api/thumbnails');
            const data = await response.json();
            
            if (data.success) {
                this.renderThumbnails(data.thumbnails);
            } else {
                this.showToast('Failed to load thumbnails', 'error');
            }
        } catch (error) {
            console.error('Error loading thumbnails:', error);
            this.showToast('Error loading thumbnails', 'error');
        }
    }

    renderThumbnails(thumbnails) {
        const thumbnailList = document.getElementById('thumbnailList');
        thumbnailList.innerHTML = '';
        
        thumbnails.forEach(thumbnail => {
            const thumbnailItem = document.createElement('div');
            thumbnailItem.className = 'thumbnail-item';
            thumbnailItem.dataset.thumbnailId = thumbnail.id;
            
            thumbnailItem.innerHTML = `
                <div class="thumbnail-checkbox">
                    <i class="fas fa-check" style="display: none;"></i>
                </div>
                <img src="${thumbnail.thumbnail}" alt="${thumbnail.filename}" class="thumbnail-preview" onerror="this.src='/placeholder-thumbnail.jpg'">
                <div class="thumbnail-info">
                    <div class="thumbnail-filename">${thumbnail.filename}</div>
                    <div class="thumbnail-size">${thumbnail.size}</div>
                </div>
            `;
            
            thumbnailItem.addEventListener('click', () => {
                this.toggleThumbnailSelection(thumbnail.id);
            });
            
            thumbnailList.appendChild(thumbnailItem);
        });
        
        this.updateThumbnailSelectionCount();
    }

    toggleThumbnailSelection(thumbnailId) {
        const thumbnailItem = document.querySelector(`[data-thumbnail-id="${thumbnailId}"]`);
        const checkbox = thumbnailItem.querySelector('.thumbnail-checkbox i');
        
        if (this.selectedThumbnails.has(thumbnailId)) {
            this.selectedThumbnails.delete(thumbnailId);
            thumbnailItem.classList.remove('selected');
            checkbox.style.display = 'none';
        } else {
            this.selectedThumbnails.add(thumbnailId);
            thumbnailItem.classList.add('selected');
            checkbox.style.display = 'block';
        }
        
        this.updateThumbnailSelectionCount();
    }

    selectAllThumbnails() {
        const thumbnailItems = document.querySelectorAll('.thumbnail-item');
        thumbnailItems.forEach(item => {
            const thumbnailId = item.dataset.thumbnailId;
            if (!this.selectedThumbnails.has(thumbnailId)) {
                this.toggleThumbnailSelection(thumbnailId);
            }
        });
    }

    updateThumbnailSelectionCount() {
        const countElement = document.querySelector('#thumbnailList').parentElement.querySelector('.selection-count');
        if (countElement) {
            countElement.textContent = `${this.selectedThumbnails.size} thumbnails selected`;
        }
    }

    toggleThumbnails() {
        const thumbnailList = document.getElementById('thumbnailList');
        const toggleBtn = document.getElementById('toggleThumbnails');
        const toggleText = toggleBtn.querySelector('span');
        const toggleIcon = toggleBtn.querySelector('i');
        
        if (thumbnailList.style.display === 'none') {
            thumbnailList.style.display = 'grid';
            toggleText.textContent = 'Hide Thumbnails';
            toggleIcon.className = 'fas fa-chevron-up';
        } else {
            thumbnailList.style.display = 'none';
            toggleText.textContent = 'Show Thumbnails';
            toggleIcon.className = 'fas fa-chevron-down';
        }
    }

    // View toggle functionality
    toggleDataView(tab, view) {
        // Update button states
        const dbBtn = document.getElementById(`${tab}DbView`);
        const sheetBtn = document.getElementById(`${tab}SheetView`);
        
        if (view === 'db') {
            dbBtn.classList.add('active');
            sheetBtn.classList.remove('active');
        } else {
            sheetBtn.classList.add('active');
            dbBtn.classList.remove('active');
        }
        
        // Reload data with new view
        if (tab === 'download') {
            this.loadDownloadData(view);
        } else if (tab === 'transcribe') {
            this.loadTranscribeData(view);
        } else if (tab === 'upload') {
            this.loadUploadData(view);
        }
    }

    // Data loading methods
    async loadDownloadData(view = 'db') {
        try {
            const response = await fetch('/api/videos');
            const data = await response.json();
            
            if (data.success) {
                this.renderDownloadData(data.videos, view);
            } else {
                this.showToast('Failed to load download data', 'error');
            }
        } catch (error) {
            console.error('Error loading download data:', error);
            this.showToast('Error loading download data', 'error');
        }
    }

    renderDownloadData(videos, view = 'db') {
        const tbody = document.getElementById('downloadDataBody');
        tbody.innerHTML = '';
        
        videos.forEach(video => {
            const row = document.createElement('tr');
            
            if (view === 'db') {
                row.innerHTML = `
                    <td>${video.id}</td>
                    <td>${video.title}</td>
                    <td><span class="status-badge ${video.status.toLowerCase()}">${video.status}</span></td>
                    <td>${video.size}</td>
                    <td>${video.created_at}</td>
                    <td><span class="status-badge success">Synced</span></td>
                    <td><span class="status-badge success">Synced</span></td>
                `;
            } else {
                // Sheet view - show different data
                row.innerHTML = `
                    <td>${video.id}</td>
                    <td>${video.title}</td>
                    <td><span class="status-badge ${video.status.toLowerCase()}">${video.status}</span></td>
                    <td>${video.size}</td>
                    <td>${video.created_at}</td>
                    <td><span class="status-badge success">Google Sheets</span></td>
                    <td><span class="status-badge success">Master Sheet</span></td>
                `;
            }
            
            tbody.appendChild(row);
        });
    }

    async loadTranscribeData(view = 'db') {
        try {
            const response = await fetch('/api/videos');
            const data = await response.json();
            
            if (data.success) {
                this.renderTranscribeData(data.videos, view);
            } else {
                this.showToast('Failed to load transcription data', 'error');
            }
        } catch (error) {
            console.error('Error loading transcription data:', error);
            this.showToast('Error loading transcription data', 'error');
        }
    }

    renderTranscribeData(videos, view = 'db') {
        const tbody = document.getElementById('transcribeDataBody');
        tbody.innerHTML = '';
        
        videos.forEach(video => {
            const transcriptLength = video.transcript ? video.transcript.length : 0;
            const processingTime = video.processingTime || 'N/A';
            
            const row = document.createElement('tr');
            
            if (view === 'db') {
                row.innerHTML = `
                    <td>${video.id}</td>
                    <td>${video.title}</td>
                    <td><span class="status-badge ${video.transcriptionStatus.toLowerCase()}">${video.transcriptionStatus}</span></td>
                    <td>${transcriptLength} chars</td>
                    <td>${processingTime}</td>
                    <td><span class="status-badge success">Synced</span></td>
                    <td><span class="status-badge success">Synced</span></td>
                `;
            } else {
                // Sheet view
                row.innerHTML = `
                    <td>${video.id}</td>
                    <td>${video.title}</td>
                    <td><span class="status-badge ${video.transcriptionStatus.toLowerCase()}">${video.transcriptionStatus}</span></td>
                    <td>${transcriptLength} chars</td>
                    <td>${processingTime}</td>
                    <td><span class="status-badge success">Transcripts Sheet</span></td>
                    <td><span class="status-badge success">Master Sheet</span></td>
                `;
            }
            
            tbody.appendChild(row);
        });
    }

    async loadUploadData(view = 'db') {
        try {
            const response = await fetch('/api/finished-videos');
            const data = await response.json();
            
            if (data.success) {
                this.renderUploadData(data.videos, view);
            } else {
                this.showToast('Failed to load upload data', 'error');
            }
        } catch (error) {
            console.error('Error loading upload data:', error);
            this.showToast('Error loading upload data', 'error');
        }
    }

    renderUploadData(videos, view = 'db') {
        const tbody = document.getElementById('uploadDataBody');
        tbody.innerHTML = '';
        
        videos.forEach(video => {
            const row = document.createElement('tr');
            
            if (view === 'db') {
                row.innerHTML = `
                    <td>${video.id}</td>
                    <td>${video.title}</td>
                    <td><span class="status-badge ${video.uploadStatus.toLowerCase()}">${video.uploadStatus}</span></td>
                    <td><span class="status-badge ${video.uploadStatus.toLowerCase()}">${video.uploadStatus}</span></td>
                    <td><span class="status-badge ${video.uploadStatus.toLowerCase()}">${video.uploadStatus}</span></td>
                    <td>${video.created_at || 'N/A'}</td>
                    <td><span class="status-badge success">Synced</span></td>
                    <td><span class="status-badge success">Synced</span></td>
                `;
            } else {
                // Sheet view
                row.innerHTML = `
                    <td>${video.id}</td>
                    <td>${video.title}</td>
                    <td><span class="status-badge ${video.uploadStatus.toLowerCase()}">${video.uploadStatus}</span></td>
                    <td><span class="status-badge ${video.uploadStatus.toLowerCase()}">${video.uploadStatus}</span></td>
                    <td><span class="status-badge ${video.uploadStatus.toLowerCase()}">${video.uploadStatus}</span></td>
                    <td>${video.created_at || 'N/A'}</td>
                    <td><span class="status-badge success">Master Sheet</span></td>
                    <td><span class="status-badge success">Transcripts Sheet</span></td>
                `;
            }
            
            tbody.appendChild(row);
        });
    }

    async completeProcess() {
        this.showToast('Process completed successfully!', 'success');
        this.updateMasterProgress(100, 'Process completed');
        
        // Reset all selections
        this.selectedUrls.clear();
        this.selectedVideos.clear();
        this.selectedFinishedVideos.clear();
        this.selectedThumbnails.clear();
        
        // Refresh all data
        await this.loadInitialData();
    }

    async updateStatusPanel() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            // Update status indicators
            Object.keys(data.status).forEach(key => {
                const statusElement = document.querySelector(`[data-status="${key}"]`);
                if (statusElement) {
                    statusElement.className = `status-value ${data.status[key]}`;
                }
            });
        } catch (error) {
            console.error('Error updating status panel:', error);
        }
    }

    toggleStatusSection(contentId, toggleId) {
        const statusContent = document.getElementById(contentId);
        const toggleBtn = document.getElementById(toggleId);
        
        if (statusContent.style.display === 'none') {
            statusContent.style.display = 'block';
            toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i>';
        } else {
            statusContent.style.display = 'none';
            toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i>';
        }
    }

    updateProcessStatus(process, count) {
        const statusElement = document.getElementById(`${process}StatusValue`);
        if (statusElement) {
            const icon = statusElement.querySelector('i');
            const span = statusElement.querySelector('span');
            
            if (count > 0) {
                icon.className = 'fas fa-check-circle';
                statusElement.className = 'status-value completed';
                span.textContent = `${count} completed`;
            } else {
                icon.className = 'fas fa-clock';
                statusElement.className = 'status-value pending';
                span.textContent = '0 completed';
            }
        }
    }

    updateDatabaseStatus(status) {
        const dbStatus = document.getElementById('dbUpdateStatus');
        const sheetsStatus = document.getElementById('sheetsUpdateStatus');
        
        if (dbStatus) {
            const icon = dbStatus.querySelector('i');
            const span = dbStatus.querySelector('span');
            
            if (status === 'updated') {
                icon.className = 'fas fa-check-circle';
                dbStatus.className = 'status-value success';
                span.textContent = 'Updated';
            } else if (status === 'updating') {
                icon.className = 'fas fa-sync-alt fa-spin';
                dbStatus.className = 'status-value processing';
                span.textContent = 'Updating...';
            } else {
                icon.className = 'fas fa-check-circle';
                dbStatus.className = 'status-value success';
                span.textContent = 'Up to date';
            }
        }
        
        if (sheetsStatus) {
            const icon = sheetsStatus.querySelector('i');
            const span = sheetsStatus.querySelector('span');
            
            if (status === 'updated') {
                icon.className = 'fas fa-check-circle';
                sheetsStatus.className = 'status-value success';
                span.textContent = 'Updated';
            } else if (status === 'updating') {
                icon.className = 'fas fa-sync-alt fa-spin';
                sheetsStatus.className = 'status-value processing';
                span.textContent = 'Updating...';
            } else {
                icon.className = 'fas fa-check-circle';
                sheetsStatus.className = 'status-value success';
                span.textContent = 'Up to date';
            }
        }
    }

    toggleTheme() {
        const body = document.body;
        const currentTheme = body.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        body.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        const themeIcon = document.querySelector('#themeToggle i');
        themeIcon.className = newTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }

    showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = this.getToastIcon(type);
        toast.innerHTML = `
            <i class="${icon}"></i>
            <span>${message}</span>
        `;
        
        toastContainer.appendChild(toast);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            toast.remove();
        }, 5000);
    }

    getToastIcon(type) {
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };
        return icons[type] || icons.info;
    }

    showLoadingOverlay(text = 'Processing...') {
        const overlay = document.getElementById('loadingOverlay');
        const loadingText = document.getElementById('loadingText');
        
        loadingText.textContent = text;
        overlay.style.display = 'flex';
    }

    hideLoadingOverlay() {
        const overlay = document.getElementById('loadingOverlay');
        overlay.style.display = 'none';
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new SocialMediaProcessor();
    
    // Load saved theme
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.setAttribute('data-theme', savedTheme);
    
    const themeIcon = document.querySelector('#themeToggle i');
    themeIcon.className = savedTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
});
