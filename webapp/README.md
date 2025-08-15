# CSDbSpider Web Application

A web interface for the CSDbSpider C64 archive tool that allows users to generate and download C64 release archives through a user-friendly browser interface.

## Features

- **Multiple Download Types**: Support for Toplist, Party/Event, and Group downloads
- **Real-time Progress**: WebSocket-powered progress updates during archive generation
- **User-friendly Interface**: Clean, responsive web interface
- **Archive Generation**: Automatically creates ZIP archives of downloaded releases
- **Configurable**: Adjustable maximum number of releases per archive

## Prerequisites

- Node.js (v14 or higher)
- Python 3 with the csdb.py tool working
- All csdb.py dependencies (cbmconvert, 7z, etc.)

## Installation

1. Navigate to the webapp directory:
   ```bash
   cd webapp
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the server:
   ```bash
   npm start
   ```

4. Open your browser to: http://localhost:3000

## Usage

1. **Select Download Type**:
   - **Toplist**: Downloads top-rated demos from CSDb
   - **Party**: Downloads releases from a specific party/event (enter party name)
   - **Group**: Downloads releases from a specific group (enter group name)

2. **Configure Settings**:
   - Set maximum number of releases (1-100)
   - Enter party/group name if applicable

3. **Generate Archive**:
   - Click "Generate Archive" to start the process
   - Monitor real-time progress via the progress bar
   - Download the generated ZIP file when complete

## API Endpoints

- `POST /api/generate` - Start a new archive generation job
- `GET /api/status/:jobId` - Get job status
- `GET /download/:jobId` - Download completed archive

## File Structure

```
webapp/
├── server.js          # Express server
├── jobs.js            # Job management system
├── public/
│   ├── index.html     # Main web interface
│   ├── style.css      # Styling
│   └── app.js         # Client-side JavaScript
├── temp/              # Temporary files (auto-created)
└── package.json       # Dependencies
```

## Configuration

The server runs on port 3000 by default. You can change this by setting the `PORT` environment variable:

```bash
PORT=8080 npm start
```

## Troubleshooting

- Ensure csdb.py is executable and in the parent directory
- Check that all csdb.py dependencies are installed
- Verify Python 3 is available in the system PATH
- Check server logs for detailed error messages