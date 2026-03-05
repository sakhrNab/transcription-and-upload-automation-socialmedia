# 🚀 Social Media Content Processor - Complete System Flow Diagram

## 📊 Mermaid Diagram

```mermaid
graph TD
    %% Entry Points
    A[User Input] --> B{Processing Type}
    B -->|URLs| C[main.py --download]
    B -->|Existing Videos| D[main.py --no-download]
    B -->|Web UI| E[web_ui/app_with_db.py]
    B -->|Standalone Scripts| F[transcribe_only.py, upload_only.py, etc.]
    
    %% Download Flow
    C --> G[VideoProcessor.process_urls]
    G --> H[Download Videos from URLs]
    H --> I[Extract Metadata]
    I --> J[Generate Thumbnails]
    J --> K[Update Database: video_transcripts]
    K --> L[Update Sheets: Master + Transcripts]
    
    %% Transcription Flow
    D --> M[VideoProcessor.process_existing_videos]
    L --> N[Transcription Process]
    M --> N
    N --> O[Convert Video to Audio]
    O --> P[Whisper GPU Transcription]
    P --> Q[Generate Smart Names with GPT-4o-mini]
    Q --> R[Save Transcript Files]
    R --> S[Update Database: transcription_text, smart_name]
    S --> T[Update Sheets: Master + Transcripts]
    
    %% Upload Flow
    T --> U[Upload Process]
    U --> V[Google Drive Upload]
    U --> W[AIWaverider Drive Upload]
    
    %% Google Drive Upload
    V --> X[UploadProcessor.process_videos]
    X --> Y[Check Duplicates in Google Drive]
    Y --> Z[Upload Videos to Google Drive]
    Z --> AA[Upload Thumbnails to Google Drive]
    AA --> BB[Update Database: upload_tracking]
    BB --> CC[Update Sheets: Master + Transcripts]
    
    %% AIWaverider Upload
    W --> DD[AIWaveriderProcessor.upload_all]
    DD --> EE[Check Duplicates in AIWaverider]
    EE --> FF[Upload Videos to AIWaverider]
    FF --> GG[Upload Thumbnails to AIWaverider]
    GG --> HH[Update Database: upload_tracking]
    HH --> II[Update Sheets: Master + Transcripts]
    
    %% Web UI Flow
    E --> JJ[Flask API Server]
    JJ --> KK[Load Videos from Database]
    KK --> LL[Display in Web Interface]
    LL --> MM[User Selects Videos/Thumbnails]
    MM --> NN[Start Transcription/Upload]
    NN --> OO[Background Processing]
    OO --> PP[Real-time Progress Updates]
    PP --> QQ[Update UI with Results]
    
    %% Database Structure
    RR[(social_media.db)] --> SS[video_transcripts table]
    RR --> TT[upload_tracking table]
    SS --> UU[Video metadata, transcripts, file paths]
    TT --> VV[Upload status for Google Drive & AIWaverider]
    
    %% Google Sheets
    WW[(Google Sheets)] --> XX[Master Sheet]
    WW --> YY[Transcripts Sheet]
    XX --> ZZ[Upload status, file paths, transcripts]
    YY --> AAA[Detailed transcript data, metadata]
    
    %% File System
    BBB[File System] --> CCC[assets/downloads/videos/]
    BBB --> DDD[assets/downloads/thumbnails/]
    BBB --> EEE[assets/finished_videos/]
    BBB --> FFF[assets/transcripts/]
    BBB --> GGG[assets/audio/]
    
    %% Continuous Processing
    HHH[continuous_scanner.py] --> III[Monitor finished_videos/]
    III --> JJJ[Auto-upload new videos]
    JJJ --> KK[Upload Process]
    
    %% Standalone Scripts
    F --> LLL[transcribe_only.py]
    F --> MMM[upload_only.py]
    F --> NNN[upload_thumbnails_only.py]
    F --> OOO[transcribe_specific.py]
    
    %% Status Tracking
    PPP[Status Tracking] --> QQQ[PENDING]
    PPP --> RRR[COMPLETED]
    PPP --> SSS[FAILED]
    PPP --> TTT[UPLOADED]
    PPP --> UUU[LOCAL]
    PPP --> VVV[PARTIAL]
    
    %% Styling
    classDef entryPoint fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#000000
    classDef process fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef database fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px,color:#000000
    classDef sheets fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#000000
    classDef files fill:#fce4ec,stroke:#880e4f,stroke-width:2px,color:#000000
    classDef status fill:#f1f8e9,stroke:#33691e,stroke-width:2px,color:#000000
    
    class A,B,C,D,E,F entryPoint
    class G,H,I,J,M,N,O,P,Q,R,U,V,W,X,DD,EE,FF,GG process
    class RR,SS,TT,UU,VV database
    class WW,XX,YY,ZZ,AAA sheets
    class BBB,CCC,DDD,EEE,FFF,GGG files
    class PPP,QQQ,RRR,SSS,TTT,UUU,VVV status
```

## 🎯 **Complete System Flow Overview:**

### **1. Entry Points:**
- **main.py** - Full pipeline with/without download
- **Web UI** - Interactive browser interface
- **Standalone Scripts** - Individual operations

### **2. Download Flow:**
- Download videos from URLs
- Extract metadata (title, description, duration, etc.)
- Generate thumbnails
- Update database and sheets

### **3. Transcription Flow:**
- Convert video to audio
- GPU-accelerated Whisper transcription
- Generate smart names with GPT-4o-mini
- Save transcript files
- Update database and sheets

### **4. Upload Flow:**
- **Google Drive Upload** - Videos and thumbnails
- **AIWaverider Drive Upload** - Videos and thumbnails
- Duplicate checking for both platforms
- Update database and sheets after each upload

### **5. Database Structure:**
- **video_transcripts** - Video metadata, transcripts, file paths
- **upload_tracking** - Upload status for both platforms

### **6. Google Sheets:**
- **Master Sheet** - Upload status, file paths, transcripts
- **Transcripts Sheet** - Detailed transcript data

### **7. File System:**
- **assets/downloads/videos/** - Downloaded videos
- **assets/downloads/thumbnails/** - Generated thumbnails
- **assets/finished_videos/** - Processed videos ready for upload
- **assets/transcripts/** - Transcript files
- **assets/audio/** - Audio files for transcription

### **8. Continuous Processing:**
- **continuous_scanner.py** - Monitors finished_videos/ for auto-upload

### **9. Status Tracking:**
- **PENDING** - Waiting for processing
- **COMPLETED** - Successfully processed
- **FAILED** - Processing failed
- **UPLOADED** - Successfully uploaded
- **LOCAL** - Available locally only
- **PARTIAL** - Partially uploaded

## 🔧 **How to Use This Diagram:**

1. **Copy the Mermaid code** from the code block above
2. **Paste it into** any Mermaid-compatible tool:
   - [Mermaid Live Editor](https://mermaid.live/)
   - [GitHub/GitLab** (supports Mermaid natively)
   - **VS Code** with Mermaid extension
   - **Notion** with Mermaid blocks
   - **Obsidian** with Mermaid plugin

3. **View the interactive diagram** with full zoom, pan, and styling

## 📝 **Key Features Shown:**

- ✅ **Complete data flow** from input to output
- ✅ **Database relationships** and table structures
- ✅ **File system organization** and paths
- ✅ **Status tracking** throughout the process
- ✅ **Parallel processing** for uploads
- ✅ **Error handling** and retry logic
- ✅ **Real-time updates** via Web UI
- ✅ **Standalone script** integration

This diagram provides a comprehensive visual representation of the entire social media content processor system architecture and workflow.
