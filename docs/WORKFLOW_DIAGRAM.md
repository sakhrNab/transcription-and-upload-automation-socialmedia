# System Workflow Diagram

## Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SOCIAL MEDIA CONTENT PROCESSOR                        │
│                              MODULAR ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MAIN ENTRY    │    │   CONTINUOUS    │    │   MANUAL UPLOAD │
│   POINT         │    │   SCANNER       │    │   PROCESSING    │
│   (main.py)     │    │   (continuous_  │    │   (main.py)     │
│                 │    │   scanner.py)   │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR (core/orchestrator.py)                   │
│  • Coordinates all processors                                                  │
│  • Manages database connections                                                │
│  • Handles error recovery and retries                                          │
│  • Tracks processing metrics                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PROCESSING PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   VIDEO         │    │   THUMBNAIL     │    │   UPLOAD        │
│   PROCESSOR     │    │   PROCESSOR     │    │   PROCESSOR     │
│                 │    │                 │    │                 │
│ 1. Download     │    │ 1. Extract      │    │ 1. Google       │
│    videos       │    │    thumbnails   │    │    Drive        │
│ 2. Convert to   │    │ 2. Generate     │    │ 2. AIWaverider  │
│    audio        │    │    smart names  │    │    Drive        │
│ 3. Transcribe   │    │ 3. Optimize     │    │ 3. Update       │
│    with Whisper │    │    images       │    │    database     │
│ 4. Save         │    │ 4. Upload to    │    │ 4. Track        │
│    transcripts  │    │    both drives  │    │    status       │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DATABASE LAYER                                       │
│  • video_transcripts table - Tracks downloads and transcripts                   │
│  • upload_tracking table - Tracks upload status to both platforms              │
│  • processing_queue table - Background task management                         │
└─────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            GOOGLE SHEETS INTEGRATION                            │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MASTER        │    │   VIDEO         │    │   LOCAL         │
│   TRACKING      │    │   TRANSCRIPTS   │    │   BACKUP        │
│   SHEET         │    │   SHEET         │    │   SYSTEM        │
│                 │    │                 │    │                 │
│ • All content   │    │ • Video         │    │ • CSV files     │
│   status        │    │   transcripts   │    │ • JSON files    │
│ • Thumbnails    │    │ • Metadata      │    │ • Excel files   │
│ • Upload        │    │ • 31 columns    │    │ • Automatic     │
│   status        │    │ • Smart names   │    │   backups       │
│ • Real-time     │    │ • Word counts   │    │ • Version       │
│   updates       │    │ • Status        │    │   control       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Detailed Workflow Scenarios

### Scenario 1: Main Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              MAIN PROCESSING FLOW                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Read URLs   │───▶│ Download    │───▶│ Transcribe  │───▶│ Upload to   │
│ from file   │    │ Videos      │    │ Audio       │    │ Both Drives │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Validate    │    │ Extract     │    │ Generate    │    │ Update      │
│ URLs        │    │ Metadata    │    │ Thumbnails  │    │ Sheets      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Check for   │    │ Convert to  │    │ Save        │    │ Track       │
│ Duplicates  │    │ Audio       │    │ Transcripts │    │ Status      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Scenario 2: Continuous Scanner Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            CONTINUOUS SCANNER FLOW                             │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Watch       │───▶│ Detect      │───▶│ Check       │───▶│ Upload      │
│ Directory   │    │ New Files   │    │ Upload      │    │ if Needed   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ File        │    │ Generate    │    │ Update      │    │ Notify      │
│ System      │    │ Thumbnails  │    │ Database    │    │ Success     │
│ Events      │    │ if Needed   │    │ Status      │    │ / Failure   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Monitor     │    │ Process     │    │ Update      │    │ Log         │
│ Changes     │    │ Files       │    │ Sheets      │    │ Results     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Scenario 3: Manual Upload Processing

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            MANUAL UPLOAD FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Place       │───▶│ Scanner     │───▶│ Process     │───▶│ Upload to   │
│ Videos in   │    │ Detects     │    │ Videos      │    │ Both Drives │
│ finished_   │    │ Changes     │    │ (if needed) │    │             │
│ videos/     │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Manual      │    │ Real-time   │    │ Check       │    │ Update      │
│ Editing     │    │ Detection   │    │ Database    │    │ Tracking    │
│ Process     │    │ System      │    │ Status      │    │ Sheets      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW DIAGRAM                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

