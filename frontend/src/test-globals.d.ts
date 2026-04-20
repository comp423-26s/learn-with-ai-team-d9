declare global {
  // Test harness may set this to speed up debounce timers during tests.
  var __TEST_DEBOUNCE_MS__: number | undefined;
}

export {};
