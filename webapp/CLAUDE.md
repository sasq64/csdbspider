# CLAUDE.md - CSDbSpider Web Application

This file provides guidance to Claude Code (claude.ai/code) when working with the CSDbSpider Web Application.

## Project Overview

The CSDbSpider Web Application is a Node.js/Express web interface that provides a user-friendly way to generate and download C64 archive collections using the csdb.py command-line tool. It features real-time progress updates, job management, and automatic archive creation.

## Architecture

### Backend Components

- **server.js**: Main Express server with WebSocket support for real-time communication
- **jobs.js**: Job management system that handles:
  - Spawning csdb.py processes as child processes
  - Parsing progress output from csdb.py
  - Creating ZIP archives from downloaded releases
  - Event-driven progress updates via EventEmitter
  - Automatic cleanup of temporary files

### Frontend Components

- **public/index.html**: Main web interface with responsive design
- **public/style.css**: Modern CSS styling with animations and mobile support
- **public/app.js**: Client-side JavaScript application class handling:
  - Form validation and submission
  - WebSocket connection for real-time updates
  - UI state management (form → progress → download)
  - Error handling and user feedback

### Key Features

- **Three Download Types**: Toplist, Party/Event, and Group downloads
- **Real-time Progress**: WebSocket-powered live updates during archive generation
- **Configurable Limits**: Adjustable maximum number of releases (1-100)
- **Archive Generation**: Automatic ZIP file creation with proper naming
- **Error Handling**: Comprehensive error reporting and recovery
- **Responsive Design**: Works on desktop and mobile devices

## Common Development Tasks

### Starting the Application
```bash
cd webapp
npm install        # First time only
npm start          # Starts server (HTTP on port 3000, HTTPS on port 3443 if certificates exist)
```

### HTTPS Setup
The webapp supports HTTPS with SSL certificates:

```bash
# Generate self-signed certificate for development
./generate-cert.sh

# Start the application (will use HTTPS if certificates exist)
npm start
```

When HTTPS is enabled:
- HTTPS server runs on port 3443 (configurable with `HTTPS_PORT` env var)
- HTTP server runs on port 3000 and redirects to HTTPS
- Certificates are automatically detected in the `ssl/` directory
- Browser will show security warning for self-signed certificates

For production, replace the self-signed certificates with proper SSL certificates from a Certificate Authority.

### Testing the Application
- Navigate to http://localhost:3000
- Select download type and configure options
- Monitor progress in real-time
- Download generated archives

### Development Commands
```bash
# Install dependencies
npm install

# Start development server
npm start

# Kill any stuck processes
pkill -f "node server.js"
```

## File Structure

```
webapp/
├── server.js          # Express server with WebSocket support
├── jobs.js            # Job management and csdb.py execution
├── public/
│   ├── index.html     # Main web interface
│   ├── style.css      # Styling and animations
│   └── app.js         # Client-side application logic
├── temp/              # Temporary files (auto-created/cleaned)
├── package.json       # Dependencies and scripts
└── README.md          # Usage documentation
```

## Key Implementation Details

### Job Management Flow

1. **Job Creation**: User submits form → server creates job with UUID
2. **Process Execution**: Spawn csdb.py with appropriate arguments
3. **Progress Parsing**: Parse stdout for progress indicators:
   - "Collected X releases" → total count
   - "Need to download X releases" → remaining count
   - Real-time download status updates
4. **Archive Creation**: Use archiver library to create ZIP from work directory
5. **Completion**: Emit completion event with download path
6. **Cleanup**: Remove temporary files after download

### WebSocket Communication

- **Connection**: Established on page load
- **Progress Events**: `{type: 'progress', jobId, data}`
- **Completion Events**: `{type: 'complete', jobId, downloadPath}`
- **Error Events**: `{type: 'error', jobId, error}`

### UI State Management

The application has four main UI states:
1. **Form State**: Initial configuration form
2. **Progress State**: Real-time progress display
3. **Download State**: Archive ready for download
4. **Error State**: Error display with retry option

### Critical Bug Fix

**Important**: When showing/hiding UI sections, always target specific elements, not their parents:

```javascript
// CORRECT - Hide just the form
this.form.style.display = 'none';

// WRONG - This hides the entire main element
this.form.parentElement.style.display = 'none';
```

## Dependencies

### Backend
- **express**: Web server framework
- **ws**: WebSocket server for real-time communication
- **archiver**: ZIP file creation
- **uuid**: Unique job ID generation

### Frontend
- **Vanilla JavaScript**: No frameworks, modern ES6+ features
- **CSS Grid/Flexbox**: Responsive layout
- **WebSocket API**: Real-time communication with server

## Environment Requirements

- **Node.js**: v14 or higher
- **Python 3**: For csdb.py execution
- **csdb.py Dependencies**: All tools required by csdb.py (7z, cbmconvert, etc.)
- **Working csdb.py**: Must be executable in parent directory

## Configuration

### Environment Variables
- `PORT`: Server port (default: 3000)

### csdb.py Integration
The webapp automatically constructs csdb.py command arguments:
- **Toplist**: `-l demo -m {maxReleases}`
- **Party**: `-e "{partyName}" -m {maxReleases}`
- **Group**: `-g "{groupName}" -m {maxReleases}`
- **Template**: `-t "{workDir}/{rank:03}. {group} - {title}{ ({year})}"`

## Debugging

### Server-Side Logging
All job operations include detailed console logging with job IDs:
```
[Job abc123] Starting CSDb with command: python3 /path/to/csdb.py -l demo -m 5
[Job abc123] CSDb stdout: Collected 869 releases
[Job abc123] Archive creation completed. Size: 1355623 bytes
```

### Client-Side Logging
Frontend operations log to browser console:
```
[Frontend] Form submitted
[Frontend] Job started with ID: abc123
[Frontend] Received WebSocket message: {type: 'progress', ...}
[Frontend] Job completed, showing download section
```

### Common Issues
- **Port in use**: Kill existing processes with `pkill -f "node server.js"`
- **csdb.py not found**: Ensure csdb.py is executable in parent directory
- **UI not updating**: Check WebSocket connection in browser developer tools
- **Downloads not working**: Verify job completion and temporary file creation

## Security Considerations

- **Input Validation**: All user inputs are validated before processing
- **Command Injection Prevention**: Arguments are properly escaped when spawning processes
- **File Access**: Temporary files are isolated to webapp/temp/ directory
- **Automatic Cleanup**: All temporary files and jobs are cleaned up after download