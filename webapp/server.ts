import express from 'express';
import WebSocket from 'ws';
import http from 'http';
import JobManager from './jobs';

interface JobParams {
  downloadType: 'toplist' | 'party' | 'group';
  partyName?: string | undefined;
  groupName?: string | undefined;
  maxReleases: number;
}

interface GenerateRequest {
  downloadType: 'toplist' | 'party' | 'group';
  partyName?: string;
  groupName?: string;
  maxReleases: string | number;
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

app.use(express.json());
app.use(express.static('public'));

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
    const { downloadType, partyName, groupName, maxReleases } = req.body;
    
    if (!downloadType || !maxReleases) {
        return res.status(400).json({ error: 'Missing required parameters' });
    }
    
    if (downloadType === 'party' && !partyName) {
        return res.status(400).json({ error: 'Party name is required for party downloads' });
    }
    
    if (downloadType === 'group' && !groupName) {
        return res.status(400).json({ error: 'Group name is required for group downloads' });
    }
    
    const jobId = jobManager.startJob({
        downloadType,
        partyName: partyName || undefined,
        groupName: groupName || undefined,
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

app.get('/download/:jobId', (req: express.Request<{jobId: string}>, res: express.Response) => {
    const job = jobManager.getJob(req.params.jobId);
    if (!job || job.status !== 'completed') {
        return res.status(404).json({ error: 'Job not found or not completed' });
    }
    
    const filename = `csdb-archive-${req.params.jobId}.zip`;
    return res.download(job.downloadPath!, filename, (err) => {
        if (err) {
            console.error('Download error:', err);
        }
        
        jobManager.cleanupJob(req.params.jobId);
    });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`CSDbSpider Web App running on port ${PORT}`);
    console.log(`Open http://localhost:${PORT} in your browser`);
});
