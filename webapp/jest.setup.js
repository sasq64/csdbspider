// Jest setup file for global test configuration

// Increase timeout for integration tests that spawn processes
jest.setTimeout(60000);

// Suppress console output during tests unless in verbose mode
if (!process.env.JEST_VERBOSE) {
  global.console = {
    ...console,
    log: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
  };
}