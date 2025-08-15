const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const archiver = require('archiver');
const { v4: uuidv4 } = require('uuid');
const EventEmitter = require('events');

class JobManager extends EventEmitter {
    constructor() {
        super();
        this.jobs = new Map();
        this.tempDir = path.join(__dirname, 'temp');
        
        if (!fs.existsSync(this.tempDir)) {
            fs.mkdirSync(this.tempDir, { recursive: true });
        }
    }
    
    startJob(params) {
        const jobId = uuidv4();
        const jobDir = path.join(this.tempDir, jobId);
        
        const job = {
            id: jobId,
            status: 'running',
            progress: { percent: 0, current: '', total: 0, completed: 0 },
            error: null,
            downloadPath: null,
            params,
            workDir: jobDir
        };
        
        this.jobs.set(jobId, job);
        
        fs.mkdirSync(jobDir, { recursive: true });
        
        this.executeCSDb(job);
        
        return jobId;
    }
    
    executeCSDb(job) {
        const { downloadType, partyName, groupName, maxReleases } = job.params;
        const csdbPath = path.join(__dirname, '..', 'csdb.py');
        
        let args = [csdbPath, '-m', maxReleases.toString()];
        
        switch (downloadType) {
            case 'toplist':
                args.push('-l', 'demo');
                break;
            case 'party':
                args.push('-e', partyName);
                break;
            case 'group':
                args.push('-g', groupName);
                break;
        }
        
        args.push('-t', `${job.workDir}/{rank:03}. {group} - {title}{ ({year})}`);
        
        console.log(`[Job ${job.id}] Starting CSDb with command: python3 ${args.join(' ')}`);
        console.log(`[Job ${job.id}] Working directory: ${job.workDir}`);
        console.log(`[Job ${job.id}] CSDb script path: ${csdbPath}`);
        
        const csdbProcess = spawn('python3', args, {
            cwd: path.join(__dirname, '..'),
            stdio: ['pipe', 'pipe', 'pipe']
        });
        
        let stdoutBuffer = '';
        let stderrBuffer = '';
        
        csdbProcess.stdout.on('data', (data) => {
            const output = data.toString();
            console.log(`[Job ${job.id}] CSDb stdout:`, output);
            stdoutBuffer += output;
            this.parseProgress(job, stdoutBuffer);
        });
        
        csdbProcess.stderr.on('data', (data) => {
            const output = data.toString();
            stderrBuffer += output;
            console.error(`[Job ${job.id}] CSDb stderr:`, output);
        });
        
        csdbProcess.on('close', (code) => {
            console.log(`[Job ${job.id}] CSDb process exited with code: ${code}`);
            console.log(`[Job ${job.id}] Final stdout:`, stdoutBuffer);
            if (stderrBuffer) {
                console.log(`[Job ${job.id}] Final stderr:`, stderrBuffer);
            }
            
            if (code === 0) {
                console.log(`[Job ${job.id}] Checking work directory contents:`, job.workDir);
                try {
                    const files = fs.readdirSync(job.workDir, { recursive: true });
                    console.log(`[Job ${job.id}] Found ${files.length} files in work directory:`, files);
                } catch (err) {
                    console.error(`[Job ${job.id}] Error reading work directory:`, err);
                }
                this.createArchive(job);
            } else {
                job.status = 'error';
                job.error = `CSDb process exited with code ${code}`;
                if (stderrBuffer) {
                    job.error += '\n' + stderrBuffer;
                }
                console.error(`[Job ${job.id}] Error:`, job.error);
                this.emit('error', job.id, job.error);
            }
        });
        
        csdbProcess.on('error', (error) => {
            job.status = 'error';
            job.error = `Failed to start CSDb process: ${error.message}`;
            console.error(`[Job ${job.id}] Process error:`, job.error);
            this.emit('error', job.id, job.error);
        });
    }
    
