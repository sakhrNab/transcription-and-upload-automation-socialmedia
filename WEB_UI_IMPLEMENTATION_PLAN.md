# Web UI Implementation Plan - Requirements Analysis

## 📋 User Requirements Summary

1. **Upload Videos**: Stay independent and untouched
2. **Transcription**: Work with `assets/downloads/videos` path (filesystem), independent from upload
3. **Upload Thumbnails**: Manually triggered via API/button
4. **Sheets Updates**: Optional - skip on auth errors, show error to user, DB is enough

---

## 1. ✅ UPLOAD VIDEOS - Independent (Keep As Is)

**Current State:**
- ✅ Already reads from `assets/finished_videos/` (independent)
- ✅ No dependencies on download/transcription
- ⚠️ Backend is TODO/mock - needs real implementation

**What to Do:**
- Keep upload completely independent
- Implement real upload logic (replace TODO)
- No changes to data source or dependencies

**Implementation:**
- Follow `upload_only.py` pattern
- Use `get_finished_videos()` response which already has `path`
- Call upload processors directly

---

## 2. 🎤 TRANSCRIPTION - Filesystem-Based (Major Change Needed)

### Current Problem:
- `app.py` line 70-90: `get_downloaded_videos()` reads from **database**
- User wants: Read from **`assets/downloads/videos`** filesystem

### What Needs to Change:

**Current Code (app.py line 70-90):**
```python
async def get_downloaded_videos(self):
    # Currently reads from DATABASE
    videos = await self.db_manager.get_all_videos()
```

**Should Be (like app_with_db.py line 76-157):**
```python
async def get_downloaded_videos(self):
    # Read from FILESYSTEM: assets/downloads/videos
    videos_dir = Path("assets/downloads/videos")
    videos = []
    for video_file in videos_dir.rglob("*.mp4"):
        # Get file info from filesystem
        # Optionally check database for transcription status
```

### Transcription Process:
1. **Get videos from filesystem** (`assets/downloads/videos/`)
2. **For each video file:**
   - Get file path from filesystem
   - Optionally check database for existing transcription status
   - If not transcribed, process it
3. **Transcribe using video processor methods**
4. **Update database** with transcription results
5. **Update sheets** (optional - skip on error)

### Independence:
- ✅ **FULLY INDEPENDENT** from upload
- ✅ Works with any video files in `assets/downloads/videos/`
- ⚠️ May need to create/update database entry if video not in DB yet

---

## 3. 📸 UPLOAD THUMBNAILS - Manual Trigger

### Current State:
- ✅ `app_with_db.py` has `/api/thumbnails` GET endpoint
- ❌ `app.py` (main) has NO thumbnail endpoint
- ❌ No upload functionality

### What Needs to Be Added:

**1. Add GET endpoint to app.py:**
```python
@app.route('/api/thumbnails', methods=['GET'])
def get_thumbnails():
    # Get thumbnails from assets/downloads/thumbnails/
    thumbnails = asyncio.run(api.get_thumbnails())
    return jsonify({"success": True, "thumbnails": thumbnails})
```

**2. Add POST endpoint for upload:**
```python
@app.route('/api/thumbnails/upload', methods=['POST'])
def upload_thumbnails():
    data = request.get_json()
    thumbnail_ids = data.get('thumbnailIds', [])
    # Upload selected thumbnails
    result = asyncio.run(api.upload_thumbnails(thumbnail_ids))
    return jsonify(result)
```

**3. Add method to WebAPI class:**
```python
async def upload_thumbnails(self, thumbnail_ids):
    # Get thumbnail paths
    # Call upload processors
    await orchestrator.upload_processor._upload_thumbnail_file(...)
    await orchestrator.aiwaverider_processor._upload_thumbnail_to_aiwaverider(...)
```

**4. Update frontend:**
- Add upload button for thumbnails
- Call `/api/thumbnails/upload` on click

---

## 4. 📊 SHEETS UPDATES - Optional with Error Handling

### Current State:
- Sheets processors already have error handling
- But they return `False` on failure, which might stop the process

### What Needs to Change:

**Current Pattern (in standalone scripts):**
```python
sheets_result = await orchestrator.sheets_processor.update_master_sheet()
if not sheets_result:
    print("❌ Sheets update failed")
    # This might be treated as failure
```

**Should Be (for web UI):**
```python
sheets_result = False
sheets_error = None
try:
    sheets_result = await orchestrator.sheets_processor.update_master_sheet()
except Exception as e:
    sheets_error = str(e)
    logger.error(f"Sheets update failed (non-fatal): {e}")

if not sheets_result:
    # Log error but don't fail the process
    error_message = f"Google Sheets update failed: {sheets_error or 'Authentication or connection error'}"
    # Return this in response so frontend can show to user
    return {
        "success": True,  # Process succeeded
        "sheets_error": error_message  # But sheets failed
    }
```

### Implementation Pattern:

