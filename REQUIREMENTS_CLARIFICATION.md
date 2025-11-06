# Requirements Clarification & Implementation Plan

## 📋 User Requirements

### 1. ✅ Upload Videos - Independent & Untouched
**Requirement:** Upload videos should stay independent and untouched.

**Current State:**
- ✅ Already independent - reads from `assets/finished_videos/`
- ✅ No dependencies on download/transcription
- ⚠️ Backend is TODO/mock - needs real implementation

**Action:** 
- Keep upload completely independent
- Just implement the real upload logic (replace TODO)
- No changes to how it works or where it gets data

---

### 2. 🎤 Transcription - Filesystem-Based (MAJOR CHANGE)

**Requirement:** 
- Transcription should work with `assets/downloads/videos` path
- These are unfinished videos that need transcription
- Should work independently from upload
- Should NOT be associated with upload

**Current Problem:**
- `app.py` reads from **database** (`get_all_videos()`)
- Should read from **filesystem** (`assets/downloads/videos/`)

**What Needs to Change:**

**BEFORE (Current - app.py line 70-90):**
```python
async def get_downloaded_videos(self):
    # Reads from DATABASE
    videos = await self.db_manager.get_all_videos()
    return [video data from database]
```

**AFTER (Should be - like app_with_db.py):**
```python
async def get_downloaded_videos(self):
    # Reads from FILESYSTEM
    videos_dir = Path("assets/downloads/videos")
    videos = []
    for video_file in videos_dir.rglob("*.mp4"):
        # Get file info from filesystem
        # Optionally check database for transcription status
        videos.append({
            'id': video_id,
            'filename': filename,
            'path': str(video_file),  # Full file path
            'transcriptionStatus': 'PENDING' or 'COMPLETED' (from DB check)
        })
    return videos
```

**Transcription Process:**
1. Get videos from `assets/downloads/videos/` (filesystem)
2. For each selected video:
   - Get file path from filesystem
   - Optionally check database for existing transcription
   - If not transcribed, process it
3. Transcribe using video processor
4. Update database with results
5. Update sheets (optional - skip on error)

**Independence:**
- ✅ **FULLY INDEPENDENT** from upload
- ✅ Works with any video files in `assets/downloads/videos/`
- ✅ No connection to upload process

---

### 3. 📸 Upload Thumbnails - Manual Trigger

**Requirement:**
- Upload thumbnails should happen when triggered manually
- Through API or button click in respective page

**Current State:**
- ✅ UI has thumbnail list
- ❌ No upload functionality
- ❌ `app.py` has no thumbnail endpoint

**What Needs to Be Added:**

1. **Backend - Add to app.py:**
   ```python
   # GET endpoint (copy from app_with_db.py)
   @app.route('/api/thumbnails', methods=['GET'])
   def get_thumbnails():
       thumbnails = asyncio.run(api.get_thumbnails())
       return jsonify({"success": True, "thumbnails": thumbnails})
   
   # POST endpoint (new)
   @app.route('/api/thumbnails/upload', methods=['POST'])
   def upload_thumbnails():
       data = request.get_json()
       thumbnail_ids = data.get('thumbnailIds', [])
       result = asyncio.run(api.upload_thumbnails(thumbnail_ids))
       return jsonify(result)
   ```

2. **Backend - Add method to WebAPI:**
   ```python
   async def get_thumbnails(self):
       # Get thumbnails from assets/downloads/thumbnails/
       # Return list with paths
   
   async def upload_thumbnails(self, thumbnail_ids):
       # For each thumbnail:
       #   Get file path
       #   Upload to Google Drive
       #   Upload to AIWaverider
       #   Update sheets (optional)
   ```

3. **Frontend:**
   - Add "Upload Selected Thumbnails" button
   - Call `/api/thumbnails/upload` on click

---

### 4. 📊 Sheets Updates - Optional with Error Handling