    parseProgress(job, output) {
        const lines = output.split('\n');
        
        for (const line of lines) {
            console.log(`[Job ${job.id}] Parsing line:`, line);
            
            if (line.includes('Collected') && line.includes('releases')) {
                const match = line.match(/Collected (\d+) releases/);
                if (match) {
                    job.progress.total = parseInt(match[1]);
                    console.log(`[Job ${job.id}] Updated total releases:`, job.progress.total);
                    this.emit('progress', job.id, {
                        ...job.progress,
                        current: `Found ${job.progress.total} releases to download`
                    });
                }
            }
            
            if (line.includes('Need to download')) {
                const match = line.match(/Need to download (\d+) releases/);
                if (match) {
                    const remaining = parseInt(match[1]);
                    job.progress.completed = job.progress.total - remaining;
                    job.progress.percent = Math.round((job.progress.completed / job.progress.total) * 100);
                    console.log(`[Job ${job.id}] Progress update: ${job.progress.percent}% (${job.progress.completed}/${job.progress.total})`);
                    this.emit('progress', job.id, {
                        ...job.progress,
                        current: `Downloading ${remaining} releases...`
                    });
                }
            }
            
            if (line.includes('Downloading')) {
                const titleMatch = line.match(/Downloading.*?([^\/]+)$/);
                if (titleMatch) {
                    job.progress.current = `Downloading: ${titleMatch[1]}`;
                    console.log(`[Job ${job.id}] Current download:`, job.progress.current);
                    this.emit('progress', job.id, job.progress);
                }
            }
        }
    }
    
    createArchive(job) {
        console.log(`[Job ${job.id}] Starting archive creation`);
        job.progress.current = 'Creating archive...';
        job.progress.percent = 95;
        this.emit('progress', job.id, job.progress);
        
        const archivePath = path.join(this.tempDir, `${job.id}.zip`);
        console.log(`[Job ${job.id}] Archive path:`, archivePath);
        
        const output = fs.createWriteStream(archivePath);
        const archive = archiver('zip', { zlib: { level: 9 } });
        
        output.on('close', () => {
            console.log(`[Job ${job.id}] Archive creation completed. Size: ${archive.pointer()} bytes`);
            job.status = 'completed';
            job.downloadPath = archivePath;
            job.progress.percent = 100;
            job.progress.current = 'Archive ready for download';
            
            console.log(`[Job ${job.id}] Emitting progress and complete events`);
            this.emit('progress', job.id, job.progress);
            this.emit('complete', job.id, archivePath);
        });
        
        archive.on('error', (err) => {
            console.error(`[Job ${job.id}] Archive error:`, err);
            job.status = 'error';
            job.error = `Archive creation failed: ${err.message}`;
            this.emit('error', job.id, job.error);
        });
        
        archive.on('warning', (err) => {
            console.warn(`[Job ${job.id}] Archive warning:`, err);
        });
        
        archive.pipe(output);
        
        if (fs.existsSync(job.workDir)) {
            console.log(`[Job ${job.id}] Adding directory to archive:`, job.workDir);
            archive.directory(job.workDir, false);
        } else {
            console.error(`[Job ${job.id}] Work directory does not exist:`, job.workDir);
        }
        
        console.log(`[Job ${job.id}] Finalizing archive...`);
        archive.finalize();
    }
    
    getJob(jobId) {
        return this.jobs.get(jobId);
    }
    
    cleanupJob(jobId) {
        const job = this.jobs.get(jobId);
        if (!job) return;
        
        try {
            if (job.downloadPath && fs.existsSync(job.downloadPath)) {
                fs.unlinkSync(job.downloadPath);
            }
            
            if (job.workDir && fs.existsSync(job.workDir)) {
                fs.rmSync(job.workDir, { recursive: true, force: true });
            }
        } catch (error) {
            console.error(`Cleanup error for job ${jobId}:`, error);
        }
        
        this.jobs.delete(jobId);
    }
}

module.exports = JobManager;