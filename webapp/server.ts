import express from 'express';
import WebSocket from 'ws';
import http from 'http';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import JobManager from './jobs';

/**
 * ASCII name sanitization - converts names to safe ASCII characters
 * Based on the fixname function from utils.py
 */
function fixname(s: string, removeDots: boolean = true): string {
    // Character translation table based on utils.py
    const nametrans: { [key: string]: string } = {
        '\\': '.', '/': '.', ':': '.', '*': '.', '"': "'", '<': '(', '>': ')', '|': '.',
        'Ç': 'C', 'ü': 'u', 'é': 'e', 'â': 'a', 'ä': 'a', 'à': 'a', 'å': 'a', 'ç': 'c',
        'ê': 'e', 'ë': 'e', 'è': 'e', 'ï': 'i', 'î': 'i', 'ì': 'i', 'Ä': 'A', 'Å': 'A',
        'É': 'E', 'æ': 'a', 'Æ': 'A', 'ô': 'o', 'ö': 'o', 'ò': 'o', 'û': 'u', 'ù': 'u',
        'ÿ': 'y', 'Ö': 'O', 'Ü': 'U', '¢': '.', '£': '$', '¥': 'Y', '₧': '_', 'ƒ': 'f',
        'á': 'a', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n', 'Ñ': 'N', 'ª': "'", 'º': "'",
        '¿': '?', '⌐': '.', '¬': '.', '½': '.', '¼': '.', '¡': '!', '«': '.', '»': '.',
        'À': 'A', 'Á': 'A', 'Â': 'A', 'Ã': 'A', 'È': 'E', 'Ê': 'E', 'Ë': 'E', 'Í': 'I',
        'Î': 'I', 'Ï': 'I', 'Ì': 'I', 'Ð': 'D', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ø': 'O',
        'Ù': 'U', 'Ú': 'U', 'Û': 'U', 'Ý': 'Y', 'Þ': 'd', 'ß': 'B', 'ð': 'd', 'þ': 'D',
        'ý': 'y'
    };
    
    // Apply character translations
    let result = s.split('').map(char => nametrans[char] || char).join('');
    
    // Remove control characters and non-ASCII
    result = result.replace(/[^\x20-\x7E]/g, '.');
    
    if (removeDots) {
        // Remove trailing dots and spaces
        result = result.replace(/[. ]+$/, '');
    }
    
    return result;
}

interface JobParams {
  downloadType: 'toplist' | 'party' | 'group';
  partyName?: string | undefined;
  groupName?: string | undefined;
  partyId?: number | undefined;
  groupId?: number | undefined;
  maxReleases: number;
}

interface GenerateRequest {
  downloadType: 'toplist' | 'party' | 'group';
  partyName?: string;
  groupName?: string;
  partyId?: number;
  groupId?: number;
  maxReleases: string | number;
}

interface AutocompleteItem {
  name: string;
  id: number;
}

interface AutocompleteData {
  groups: AutocompleteItem[];
  events: AutocompleteItem[];
}

interface Job {
  id: string;
  status: 'running' | 'completed' | 'error';
  progress: {
    percent: number;
    current: string;
    total: number;
    completed: number;
  };
  error: string | null;
  downloadPath: string | null;
  params: JobParams;
  workDir: string;
}

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });
const jobManager = new JobManager();

// Store autocomplete data
let autocompleteData: AutocompleteData = {
  groups: [],
  events: []
};

app.use(express.json());
app.use(express.static('public'));

// Load groups and events data at startup
async function loadAutocompleteData(): Promise<void> {
  console.log('Loading autocomplete data...');
  
  try {
    // Load groups
    const groupsData = await loadCsdbList('groups');
    autocompleteData.groups = groupsData;
    console.log(`Loaded ${groupsData.length} groups`);
    
    // Load events
    const eventsData = await loadCsdbList('events');
    autocompleteData.events = eventsData;
    console.log(`Loaded ${eventsData.length} events`);
  } catch (error) {
    console.error('Failed to load autocomplete data:', error);
  }
}

function loadCsdbList(type: 'groups' | 'events'): Promise<AutocompleteItem[]> {
  return new Promise((resolve, reject) => {
    const csdbPath = path.join(__dirname, '..', '..', 'csdb.py');
    const process = spawn('python3', [csdbPath, '--list', type], {
      cwd: path.join(__dirname, '..', '..')
    });
    
    let output = '';
    let errorOutput = '';
    
    process.stdout?.on('data', (data) => {
      output += data.toString();
    });
    
    process.stderr?.on('data', (data) => {
      errorOutput += data.toString();
    });
    
    process.on('close', (code) => {
      if (code === 0) {
        try {
          const items: AutocompleteItem[] = [];
          const lines = output.trim().split('\n');
          
          for (const line of lines) {
            if (line.trim()) {
              // Parse CSV format: "Name",ID
              const match = line.match(/^"(.+?)",(.+)$/);
              if (match) {
                const name = match[1];
                const id = parseInt(match[2]);
                if (!isNaN(id)) {
                  items.push({ name, id });
                }
              }
            }
          }
          
          resolve(items);
        } catch (error) {
          reject(new Error(`Failed to parse ${type} data: ${error}`));
        }
      } else {
        reject(new Error(`csdb.py --list ${type} exited with code ${code}: ${errorOutput}`));
      }
    });
    
    process.on('error', (error) => {
      reject(new Error(`Failed to spawn csdb.py: ${error.message}`));
    });
  });
}

wss.on('connection', (ws) => {
    console.log('Client connected');
    
    ws.on('close', () => {
        console.log('Client disconnected');
    });
});

