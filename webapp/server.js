const express = require('express');
const WebSocket = require('ws');
const http = require('http');
const path = require('path');
const JobManager = require('./jobs');

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

function broadcastProgress(jobId, data) {
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

function broadcastJobComplete(jobId, downloadPath) {
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

function broadcastJobError(jobId, error) {
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

app.post('/api/generate', (req, res) => {
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
        partyName,
        groupName,
        maxReleases: parseInt(maxReleases)
    });
    
    res.json({ jobId, status: 'started' });
});

app.get('/api/status/:jobId', (req, res) => {
    const job = jobManager.getJob(req.params.jobId);
    if (!job) {
        return res.status(404).json({ error: 'Job not found' });
    }
    
    res.json({
        jobId: req.params.jobId,
        status: job.status,
        progress: job.progress,
        error: job.error
    });
});

app.get('/download/:jobId', (req, res) => {
    const job = jobManager.getJob(req.params.jobId);
    if (!job || job.status !== 'completed') {
        return res.status(404).json({ error: 'Job not found or not completed' });
    }
    
    const filename = `csdb-archive-${req.params.jobId}.zip`;
    res.download(job.downloadPath, filename, (err) => {
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