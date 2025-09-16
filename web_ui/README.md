# Social Media Content Processor - Web UI

A beautiful, modern web interface for the Social Media Content Processor with three main tabs: Download, Transcribe, and Upload.

## 🎨 Features

### Modern Design
- **Responsive Layout**: Works on desktop, tablet, and mobile
- **Dark/Light Theme**: Toggle between themes
- **Beautiful UI**: Modern CSS with smooth animations
- **Real-time Updates**: Live progress tracking and status updates

### Three Main Tabs

#### 1. Download Tab
- **URL Selection**: Choose which URLs to download from `urls.txt`
- **Batch Selection**: Select all or individual URLs
- **Progress Tracking**: Real-time download progress
- **Status Indicators**: Clear status for each download
- **Max Limit Warning**: Warns when more than 5 videos selected

#### 2. Transcribe Tab
- **Video Selection**: Choose downloaded videos to transcribe
- **GPU Detection**: Shows GPU availability for faster processing
- **Progress Tracking**: Real-time transcription progress
- **Status Updates**: Clear status for each transcription

#### 3. Upload Tab
- **Finished Videos**: Select videos from `assets/finished_videos/`
- **Multi-Platform Upload**: Uploads to both Google Drive and AIWaverider
- **Progress Tracking**: Real-time upload progress
- **Duplicate Prevention**: Smart duplicate checking

### Master Control
- **Run All Processes**: Single button to run download → transcribe → upload
- **Progress Tracking**: Overall progress bar and status
- **Error Handling**: Graceful error handling and recovery

### Status Panel
- **System Status**: Database, Google Sheets, AIWaverider, GPU status
- **Real-time Updates**: Live status monitoring
- **Health Indicators**: Visual status indicators

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Virtual environment activated
- Main project dependencies installed

### Installation
```bash
# Navigate to web UI directory
cd web_ui

# Install web UI requirements
pip install -r requirements.txt

# Start the web server
python app.py
```

### Windows Users
```bash
# Use the batch file
start_web_ui.bat
```

### Access the UI
Open your browser and go to: `http://localhost:5000`

## 📁 File Structure

```
web_ui/
├── index.html              # Main HTML structure
├── styles.css              # Modern CSS design system
├── script.js               # Frontend JavaScript functionality
├── app.py                  # Flask backend API server
├── requirements.txt        # Python dependencies
├── start_web_ui.bat       # Windows startup script
├── placeholder-thumbnail.jpg # Placeholder image
└── README.md              # This file
```

## 🎯 Usage

### Download Videos
1. Go to the **Download** tab
2. Select URLs from the list (max 5 per run)
3. Click **Start Download**
4. Monitor progress in real-time
5. View downloaded videos below

### Transcribe Videos
1. Go to the **Transcribe** tab
2. Select downloaded videos to transcribe
3. Click **Start Transcription**
4. Monitor progress with GPU status
5. View transcribed videos below

### Upload Videos
1. Go to the **Upload** tab
2. Select finished videos from `assets/finished_videos/`
3. Click **Start Upload**
4. Monitor upload progress to both platforms
5. View uploaded videos below

### Run All Processes
1. Click **Run All Processes** in the header
2. Monitor overall progress
3. System will automatically run download → transcribe → upload
4. View final results

## 🎨 Design Features

### Color Scheme
- **Primary**: Indigo (#6366f1)
- **Success**: Emerald (#10b981)
- **Warning**: Amber (#f59e0b)
- **Error**: Red (#ef4444)
- **Neutral**: Gray scale

### Typography
- **Font**: Inter (Google Fonts)
- **Weights**: 300, 400, 500, 600, 700
- **Responsive**: Scales with screen size

### Components
- **Cards**: Rounded corners with subtle shadows
- **Buttons**: Hover effects and smooth transitions
- **Progress Bars**: Animated progress indicators
- **Status Badges**: Color-coded status indicators
- **Toast Notifications**: Slide-in notifications

### Responsive Design
- **Mobile First**: Optimized for mobile devices
- **Breakpoints**: 768px, 1024px
- **Grid Layout**: CSS Grid and Flexbox
- **Touch Friendly**: Large touch targets

## 🔧 API Endpoints

### URLs
- `GET /api/urls` - Get URLs from urls.txt
- `GET /api/videos` - Get downloaded videos
- `GET /api/finished-videos` - Get finished videos

### Processing
- `POST /api/download` - Start download process
- `POST /api/transcribe` - Start transcription process
- `POST /api/upload` - Start upload process

### Status
- `GET /api/progress/<task_id>` - Get task progress
- `GET /api/status` - Get system status

### Static Files
- `GET /thumbnails/<filename>` - Serve thumbnail images

## 🛠️ Customization

### Themes
The UI supports dark and light themes. Toggle using the theme button in the header.

### Colors
Modify CSS custom properties in `styles.css`:
```css
:root {
    --primary-color: #6366f1;
    --success-color: #10b981;
    /* ... other colors */
}
```

### Layout
Adjust grid layouts and spacing:
```css
.app-container {
    grid-template-columns: 1fr 300px;
    gap: var(--space-6);
}
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Server Won't Start
- Check if port 5000 is available
- Ensure virtual environment is activated
- Install requirements: `pip install -r requirements.txt`

#### 2. API Errors
- Check if main project is properly configured
- Verify database connection
- Check Google API credentials

#### 3. UI Not Loading
- Clear browser cache
- Check browser console for errors
- Ensure all files are in the correct location

#### 4. Progress Not Updating
- Check network connection
- Verify API endpoints are responding
- Check browser console for JavaScript errors

### Debug Mode
Enable debug mode by setting `debug=True` in `app.py`:
```python
app.run(debug=True)
```

## 📱 Mobile Support

The UI is fully responsive and works on:
- **Desktop**: Full feature set
- **Tablet**: Optimized layout
- **Mobile**: Touch-friendly interface

## 🔒 Security

- **CORS**: Configured for local development
- **Input Validation**: All inputs are validated
- **Error Handling**: Graceful error handling
- **Rate Limiting**: Built-in rate limiting (TODO)

## 🚀 Performance

- **Lazy Loading**: Images load on demand
- **Efficient Updates**: Only update changed elements
- **Caching**: Browser caching for static assets
- **Compression**: Gzip compression for API responses

## 📈 Future Enhancements

- [ ] Real-time WebSocket updates
- [ ] Advanced filtering and search
- [ ] Batch operations
- [ ] Export/import functionality
- [ ] User authentication
- [ ] Multi-user support
- [ ] Advanced analytics
- [ ] Custom themes
- [ ] Keyboard shortcuts
- [ ] Offline support

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the main project LICENSE file for details.

---

**Note**: This web UI is designed to work with the existing Social Media Content Processor backend. Make sure the main project is properly configured before using the web interface.
