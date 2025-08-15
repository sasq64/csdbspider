import JobManager from '../jobs';
import fs from 'fs';

/**
 * Integration test for JobManager - tests the full workflow of generating a top 10 demos archive.
 * This test actually executes csdb.py and creates real archives, so it requires:
 * - Python 3 and csdb.py to be available
 * - Network access to download releases
 * - Sufficient disk space for temporary files
 */
describe('JobManager Integration Tests', () => {
  let jobManager: JobManager;
  let testJobId: string;

  beforeAll(() => {
    jobManager = new JobManager();
  });

  afterAll(() => {
    // Clean up any remaining test jobs
    if (testJobId) {
      jobManager.cleanupJob(testJobId);
    }
  });

  /**
   * Test: Generate archive for top 10 demos
   * This is a full integration test that:
   * 1. Creates a job for top 10 demos
   * 2. Monitors progress events
   * 3. Waits for completion
   * 4. Verifies the archive was created
   * 5. Checks that files were downloaded
   */
  test('should successfully generate archive for top 10 demos', async () => {
    // Track events emitted by the job manager
    const progressEvents: Array<{jobId: string, data: any}> = [];
    const errorEvents: Array<{jobId: string, error: string}> = [];
    let completionEvent: {jobId: string, downloadPath: string} | null = null;

    // Set up event listeners
    jobManager.on('progress', (jobId: string, data: any) => {
      progressEvents.push({jobId, data});
    });

    jobManager.on('error', (jobId: string, error: string) => {
      errorEvents.push({jobId, error});
    });

    jobManager.on('complete', (jobId: string, downloadPath: string) => {
      completionEvent = {jobId, downloadPath};
    });

    // Start the job
    testJobId = jobManager.startJob({
      downloadType: 'toplist',
      maxReleases: 10
    });

    // Verify job was created
    expect(testJobId).toBeDefined();
    expect(typeof testJobId).toBe('string');

    // Get the initial job state
    const job = jobManager.getJob(testJobId);
    expect(job).toBeDefined();
    expect(job!.status).toBe('running');
    expect(job!.params.downloadType).toBe('toplist');
    expect(job!.params.maxReleases).toBe(10);
    expect(job!.workDir).toContain(testJobId);

    // Verify working directory was created
    expect(fs.existsSync(job!.workDir)).toBe(true);

    // Wait for job completion (with timeout)
    const timeout = 45000; // 45 seconds
    const startTime = Date.now();
    
    while (!completionEvent && errorEvents.length === 0) {
      if (Date.now() - startTime > timeout) {
        throw new Error(`Test timed out after ${timeout}ms waiting for job completion`);
      }
      
      // Wait 500ms between checks
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    // Check for errors
    if (errorEvents.length > 0) {
      const error = errorEvents.find(e => e.jobId === testJobId);
      if (error) {
        throw new Error(`Job failed with error: ${error.error}`);
      }
    }

    // Verify completion
    expect(completionEvent).not.toBeNull();
    expect(completionEvent!.jobId).toBe(testJobId);
    expect(completionEvent!.downloadPath).toBeDefined();

    // Verify final job state
    const finalJob = jobManager.getJob(testJobId);
    expect(finalJob).toBeDefined();
    expect(finalJob!.status).toBe('completed');
    expect(finalJob!.progress.percent).toBe(100);
    expect(finalJob!.downloadPath).toBe(completionEvent!.downloadPath);
    expect(finalJob!.error).toBeNull();

    // Verify archive file exists
    expect(fs.existsSync(completionEvent!.downloadPath)).toBe(true);

    // Check archive file size (should be > 0)
    const stats = fs.statSync(completionEvent!.downloadPath);
    expect(stats.size).toBeGreaterThan(0);

    // Verify we got progress events
    expect(progressEvents.length).toBeGreaterThan(0);
    
    // Find events for our job
    const jobProgressEvents = progressEvents.filter(e => e.jobId === testJobId);
    expect(jobProgressEvents.length).toBeGreaterThan(0);

    // Check that we got meaningful progress updates
    const hasCollectedEvent = jobProgressEvents.some(e => 
      e.data.current && e.data.current.includes('Found') && e.data.current.includes('releases')
    );
    expect(hasCollectedEvent).toBe(true);

    // Verify download progress event (even if 0 files needed)
    const hasDownloadEvent = jobProgressEvents.some(e => 
      e.data.current && e.data.current.includes('Downloading') && e.data.current.includes('releases')
    );
    expect(hasDownloadEvent).toBe(true);

    // Verify final completion event
    const hasFinalEvent = jobProgressEvents.some(e => 
      e.data.current && e.data.current.includes('Archive ready for download')
    );
    expect(hasFinalEvent).toBe(true);

    // Verify we got the expected progress sequence: Found -> Downloading -> Archive ready
    expect(jobProgressEvents[0].data.current).toContain('Found');
    expect(jobProgressEvents[1].data.current).toContain('Downloading');
    expect(jobProgressEvents[2].data.current).toContain('Archive ready for download');

    // Log success details for debugging if needed
    if (process.env.JEST_VERBOSE) {
      console.log(`✓ Test completed successfully. Archive created: ${completionEvent!.downloadPath}`);
      console.log(`✓ Archive size: ${(stats.size / 1024).toFixed(2)} KB`);
      console.log(`✓ Received ${jobProgressEvents.length} progress events`);
    }

  }, 60000); // 60 second timeout for the entire test

  /**
   * Test: Download releases by group ID
   * This test verifies that downloading by group ID works correctly
   */
  test('should successfully download releases by group ID', async () => {
    const progressEvents: Array<{jobId: string, data: any}> = [];
    const errorEvents: Array<{jobId: string, error: string}> = [];
    let completionEvent: {jobId: string, downloadPath: string} | null = null;

    // Set up event listeners
    jobManager.on('progress', (jobId: string, data: any) => {
      progressEvents.push({jobId, data});
    });

    jobManager.on('error', (jobId: string, error: string) => {
      errorEvents.push({jobId, error});
    });

    jobManager.on('complete', (jobId: string, downloadPath: string) => {
      completionEvent = {jobId, downloadPath};
    });

    // Start a job using group ID (Performers = 8937)
    testJobId = jobManager.startJob({
      downloadType: 'group',
      groupId: 8937, // Performers group ID
      maxReleases: 3
    });

    // Verify job was created
    expect(testJobId).toBeDefined();
    expect(typeof testJobId).toBe('string');

    // Get the initial job state
    const job = jobManager.getJob(testJobId);
    expect(job).toBeDefined();
    expect(job!.status).toBe('running');
    expect(job!.params.downloadType).toBe('group');
    expect(job!.params.groupId).toBe(8937);
    expect(job!.params.maxReleases).toBe(3);

    // Wait for job completion
    const timeout = 30000; // 30 seconds
    const startTime = Date.now();
    
    while (!completionEvent && errorEvents.length === 0) {
      if (Date.now() - startTime > timeout) {
        throw new Error(`Test timed out after ${timeout}ms waiting for job completion`);
      }
      
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    // Check for errors
    if (errorEvents.length > 0) {
      const error = errorEvents.find(e => e.jobId === testJobId);
      if (error) {
        throw new Error(`Job failed with error: ${error.error}`);
      }
    }

    // Verify completion
    expect(completionEvent).not.toBeNull();
    expect(completionEvent!.jobId).toBe(testJobId);
    expect(completionEvent!.downloadPath).toBeDefined();

    // Verify final job state
    const finalJob = jobManager.getJob(testJobId);
    expect(finalJob).toBeDefined();
    expect(finalJob!.status).toBe('completed');
    expect(finalJob!.progress.percent).toBe(100);

    // Verify archive file exists and has content
    expect(fs.existsSync(completionEvent!.downloadPath)).toBe(true);
    const stats = fs.statSync(completionEvent!.downloadPath);
    expect(stats.size).toBeGreaterThan(0);

    // Clean up
    jobManager.cleanupJob(testJobId);
    testJobId = '';

  }, 45000); // 45 second timeout

  /**
   * Test: Download releases by event ID
   * This test verifies that downloading by event ID works correctly
   */
  test('should successfully download releases by event ID', async () => {
    const progressEvents: Array<{jobId: string, data: any}> = [];
    const errorEvents: Array<{jobId: string, error: string}> = [];
    let completionEvent: {jobId: string, downloadPath: string} | null = null;

    // Set up event listeners
    jobManager.on('progress', (jobId: string, data: any) => {
      progressEvents.push({jobId, data});
    });

    jobManager.on('error', (jobId: string, error: string) => {
      errorEvents.push({jobId, error});
    });

    jobManager.on('complete', (jobId: string, downloadPath: string) => {
      completionEvent = {jobId, downloadPath};
    });

    // Start a job using event ID (WHY2025 = 3552)
    testJobId = jobManager.startJob({
      downloadType: 'party',
      partyId: 3552, // WHY2025 event ID
      maxReleases: 2
    });

    // Verify job was created
    expect(testJobId).toBeDefined();
    expect(typeof testJobId).toBe('string');

    // Get the initial job state
    const job = jobManager.getJob(testJobId);
    expect(job).toBeDefined();
    expect(job!.status).toBe('running');
    expect(job!.params.downloadType).toBe('party');
    expect(job!.params.partyId).toBe(3552);
    expect(job!.params.maxReleases).toBe(2);

    // Wait for job completion
    const timeout = 30000; // 30 seconds
    const startTime = Date.now();
    
    while (!completionEvent && errorEvents.length === 0) {
      if (Date.now() - startTime > timeout) {
        throw new Error(`Test timed out after ${timeout}ms waiting for job completion`);
      }
      
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    // Check for errors
    if (errorEvents.length > 0) {
      const error = errorEvents.find(e => e.jobId === testJobId);
      if (error) {
        throw new Error(`Job failed with error: ${error.error}`);
      }
    }

    // Verify completion
    expect(completionEvent).not.toBeNull();
    expect(completionEvent!.jobId).toBe(testJobId);
    expect(completionEvent!.downloadPath).toBeDefined();

    // Verify final job state
    const finalJob = jobManager.getJob(testJobId);
    expect(finalJob).toBeDefined();
    expect(finalJob!.status).toBe('completed');
    expect(finalJob!.progress.percent).toBe(100);

    // Verify archive file exists and has content
    expect(fs.existsSync(completionEvent!.downloadPath)).toBe(true);
    const stats = fs.statSync(completionEvent!.downloadPath);
    expect(stats.size).toBeGreaterThan(0);

    // Clean up
    jobManager.cleanupJob(testJobId);
    testJobId = '';

  }, 45000); // 45 second timeout
});