function broadcastProgress(jobId: string, data: Job['progress']): void {
    console.log(`[Server] Broadcasting progress for job ${jobId}:`, data);
    const message = JSON.stringify({
        type: 'progress',
        jobId,
        data
    });
    
    let clientCount = 0;
    wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(message);
            clientCount++;
        }
    });
    console.log(`[Server] Sent progress to ${clientCount} clients`);
}

function broadcastJobComplete(jobId: string, downloadPath: string): void {
    console.log(`[Server] Broadcasting completion for job ${jobId}:`, downloadPath);
    const message = JSON.stringify({
        type: 'complete',
        jobId,
        downloadPath
    });
    
    let clientCount = 0;
    wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(message);
            clientCount++;
        }
    });
    console.log(`[Server] Sent completion to ${clientCount} clients`);
}

function broadcastJobError(jobId: string, error: string): void {
    console.log(`[Server] Broadcasting error for job ${jobId}:`, error);
    const message = JSON.stringify({
        type: 'error',
        jobId,
        error
    });
    
    let clientCount = 0;
    wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(message);
            clientCount++;
        }
    });
    console.log(`[Server] Sent error to ${clientCount} clients`);
}

jobManager.on('progress', broadcastProgress);
jobManager.on('complete', broadcastJobComplete);
jobManager.on('error', broadcastJobError);

app.post('/api/generate', (req: express.Request<{}, {}, GenerateRequest>, res: express.Response) => {
    const { downloadType, partyName, groupName, partyId, groupId, maxReleases } = req.body;
    
    if (!downloadType || !maxReleases) {
        return res.status(400).json({ error: 'Missing required parameters' });
    }
    
    if (downloadType === 'party' && !partyName && partyId === undefined) {
        return res.status(400).json({ error: 'Party name or ID is required for party downloads' });
    }
    
    if (downloadType === 'group' && !groupName && groupId === undefined) {
        return res.status(400).json({ error: 'Group name or ID is required for group downloads' });
    }
    
    const jobId = jobManager.startJob({
        downloadType,
        partyName: partyName || undefined,
        groupName: groupName || undefined,
        partyId: partyId || undefined,
        groupId: groupId || undefined,
        maxReleases: typeof maxReleases === 'string' ? parseInt(maxReleases) : maxReleases
    });
    
    return res.json({ jobId, status: 'started' });
});

app.get('/api/status/:jobId', (req: express.Request<{jobId: string}>, res: express.Response) => {
    const job = jobManager.getJob(req.params.jobId);
    if (!job) {
        return res.status(404).json({ error: 'Job not found' });
    }
    
    return res.json({
        jobId: req.params.jobId,
        status: job.status,
        progress: job.progress,
        error: job.error
    });
});

// Autocomplete endpoints
app.get('/api/autocomplete/groups', (req: express.Request, res: express.Response) => {
  const query = req.query.q as string;
  
  if (!query) {
    return res.json(autocompleteData.groups.slice(0, 50)); // Return first 50 if no query
  }
  
  const filteredGroups = autocompleteData.groups
    .filter(group => group.name.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 20); // Limit to 20 results
  
  return res.json(filteredGroups);
});

app.get('/api/autocomplete/events', (req: express.Request, res: express.Response) => {
  const query = req.query.q as string;
  
  if (!query) {
    return res.json(autocompleteData.events.slice(0, 50)); // Return first 50 if no query
  }
  
  const filteredEvents = autocompleteData.events
    .filter(event => event.name.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 20); // Limit to 20 results
  
  return res.json(filteredEvents);
});

// Archive management endpoints
app.get('/api/archives', (_req: express.Request, res: express.Response) => {
  const archives = jobManager.getArchiveHistory();
  return res.json(archives);
});

app.get('/download/archive/:filename', (req: express.Request<{filename: string}>, res: express.Response) => {
  const filename = req.params.filename;
  const archivePath = path.join(__dirname, 'archives', filename);
  
  if (!fs.existsSync(archivePath)) {
    return res.status(404).json({ error: 'Archive not found' });
  }
  
  // Increment download count
  jobManager.incrementDownloadCount(filename);
  
  return res.download(archivePath, filename, (err) => {
    if (err) {
      console.error('Archive download error:', err);
    }
  });
});

app.get('/download/:jobId', (req: express.Request<{jobId: string}>, res: express.Response) => {
    const job = jobManager.getJob(req.params.jobId);
    if (!job || job.status !== 'completed') {
        return res.status(404).json({ error: 'Job not found or not completed' });
    }
    
    // Generate filename based on job parameters and content type
    let filename: string;
    const { downloadType, partyName, groupName, maxReleases } = job.params;
    
    switch (downloadType) {
        case 'toplist':
            filename = `csdb-top${maxReleases}-releases.zip`;
            break;
        case 'group':
            const sanitizedGroup = fixname(groupName || 'unknown-group');
            filename = `${sanitizedGroup}-top-${maxReleases}-releases.zip`;
            break;
        case 'party':
            const sanitizedParty = fixname(partyName || 'unknown-party');
            filename = `${sanitizedParty}-releases.zip`;
            break;
        default:
            filename = `csdb-archive-${req.params.jobId}.zip`;
    }
    
    return res.download(job.downloadPath!, filename, (err) => {
        if (err) {
            console.error('Download error:', err);
        }
        
        jobManager.cleanupJob(req.params.jobId);
    });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, async () => {
    console.log(`CSDbSpider Web App running on port ${PORT}`);
    console.log(`Open http://localhost:${PORT} in your browser`);
    
    // Load autocomplete data after server starts
    await loadAutocompleteData();
});
