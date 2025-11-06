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
        // Pagination for URL list
        this.urlListCurrentPage = 1;
        this.urlListItemsPerPage = 4;
        this.urlListAllItems = [];
        
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
        document.getElementById('refreshUrlsTable').addEventListener('click', () => {
            this.loadUrlsTable();
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
        document.getElementById('uploadThumbnails').addEventListener('click', () => {
            this.uploadThumbnails();
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
        await this.loadUrlsTable();
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
            // Reset to page 1 when loading URLs
            this.urlListCurrentPage = 1;
            const response = await fetch('/api/urls');
            const data = await response.json();
            // Use urls_with_metadata to get status information
            const urlsWithMetadata = data.urls_with_metadata || [];
            this.displayUrls(urlsWithMetadata);
        } catch (error) {
            this.showToast('Error loading URLs', 'error');
            console.error('Error loading URLs:', error);
        }
    }

    async loadUrlsTable() {
        try {
            const response = await fetch('/api/urls');
            const data = await response.json();
            
            // Debug logging
            console.log('URLs API response:', data);
            console.log('URLs with metadata:', data.urls_with_metadata);
            
            if (!data.success) {
                console.error('API returned error:', data.error);
                this.showToast(`Error loading URLs: ${data.error}`, 'error');
                return;
            }
            
            const urlsWithMetadata = data.urls_with_metadata || [];
            console.log(`Displaying ${urlsWithMetadata.length} URLs in table`);
            
            this.displayUrlsTable(urlsWithMetadata);
        } catch (error) {
            this.showToast('Error loading URLs table', 'error');
            console.error('Error loading URLs table:', error);
        }
    }

    displayUrlsTable(urls) {
        const tbody = document.getElementById('urlsTableBody');
        if (!tbody) return;
        
        tbody.innerHTML = '';

        if (!urls || urls.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">No URLs found</td></tr>';
            return;
        }

        urls.forEach((urlData) => {
            const url = typeof urlData === 'string' ? urlData : urlData.url || '';
            const source = urlData.source || 'file';
            // Check both download_status and status fields
            const downloadStatus = urlData.download_status || urlData.downloadStatus || urlData.status || 'PENDING';
            
            // Parse date added - handle SQLite format "YYYY-MM-DD HH:MM:SS"
            let dateAdded = '-';
            if (urlData.created_at) {
                try {
                    // SQLite format: "2025-11-06 21:37:46" - replace space with T for ISO format
                    let dateStr = urlData.created_at;
                    if (dateStr.includes(' ') && !dateStr.includes('T')) {
                        dateStr = dateStr.replace(' ', 'T');
                    }
                    const date = new Date(dateStr);
                    if (!isNaN(date.getTime())) {
                        dateAdded = date.toLocaleDateString();
                    } else {
                        // Try Date.parse as fallback
                        const parsed = Date.parse(urlData.created_at);
                        if (!isNaN(parsed)) {
                            dateAdded = new Date(parsed).toLocaleDateString();
                        } else {
                            dateAdded = urlData.created_at; // Fallback to raw value
                        }
                    }
                } catch (e) {
                    dateAdded = urlData.created_at || '-';
                }
            }
            
            // Handle both downloaded_at formats - SQLite format "YYYY-MM-DD HH:MM:SS" or ISO
            let dateDownloaded = '-';
            if (urlData.downloaded_at) {
                try {
                    // SQLite format: "2025-11-06 21:37:46" - replace space with T for ISO format
                    let dateStr = urlData.downloaded_at;
                    if (dateStr.includes(' ') && !dateStr.includes('T')) {
                        dateStr = dateStr.replace(' ', 'T');
                    }
                    const date = new Date(dateStr);
                    if (!isNaN(date.getTime())) {
                        dateDownloaded = date.toLocaleDateString();
                    } else {
                        const parsed = Date.parse(urlData.downloaded_at);
                        if (!isNaN(parsed)) {
                            dateDownloaded = new Date(parsed).toLocaleDateString();
                        } else {
                            dateDownloaded = urlData.downloaded_at;
                        }
                    }
                } catch (e) {
                    dateDownloaded = urlData.downloaded_at || '-';
                }
            }
            
            // Extract video_id from URL if not provided
            let videoId = urlData.video_id;
            if (!videoId && url) {
                // Try to extract video ID from URL (Instagram, YouTube, etc.)
                const instagramMatch = url.match(/\/reel\/([A-Za-z0-9_-]+)/);
                const youtubeMatch = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([A-Za-z0-9_-]{11})/);
                videoId = instagramMatch ? instagramMatch[1] : (youtubeMatch ? youtubeMatch[1] : null);
            }
            
            // Check multiple possible fields for video name
            let videoName = urlData.video_name || urlData.video_filename || urlData.smart_name;
            
            // If no video name but we have video_id, try to construct a name from the URL
            if (!videoName && videoId) {
                // Extract username/creator from URL if possible
                const urlParts = url.split('/');
                const reelIndex = urlParts.findIndex(part => part === 'reel');
                if (reelIndex > 0) {
                    const username = urlParts[reelIndex - 1];
                    videoName = `${username} ${videoId}`;
                } else {
                    videoName = videoId;
                }
            }
            
            if (!videoName) {
                videoName = '-';
            }
            
            // Handle transcription status - prioritize urls table, then video_transcripts
            // The query returns transcription_status from COALESCE, so it should be available
            let transcriptionStatus = 'N/A';
            if (urlData.transcription_status) {
                transcriptionStatus = urlData.transcription_status;
            } else if (urlData.video_id) {
                // If we have video_id but no transcription_status, check if it's in the database
                // This is a fallback - the JOIN should have provided it
                transcriptionStatus = 'PENDING';
            }
            
            // Debug log to see what data we're getting
            if (!urlData.video_name || urlData.transcription_status === 'N/A' || dateAdded === 'Invalid Date') {
                console.log('URL data debug:', {
                    url: url.substring(0, 50),
                    video_id: urlData.video_id,
                    video_name: urlData.video_name,
                    transcription_status: urlData.transcription_status,
                    created_at: urlData.created_at,
                    all_keys: Object.keys(urlData)
                });
            }

            const row = document.createElement('tr');
            row.innerHTML = `
                <td title="${url}">${url.length > 50 ? url.substring(0, 50) + '...' : url}</td>
                <td>${source}</td>
                <td><span class="status-badge ${downloadStatus.toLowerCase()}">${downloadStatus}</span></td>
                <td>${dateAdded}</td>
                <td>${dateDownloaded}</td>
                <td>${videoName}</td>
                <td><span class="status-badge ${transcriptionStatus.toLowerCase().replace(' ', '-')}">${transcriptionStatus}</span></td>
            `;
            tbody.appendChild(row);
        });
    }

    displayUrls(urls) {
        const urlList = document.getElementById('urlList');
        urlList.innerHTML = '';

        if (!urls || urls.length === 0) {
            urlList.innerHTML = '<div class="empty-state">No URLs found</div>';
            // Clear pagination
            this.updateUrlListPagination(0);
            return;
        }

        // Store all URLs for pagination
        this.urlListAllItems = urls;
        
        // Separate downloaded and non-downloaded URLs
        const downloadedUrls = [];
        const pendingUrls = [];

        urls.forEach((urlData) => {
            const url = typeof urlData === 'string' ? urlData : urlData.url || '';
            if (!url) return;

            // Check download status
            const downloadStatus = urlData.download_status || urlData.downloadStatus || urlData.status || 'PENDING';
            const isDownloaded = downloadStatus === 'DOWNLOADED' || downloadStatus === 'downloaded';

            if (isDownloaded) {
                downloadedUrls.push({ url, urlData, downloadStatus });
            } else {
                pendingUrls.push({ url, urlData, downloadStatus });
            }
        });

        // Sort: pending first, then downloaded
        const sortedUrls = [...pendingUrls, ...downloadedUrls];
        
        // Store sorted URLs for pagination
        this.urlListAllItems = sortedUrls;
        
        // Calculate pagination
        const totalPages = Math.ceil(sortedUrls.length / this.urlListItemsPerPage);
        if (this.urlListCurrentPage > totalPages && totalPages > 0) {
            this.urlListCurrentPage = totalPages;
        }
        
        // Get items for current page
        const startIndex = (this.urlListCurrentPage - 1) * this.urlListItemsPerPage;
        const endIndex = startIndex + this.urlListItemsPerPage;
        const pageItems = sortedUrls.slice(startIndex, endIndex);

        // Display items for current page
        pageItems.forEach((item, index) => {
            const { url, urlData, downloadStatus } = item;
            const isDownloaded = downloadStatus === 'DOWNLOADED' || downloadStatus === 'downloaded';

            const urlItem = document.createElement('div');
            urlItem.className = `url-item ${isDownloaded ? 'downloaded' : ''}`;
            
            // Determine status badge class and text
            let statusClass = 'pending';
            let statusText = 'PENDING';
            if (isDownloaded) {
                statusClass = 'downloaded';
                statusText = 'DOWNLOADED';
            } else if (downloadStatus === 'FAILED' || downloadStatus === 'failed') {
                statusClass = 'failed';
                statusText = 'FAILED';
            }

            // Use actual index from sorted array for unique IDs
            const actualIndex = startIndex + index;
            urlItem.innerHTML = `
                <input type="checkbox" class="url-checkbox" data-url="${url}" id="url-${actualIndex}" ${isDownloaded ? 'disabled' : ''}>
                <div class="url-text ${isDownloaded ? 'strikethrough' : ''}">${url}</div>
                <div class="url-status">
                    <span class="status-badge ${statusClass}">${statusText}</span>
                </div>
            `;

            // Add event listener for checkbox (only if not disabled)
            if (!isDownloaded) {
                const checkbox = urlItem.querySelector('.url-checkbox');
                checkbox.addEventListener('change', (e) => {
                    if (e.target.checked) {
                        this.selectedUrls.add(url);
                    } else {
                        this.selectedUrls.delete(url);
                    }
                    this.updateSelectionInfo();
                });
            }

            urlList.appendChild(urlItem);
        });

        // Update pagination controls
        this.updateUrlListPagination(sortedUrls.length);

        this.updateSelectionInfo();
    }
    
    updateUrlListPagination(totalItems) {
        const paginationContainer = document.getElementById('urlListPagination');
        if (!paginationContainer) return;
        
        const totalPages = Math.ceil(totalItems / this.urlListItemsPerPage);
        
        if (totalPages <= 1) {
            paginationContainer.innerHTML = '';
            return;
        }
        
        const prevDisabled = this.urlListCurrentPage <= 1 ? 'disabled' : '';
        const nextDisabled = this.urlListCurrentPage >= totalPages ? 'disabled' : '';
        
        paginationContainer.innerHTML = `
            <button class="btn btn-outline pagination-btn" id="urlListPrev" ${prevDisabled}>
                <i class="fas fa-chevron-left"></i>
                Previous
            </button>
            <span class="pagination-info">
                Page ${this.urlListCurrentPage} of ${totalPages} (${totalItems} URLs)
            </span>
            <button class="btn btn-outline pagination-btn" id="urlListNext" ${nextDisabled}>
                Next
                <i class="fas fa-chevron-right"></i>
            </button>
        `;
        
        // Add event listeners
        const prevBtn = document.getElementById('urlListPrev');
        const nextBtn = document.getElementById('urlListNext');
        
        if (prevBtn && !prevDisabled) {
            prevBtn.addEventListener('click', () => {
                if (this.urlListCurrentPage > 1) {
                    this.urlListCurrentPage--;
                    this.displayUrls(this.urlListAllItems);
                }
            });
        }
        
        if (nextBtn && !nextDisabled) {
            nextBtn.addEventListener('click', () => {
                const totalPages = Math.ceil(this.urlListAllItems.length / this.urlListItemsPerPage);
                if (this.urlListCurrentPage < totalPages) {
                    this.urlListCurrentPage++;
                    this.displayUrls(this.urlListAllItems);
                }
            });
        }
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

        // Track progress with polling
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/progress/${taskId}`);
                const data = await response.json();
                
                this.updateDownloadProgress(data);
                
                // Check if completed or failed
                if (data.status === 'completed' || data.status === 'failed') {
                    clearInterval(interval);
                    
                    if (data.status === 'completed') {
                        const completed = data.completed || 0;
                        const failed = data.failed || 0;
                        const skipped = data.skipped || 0;
                        let message = `Download completed!`;
                        const parts = [];
                        if (completed > 0) parts.push(`${completed} downloaded`);
                        if (skipped > 0) parts.push(`${skipped} already downloaded`);
                        if (failed > 0) parts.push(`${failed} failed`);
                        if (parts.length > 0) {
                            message += ` (${parts.join(', ')})`;
                        }
                        this.showToast(message, skipped > 0 && completed === 0 ? 'info' : 'success');
                    } else {
                        this.showToast(`Download failed: ${data.error || 'Unknown error'}`, 'error');
                    }
                    
                    this.updateDatabaseStatus('updated');
                    
                    // Refresh data with a small delay to ensure DB is updated
                    setTimeout(() => {
                        this.loadVideos(); // Refresh video list
                        this.loadUrlsTable(); // Refresh URLs table
                    }, 500);
                }
            } catch (error) {
                console.error('Progress tracking error:', error);
                clearInterval(interval);
                this.showToast('Error tracking download progress', 'error');
            }
        }, 1000);
    }

    updateDownloadProgress(progressData) {
        // Update main progress bar
        const progressBar = document.getElementById('downloadProgressBar');
        const progressText = document.getElementById('downloadProgressText');
        const progressPercent = document.getElementById('downloadProgressPercent');
        const completed = document.getElementById('downloadCompleted');
        const failed = document.getElementById('downloadFailed');
        const total = document.getElementById('downloadTotal');
        
        const progress = progressData.progress || 0;
        const status = progressData.status || 'running';
        const message = progressData.message || 'Processing...';
        const completedCount = progressData.completed || 0;
        const failedCount = progressData.failed || 0;
        const totalCount = progressData.total || (progressData.items ? progressData.items.length : 0);
        
        // Update main progress bar
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
            if (status === 'completed') {
                progressBar.style.backgroundColor = '#4caf50';
            } else if (status === 'failed') {
                progressBar.style.backgroundColor = '#f44336';
            } else {
                progressBar.style.backgroundColor = '#2196f3';
            }
        }
        
        if (progressText) progressText.textContent = message;
        if (progressPercent) progressPercent.textContent = `${progress}%`;
        if (completed) completed.textContent = completedCount;
        if (failed) failed.textContent = failedCount;
        if (total) total.textContent = totalCount;
        
        // Update individual video progress
        const progressGrid = document.getElementById('downloadProgressGrid');
        if (!progressGrid) return;
        
        progressGrid.innerHTML = '';
        
        if (progressData.items && progressData.items.length > 0) {
            progressData.items.forEach((item, index) => {
                const progressItem = document.createElement('div');
                progressItem.className = `progress-item ${item.status || 'pending'}`;
                
                const statusText = item.status === 'completed' ? 'Completed' :
                                  item.status === 'failed' ? 'Failed' :
                                  item.status === 'already_downloaded' ? 'Already Downloaded' :
                                  item.status === 'downloading' ? 'Downloading...' :
                                  item.status === 'checking' ? 'Checking...' : 'Pending';
                
                const url = item.title || `Video ${index + 1}`;
                const shortUrl = url.length > 60 ? url.substring(0, 60) + '...' : url;
                
                // Determine color based on status
                let statusColor = '#2196f3'; // Default blue
                if (item.status === 'completed') statusColor = '#4caf50'; // Green
                else if (item.status === 'failed') statusColor = '#f44336'; // Red
                else if (item.status === 'already_downloaded') statusColor = '#ff9800'; // Orange
                
                const message = item.message ? ` - ${item.message}` : '';
                
                progressItem.innerHTML = `
                    <div class="progress-details">
                        <div class="progress-title" title="${url}">${shortUrl}</div>
                        <div class="progress-status">${statusText}${message}</div>
                        <div class="progress-bar-item">
                            <div class="progress-bar-fill" style="width: ${item.progress || 0}%; background-color: ${statusColor}"></div>
                        </div>
                    </div>
                    <div class="progress-percentage">${item.progress || 0}%</div>
                `;
                progressGrid.appendChild(progressItem);
            });
        }
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
                    <span class="status-badge ${video.transcriptionStatus ? video.transcriptionStatus.toLowerCase() : 'pending'}">${video.transcriptionStatus || 'PENDING'}</span>
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
        // Also refresh URLs table when transcription starts/completes
        this.loadUrlsTable();
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
                
                if (data.status === 'completed' || data.status === 'failed') {
                    clearInterval(interval);
                    
                    // Build success message
                    let message = 'Transcription completed';
                    if (data.skipped && data.skipped > 0) {
                        message += ` (${data.skipped} video(s) skipped - already transcribed)`;
                    }
                    if (data.transcribed && data.transcribed > 0) {
                        message += ` - ${data.transcribed} video(s) transcribed`;
                    }
                    
                    // Check for sheets errors
                    if (data.sheets_error) {
                        this.showToast(
                            `${message}, but Google Sheets update failed: ${data.sheets_error}. Data saved to database.`,
                            'warning'
                        );
                    } else {
                        this.showToast(message, 'success');
                    }
                    
                    // Log skipped videos to console
                    if (data.skipped && data.skipped > 0) {
                        console.log(`⏭️ Skipped ${data.skipped} video(s) that were already transcribed`);
                    }
                    
                    this.updateDatabaseStatus('updated');
                    this.updateProcessStatus('transcribe', this.selectedVideos.size);
                    
                    // Refresh data with a small delay to ensure DB is updated
                    setTimeout(() => {
                        this.loadVideos(); // Refresh videos list
                        this.loadUrlsTable(); // Refresh URLs table to show updated transcription status
                    }, 500);
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
                
                if (data.status === 'completed' || data.status === 'failed') {
                    clearInterval(interval);
                    
                    // Check for sheets errors
                    if (data.sheets_error) {
                        this.showToast(
                            `Upload completed, but Google Sheets update failed: ${data.sheets_error}. Data saved to database.`,
                            'warning'
                        );
                    } else {
                        this.showToast('Upload completed', 'success');
                    }
                    
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
    async addCustomUrl() {
        const input = document.getElementById('customUrlInput');
        const url = input.value.trim();
        
        if (!url) {
            this.showToast('Please enter a valid URL', 'error');
            return;
        }
        
        try {
            // Save to backend
            const response = await fetch('/api/urls', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    urls: [url]
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Refresh URL list and URLs table to show new URL
                await this.loadUrls();
                await this.loadUrlsTable();
                
                // Clear input
                input.value = '';
                
                // Show success message with details
                let message = `Custom URL added successfully!`;
                if (data.db_added !== undefined && data.file_added !== undefined) {
                    message += ` (DB: ${data.db_added}, File: ${data.file_added}, Total: ${data.total})`;
                } else {
                    message += ` (${data.added} new, ${data.total} total)`;
                }
                this.showToast(message, 'success');
            } else {
                this.showToast(data.error || 'Failed to save URL', 'error');
            }
        } catch (error) {
            console.error('Error saving URL:', error);
            this.showToast('Error saving URL to file', 'error');
        }
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

    async uploadThumbnails() {
        if (this.selectedThumbnails.size === 0) {
            this.showToast('Please select at least one thumbnail', 'warning');
            return;
        }

        this.isProcessing = true;
        this.showLoadingOverlay('Uploading thumbnails...');

        try {
            const response = await fetch('/api/thumbnails/upload', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    thumbnailIds: Array.from(this.selectedThumbnails)
                })
            });

            const data = await response.json();
            
            if (data.success) {
                // Check for sheets errors
                if (data.sheets_error) {
                    this.showToast(
                        `Thumbnails uploaded, but Google Sheets update failed: ${data.sheets_error}. Data saved to database.`,
                        'warning'
                    );
                } else {
                    this.showToast(`Successfully uploaded ${data.uploaded} thumbnail(s)`, 'success');
                }
                this.selectedThumbnails.clear();
                this.loadThumbnails(); // Refresh thumbnails list
            } else {
                this.showToast(data.error || 'Thumbnail upload failed', 'error');
            }
        } catch (error) {
            this.showToast('Error uploading thumbnails', 'error');
            console.error('Thumbnail upload error:', error);
        } finally {
            this.hideLoadingOverlay();
            this.isProcessing = false;
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
