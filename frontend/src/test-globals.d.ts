// Shared test-only globals used by Vitest and unit tests.
// Declare them here so TypeScript knows about `globalThis.__TEST_DEBOUNCE_MS__`.

declare global {
	var __TEST_DEBOUNCE_MS__: number | undefined;
}

export {};
