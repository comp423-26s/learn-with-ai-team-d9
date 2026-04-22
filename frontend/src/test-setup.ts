/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { NgModule } from '@angular/core';
import { getTestBed, ɵgetCleanupHook as getCleanupHook } from '@angular/core/testing';
import { BrowserTestingModule, platformBrowserTesting } from '@angular/platform-browser/testing';
import { afterEach, beforeEach, vi } from 'vitest';

beforeEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

beforeEach(getCleanupHook(false));
afterEach(getCleanupHook(true));

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const ANGULAR_TESTBED_SETUP = Symbol.for('@learnwithai/angular-testbed-setup');

if (!(ANGULAR_TESTBED_SETUP in globalThis)) {
  Object.defineProperty(globalThis, ANGULAR_TESTBED_SETUP, {
    value: true,
    configurable: false,
    enumerable: false,
    writable: false,
  });

  @NgModule({})
  class TestModule {}

  getTestBed().initTestEnvironment([BrowserTestingModule, TestModule], platformBrowserTesting(), {
    errorOnUnknownElements: true,
    errorOnUnknownProperties: true,
  });
}

// Make debounces fast under test to avoid timing flakes without changing specs.
Object.defineProperty(globalThis, '__TEST_DEBOUNCE_MS__', {
  value: 5,
  configurable: true,
  enumerable: false,
  writable: true,
});