**Requirement:**
- Database updates should still work (required)
- Sheets updates should work if reachable
- If auth issues, skip sheets update (don't fail process)
- Show error to user that sheets update didn't happen
- DB persistence is enough

**Current Problem:**
- Sheets processors return `False` on failure
- This might be treated as process failure
- Need to make sheets optional

**What Needs to Change:**

**BEFORE (Current pattern):**
```python
sheets_result = await orchestrator.sheets_processor.update_master_sheet()
if not sheets_result:
    # This might fail the whole process
    return False
```

**AFTER (Should be):**
```python
sheets_success = False
sheets_error = None
try:
    sheets_success = await orchestrator.sheets_processor.update_master_sheet()
    await orchestrator.transcripts_sheets_processor.update_transcripts_sheet()
except Exception as e:
    sheets_error = str(e)
    logger.error(f"Sheets update failed (non-fatal): {e}")
    # Continue - don't fail the process

# Return with sheets status
return {
    "success": True,  # Main process succeeded
    "sheets_updated": sheets_success,
    "sheets_error": sheets_error if not sheets_success else None
}
```

**Frontend Handling:**
```javascript
if (data.sheets_error) {
    this.showToast(
        `Process completed, but Google Sheets update failed: ${data.sheets_error}. Data saved to database.`, 
        'warning'
    );
} else {
    this.showToast('Process completed successfully', 'success');
}
```

**Implementation Locations:**
1. **Transcription** - After transcription, update sheets with error handling
2. **Upload** - After upload, update sheets with error handling
3. **Thumbnail Upload** - After upload, update sheets with error handling

---

## 📊 Summary of Changes

### 1. Upload Videos
- ✅ **NO CHANGES** to independence or data source
- ✅ Just implement real upload logic (replace TODO)
- ✅ Keep reading from `assets/finished_videos/`

### 2. Transcription
- ❌ **MAJOR CHANGE**: Change `get_downloaded_videos()` to read from filesystem
- ✅ Read from `assets/downloads/videos/` instead of database
- ✅ Optionally check database for transcription status
- ✅ Return file paths for transcription
- ✅ Implement real transcription logic
- ✅ Add sheets error handling

### 3. Thumbnail Upload
- ✅ Add `get_thumbnails()` method to app.py
- ✅ Add `upload_thumbnails()` method to app.py
- ✅ Add GET `/api/thumbnails` endpoint
- ✅ Add POST `/api/thumbnails/upload` endpoint
- ✅ Add frontend upload button
- ✅ Add sheets error handling

### 4. Sheets Updates
- ✅ Wrap all sheets calls in try/except
- ✅ Don't fail process on sheets errors
- ✅ Return error messages in API responses
- ✅ Update frontend to show warnings (not errors)
- ✅ Database updates are required, sheets are optional

---

## 🔍 Key Points

1. **Transcription Independence:**
   - Reads from filesystem (`assets/downloads/videos/`)
   - NOT from database (except to check status)
   - Completely separate from upload

2. **Upload Independence:**
   - Stays as is - reads from `assets/finished_videos/`
   - No changes needed to independence

3. **Sheets are Optional:**
   - Database updates = Required
   - Sheets updates = Optional (nice to have)
   - If sheets fail, show warning but don't fail process

4. **Thumbnails are Manual:**
   - User must click button to upload
   - Not automatic
   - Independent operation

---

## ✅ Implementation Checklist

- [ ] Change `get_downloaded_videos()` to read from filesystem
- [ ] Implement real transcription logic
- [ ] Add sheets error handling to transcription
- [ ] Implement real upload logic (keep independent)
- [ ] Add sheets error handling to upload
- [ ] Add thumbnail endpoints to app.py
- [ ] Add thumbnail upload functionality
- [ ] Add sheets error handling to thumbnail upload
- [ ] Update frontend to show sheets warnings
- [ ] Test all operations independently

