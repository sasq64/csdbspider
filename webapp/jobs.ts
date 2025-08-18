import { spawn, ChildProcess } from 'child_process';
import fs from 'fs';
import path from 'path';
import archiver from 'archiver';
import { v4 as uuidv4 } from 'uuid';
import { EventEmitter } from 'events';

/**
 * Configuration parameters for creating a new CSDb archive generation job.
 */
interface JobParams {
    downloadType: 'toplist' | 'party' | 'group';
    partyName?: string | undefined;
    groupName?: string | undefined;
    partyId?: number | undefined;
    groupId?: number | undefined;
    maxReleases: number;
}

/**
 * Real-time progress information for a running job, used for UI updates and WebSocket broadcasts.
 */
interface JobProgress {
    percent: number;
    current: string;
    total: number;
    completed: number;
}

/**
 * Complete job state object containing all information about an archive generation task.
 * Tracks the job from creation through completion or failure, including all metadata and progress.
 */
interface Job {
    id: string;
    status: 'running' | 'completed' | 'error';
    progress: JobProgress;
    error: string | null;
    downloadPath: string | null;
    params: JobParams;
    workDir: string;
}

/**
 * Persistent archive metadata for stored archives.
 * Used to track archive history and provide download information.
 */
interface ArchiveMetadata {
    filename: string;
    createdAt: string;
    downloadType: 'toplist' | 'party' | 'group';
    params: JobParams;
    fileSize: number;
    downloadCount: number;
    actualReleases: number;
}

/**
 * Archive history structure stored in history.json.
 * Maintains list of up to 10 most recent archives.
 */
interface ArchiveHistory {
    archives: ArchiveMetadata[];
}

/**
 * Manages CSDb archive generation jobs, handling job lifecycle from creation to completion.
 * Spawns csdb.py processes, tracks progress, creates ZIP archives, and emits real-time updates.
 * Extends EventEmitter to broadcast progress, completion, and error events to connected clients.
 */
class JobManager extends EventEmitter {
    private jobs: Map<string, Job>;
    private tempDir: string;
    private archivesDir: string;
    private historyFile: string;

    /**
     * Initializes the job manager and creates the temporary directory for job files.
     */
    constructor() {
        super();
        this.jobs = new Map<string, Job>();
        this.tempDir = path.join(__dirname, 'temp');
        this.archivesDir = path.join(__dirname, 'archives');
        this.historyFile = path.join(this.archivesDir, 'history.json');

        if (!fs.existsSync(this.tempDir)) {
            fs.mkdirSync(this.tempDir, { recursive: true });
        }

        if (!fs.existsSync(this.archivesDir)) {
            fs.mkdirSync(this.archivesDir, { recursive: true });
        }
    }