INPUT SOURCES
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ URLs File   │    │ Manual      │    │ API         │
│ (urls.txt)  │    │ Videos      │    │ Endpoints   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATOR                                      │
│  • URL Validation                                                              │
│  • Task Distribution                                                           │
│  • Error Handling                                                              │
│  • Progress Tracking                                                           │
└─────────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              PROCESSING LAYER                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Video       │    │ Audio       │    │ Thumbnail   │    │ Upload      │
│ Download    │    │ Processing  │    │ Generation  │    │ Processing  │
│             │    │             │    │             │    │             │
│ • yt-dlp    │    │ • ffmpeg    │    │ • PIL       │    │ • Google    │
│ • Metadata  │    │ • Whisper   │    │ • OpenCV    │    │   Drive     │
│ • Thumbnail │    │ • GPU       │    │ • AI Names  │    │ • AIWaverider│
│   Download  │    │   Support   │    │ • Upload    │    │ • Status    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATABASE LAYER                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Video       │    │ Upload      │    │ Processing  │
│ Transcripts │    │ Tracking    │    │ Queue       │
│ Table       │    │ Table       │    │ Table       │
│             │    │             │    │             │
│ • Downloads │    │ • Google    │    │ • Tasks     │
│ • Metadata  │    │   Drive     │    │ • Status    │
│ • Transcripts│    │ • AIWaverider│    │ • Retries  │
│ • Status    │    │ • Status    │    │ • Workers   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT LAYER                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Google      │    │ AIWaverider │    │ Local       │    │ Monitoring  │
│ Sheets      │    │ Drive       │    │ Backups     │    │ & Logs      │
│             │    │             │    │             │    │             │
│ • Master    │    │ • Videos    │    │ • CSV       │    │ • Health    │
│   Tracking  │    │ • Thumbnails│    │ • JSON      │    │   Metrics   │
│ • Transcripts│    │ • Folders   │    │ • Excel     │    │ • Error     │
│ • Real-time │    │ • Status    │    │ • Archives  │    │   Tracking  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          COMPONENT INTERACTION DIAGRAM                         │
└─────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────┐
    │    main.py  │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Orchestrator│
    └──────┬──────┘
           │
    ┌──────┼──────┐
    │      │      │
    ▼      ▼      ▼
┌─────┐ ┌─────┐ ┌─────┐
│Video│ │Thumb│ │Upload│
│Proc │ │Proc │ │Proc │
└──┬──┘ └──┬──┘ └──┬──┘
   │       │       │
   ▼       ▼       ▼
┌─────────────────────┐
│   Database Layer    │
│  (SQLite + Queue)   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Google Sheets API  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  AIWaverider API    │
└─────────────────────┘

    ┌─────────────┐
    │Continuous   │
    │Scanner      │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │File System  │
    │Watcher      │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │finished_    │
    │videos/      │
    └─────────────┘
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            ERROR HANDLING FLOW                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Error       │───▶│ Retry       │───▶│ Circuit     │───▶│ Fallback    │
│ Detection   │    │ Logic       │    │ Breaker     │    │ Strategy    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Log Error   │    │ Exponential │    │ Prevent     │    │ Continue    │
│ Details     │    │ Backoff     │    │ Cascading   │    │ Processing  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Update      │    │ Track       │    │ Monitor     │    │ Notify      │
│ Database    │    │ Attempts    │    │ Health      │    │ Status      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

This comprehensive workflow diagram shows how all components interact in the social media content processing system, from input sources through processing to final outputs and monitoring.