**For Transcription:**
```python
# 1. Transcribe video (required)
transcript = await video_processor._transcribe_audio_with_whisper(...)
await video_processor._update_video_transcription(...)  # Update DB

# 2. Update sheets (optional)
sheets_success = False
sheets_error = None
try:
    sheets_success = await orchestrator.sheets_processor.update_master_sheet()
    await orchestrator.transcripts_sheets_processor.update_transcripts_sheet()
except Exception as e:
    sheets_error = str(e)
    logger.error(f"Sheets update failed (non-fatal): {e}")

# Return result with sheets status
return {
    "success": True,  # Transcription succeeded
    "sheets_updated": sheets_success,
    "sheets_error": sheets_error if not sheets_success else None
}
```

**For Upload:**
```python
# 1. Upload video (required)
await upload_processor._upload_video_file(...)
await aiwaverider_processor._upload_video_to_aiwaverider(...)

# 2. Update sheets (optional)
sheets_success = False
sheets_error = None
try:
    sheets_success = await orchestrator.sheets_processor.update_master_sheet()
    await orchestrator.transcripts_sheets_processor.update_transcripts_sheet()
except Exception as e:
    sheets_error = str(e)
    logger.error(f"Sheets update failed (non-fatal): {e}")

# Return result with sheets status
return {
    "success": True,  # Upload succeeded
    "sheets_updated": sheets_success,
    "sheets_error": sheets_error if not sheets_success else None
}
```

**Frontend Handling:**
```javascript
if (data.sheets_error) {
    this.showToast(`Process completed, but sheets update failed: ${data.sheets_error}`, 'warning');
} else {
    this.showToast('Process completed successfully', 'success');
}
```

---

## 📝 Detailed Implementation Checklist

### Transcription Changes:

1. **Change `get_downloaded_videos()` in app.py:**
   - ❌ Remove: Database reading (`get_all_videos()`)
   - ✅ Add: Filesystem reading from `assets/downloads/videos/`
   - ✅ Optionally check database for transcription status
   - ✅ Return file paths, not just IDs

2. **Implement `start_transcribe_process()`:**
   - ✅ Get video file paths from filesystem (not database)
   - ✅ For each video:
     - Check if file exists
     - Optionally check database for existing transcription
     - If not transcribed, process it
   - ✅ Call transcription methods
   - ✅ Update database
   - ✅ Update sheets (with error handling)

3. **Handle database entry creation:**
   - If video not in database, may need to create entry
   - Or just transcribe and update if exists

### Upload Changes:

1. **Keep upload independent:**
   - ✅ Already reads from `assets/finished_videos/`
   - ✅ No changes to data source
   - ✅ Just implement real upload logic

2. **Implement `start_upload_process()`:**
   - ✅ Get video paths from `get_finished_videos()` response
   - ✅ Call upload processors
   - ✅ Update sheets (with error handling)

### Thumbnail Changes:

1. **Add to app.py:**
   - ✅ Add `get_thumbnails()` method (copy from app_with_db.py)
   - ✅ Add `upload_thumbnails()` method
   - ✅ Add GET `/api/thumbnails` endpoint
   - ✅ Add POST `/api/thumbnails/upload` endpoint

2. **Frontend:**
   - ✅ Add upload button for thumbnails
   - ✅ Call upload endpoint on click

### Sheets Error Handling:

1. **Wrap all sheets calls in try/except:**
   - ✅ Don't let sheets errors stop the process
   - ✅ Log errors but continue
   - ✅ Return error message in response

2. **Frontend:**
   - ✅ Show warning toast if sheets update fails
   - ✅ Don't treat as process failure

---

## 🔄 Data Flow Diagrams

### Transcription Flow (NEW):
```
assets/downloads/videos/*.mp4
    ↓
Get file paths from filesystem
    ↓
For each video file:
    ↓
Check database (optional) for transcription status
    ↓
If not transcribed:
    ↓
Convert to audio → Transcribe → Update DB
    ↓
Update sheets (optional, skip on error)
```

### Upload Flow (UNCHANGED):
```
assets/finished_videos/*.mp4
    ↓
Get file paths from filesystem
    ↓
Upload to Google Drive
    ↓
Upload to AIWaverider
    ↓
Update sheets (optional, skip on error)
```

### Thumbnail Upload Flow (NEW):
```
assets/downloads/thumbnails/*.{webp,jpg}
    ↓
User selects thumbnails
    ↓
Upload to Google Drive
    ↓
Upload to AIWaverider
    ↓
Update sheets (optional, skip on error)
```

---

## ✅ Summary of Changes Needed

1. **Transcription:**
   - Change `get_downloaded_videos()` to read from filesystem
   - Implement real transcription logic
   - Add sheets error handling

2. **Upload:**
   - Keep independent (no changes to data source)
   - Implement real upload logic
   - Add sheets error handling

3. **Thumbnails:**
   - Add endpoints to app.py
   - Add upload functionality
   - Add frontend button

4. **Sheets:**
   - Wrap all calls in try/except
   - Return error messages in responses
   - Update frontend to show warnings

All changes follow existing patterns from standalone scripts!