    /**
     * Creates and starts a new CSDb archive generation job.
     * Creates a unique working directory, spawns the csdb.py process, and returns the job ID.
     * @param params - Job configuration including download type, names, and limits
     * @returns Unique job identifier for tracking progress
     */
    startJob(params: JobParams): string {
        const jobId = uuidv4();
        const jobDir = path.join(this.tempDir, jobId);

        const job: Job = {
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

    /**
     * Spawns the csdb.py process with appropriate arguments based on job parameters.
     * Configures command line arguments, sets up stdout/stderr monitoring, and handles process events.
     * @param job - The job object containing configuration and state
     */
    private executeCSDb(job: Job): void {
        const { downloadType, partyName, groupName, partyId, groupId, maxReleases } = job.params;
        const csdbPath = path.join(__dirname, '..', '..', 'csdb.py');

        let args: string[] = [csdbPath, '-m', maxReleases.toString()];

        switch (downloadType) {
            case 'toplist':
                args.push('-l', 'demo');
                break;
            case 'party':
                if (partyId !== undefined) {
                    args.push('-e', partyId.toString());
                } else if (partyName) {
                    args.push('-e', partyName);
                }
                break;
            case 'group':
                if (groupId !== undefined) {
                    args.push('-g', groupId.toString());
                } else if (groupName) {
                    args.push('-g', groupName);
                }
                break;
        }

        // Template patterns for different download types - edit these as needed
        const templates = {
            toplist: `${job.workDir}/{rank:03}. {group} - {title}{ ({year})}`,
            party: `${job.workDir}/{event}/{compo}/{{place:02}. }{group} - {title}`,
            group: `${job.workDir}/{group}/{qyear} - {title} [{type}]`,
        };

        args.push('-t', templates[downloadType]);

        console.log(`[Job ${job.id}] Starting CSDb with command: python3 ${args.join(' ')}`);
        console.log(`[Job ${job.id}] Working directory: ${job.workDir}`);
        console.log(`[Job ${job.id}] CSDb script path: ${csdbPath}`);

        const csdbProcess: ChildProcess = spawn('python3', args, {
            cwd: path.join(__dirname, '..', '..'),
            stdio: ['pipe', 'pipe', 'pipe']
        });

        let stdoutBuffer = '';
        let stderrBuffer = '';

        csdbProcess.stdout?.on('data', (data) => {
            const output = data.toString();
            console.log(`[Job ${job.id}] CSDb stdout:`, output);
            stdoutBuffer += output;
            this.parseProgress(job, stdoutBuffer);
        });

        csdbProcess.stderr?.on('data', (data) => {
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

    /**
     * Parses csdb.py stdout output to extract progress information and emit updates.
     * Monitors for collection completion, download progress, and current file being processed.
     * @param job - The job being monitored
     * @param output - Raw stdout output from csdb.py process
     */
    private parseProgress(job: Job, output: string): void {
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

    /**
     * Creates a ZIP archive from the downloaded releases in the job's working directory.
     * Uses maximum compression and handles archive creation events, updating progress to 100% on completion.
     * @param job - The job containing the working directory to archive
     */
    private createArchive(job: Job): void {
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

            console.log(`[Job ${job.id}] Saving archive to permanent storage`);
            this.saveArchivePermanently(job, archivePath, archive.pointer());

            console.log(`[Job ${job.id}] Emitting progress and complete events`);
            this.emit('progress', job.id, job.progress);
            this.emit('complete', job.id, archivePath);
        });

        archive.on('error', (err: Error) => {
            console.error(`[Job ${job.id}] Archive error:`, err);
            job.status = 'error';
            job.error = `Archive creation failed: ${err.message}`;
            this.emit('error', job.id, job.error);
        });

        archive.on('warning', (err: Error) => {
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

    /**
     * Retrieves a job by its unique identifier.
     * @param jobId - The unique job identifier
     * @returns The job object or undefined if not found
     */
    getJob(jobId: string): Job | undefined {
        return this.jobs.get(jobId);
    }

    getTodayString(): string {
        const now = new Date();

        const year = now.getFullYear();
        const month = new Intl.DateTimeFormat("en", { month: "short" })
            .format(now)
            .toLowerCase();
        const day = now.getDate();

        return `${year}.${month}.${day}`;
    }
    /**
     * Saves an archive permanently to the archives directory and updates history.
     * Creates a timestamped filename and maintains the 10 most recent archives.
     * @param job - The completed job object
     * @param tempArchivePath - Path to the temporary archive file
     * @param fileSize - Size of the archive in bytes
     */
    private saveArchivePermanently(job: Job, tempArchivePath: string, fileSize: number): void {
        try {
            const timestamp = this.getTodayString();
            let archiveParam = '';

            switch (job.params.downloadType) {
                case 'toplist':
                    archiveParam = 'toplist';
                    break;
                case 'party':
                    archiveParam = job.params.partyName || job.params.partyId?.toString() || 'unknown-party';
                    break;
                case 'group':
                    archiveParam = job.params.groupName || job.params.groupId?.toString() || 'unknown-group';
                    break;
            }

            const actualReleases = job.progress.total || job.params.maxReleases;
            const filename = `csdb-${archiveParam}-${actualReleases}-${timestamp}.zip`
                .replace(/[^\w\-_.]/g, '-');
            const permanentPath = path.join(this.archivesDir, filename);

            fs.copyFileSync(tempArchivePath, permanentPath);
            console.log(`[Job ${job.id}] Archive saved as: ${filename}`);

            const metadata: ArchiveMetadata = {
                filename,
                createdAt: new Date().toISOString(),
                downloadType: job.params.downloadType,
                params: job.params,
                fileSize,
                downloadCount: 0,
                actualReleases
            };

            this.updateArchiveHistory(metadata);

        } catch (error) {
            console.error(`[Job ${job.id}] Failed to save archive permanently:`, error);
        }
    }

    /**
     * Updates the archive history file with new metadata and maintains the 10 archive limit.
     * @param newMetadata - Metadata for the new archive
     */
    private updateArchiveHistory(newMetadata: ArchiveMetadata): void {
        try {
            let history: ArchiveHistory = { archives: [] };

            if (fs.existsSync(this.historyFile)) {
                const data = fs.readFileSync(this.historyFile, 'utf8');
                history = JSON.parse(data);
            }

            history.archives.unshift(newMetadata);

            if (history.archives.length > 10) {
                const oldArchives = history.archives.slice(10);
                for (const oldArchive of oldArchives) {
                    const oldPath = path.join(this.archivesDir, oldArchive.filename);
                    if (fs.existsSync(oldPath)) {
                        fs.unlinkSync(oldPath);
                        console.log(`Deleted old archive: ${oldArchive.filename}`);
                    }
                }
                history.archives = history.archives.slice(0, 10);
            }

            fs.writeFileSync(this.historyFile, JSON.stringify(history, null, 2));
            console.log(`Updated archive history with ${newMetadata.filename}`);

        } catch (error) {
            console.error('Failed to update archive history:', error);
        }
    }

    /**
     * Retrieves the list of archived files with metadata.
     * @returns Array of archive metadata objects
     */
    getArchiveHistory(): ArchiveMetadata[] {
        try {
            if (!fs.existsSync(this.historyFile)) {
                return [];
            }

            const data = fs.readFileSync(this.historyFile, 'utf8');
            const history: ArchiveHistory = JSON.parse(data);
            return history.archives;

        } catch (error) {
            console.error('Failed to read archive history:', error);
            return [];
        }
    }

    /**
     * Increments the download count for a specific archive.
     * @param filename - Name of the archive file
     */
    incrementDownloadCount(filename: string): void {
        try {
            console.log(`[JobManager] Attempting to increment download count for: ${filename}`);

            if (!fs.existsSync(this.historyFile)) {
                console.log(`[JobManager] History file does not exist: ${this.historyFile}`);
                return;
            }

            const data = fs.readFileSync(this.historyFile, 'utf8');
            const history: ArchiveHistory = JSON.parse(data);

            console.log(`[JobManager] Found ${history.archives.length} archives in history`);
            console.log(`[JobManager] Looking for archive with filename: ${filename}`);

            const archive = history.archives.find(a => a.filename === filename);
            if (archive) {
                archive.downloadCount++;
                fs.writeFileSync(this.historyFile, JSON.stringify(history, null, 2));
                console.log(`[JobManager] Incremented download count for ${filename} to ${archive.downloadCount}`);
            } else {
                console.log(`[JobManager] Archive not found in history: ${filename}`);
                console.log(`[JobManager] Available filenames:`, history.archives.map(a => a.filename));
            }

        } catch (error) {
            console.error('[JobManager] Failed to increment download count:', error);
        }
    }

    /**
     * Removes a job and cleans up all associated files and directories.
     * Deletes the ZIP archive, working directory, and removes the job from memory.
     * Called automatically after successful download to prevent disk space accumulation.
     * @param jobId - The unique job identifier to clean up
     */
    cleanupJob(jobId: string): void {
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

export default JobManager;
