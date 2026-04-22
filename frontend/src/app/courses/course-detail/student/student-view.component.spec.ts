/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { StudentView } from './student-view.component';
import { PageTitleService } from '../../../page-title.service';
import { LayoutNavigationService } from '../../../layout/layout-navigation.service';
import { RECENT_DAILY_SCORES_STORAGE_KEY } from './daily-practice/daily-practice.component';

describe('StudentView', () => {
  const originalLocalStorage = globalThis.localStorage;

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    Object.defineProperty(globalThis, 'localStorage', {
      value: originalLocalStorage,
      configurable: true,
      writable: true,
    });
  });

  function configureAndRender() {
    const mockPageTitle = {
      setTitle: vi.fn(),
    };
    const mockLayoutNavigation = { clearContext: vi.fn() };

    TestBed.configureTestingModule({
      imports: [StudentView],
      providers: [
        provideRouter([]),
        { provide: PageTitleService, useValue: mockPageTitle },
        { provide: LayoutNavigationService, useValue: mockLayoutNavigation },
      ],
    });

    const fixture = TestBed.createComponent(StudentView);
    fixture.detectChanges();
    return { fixture, mockPageTitle, mockLayoutNavigation };
  }

  it('should set the page title and show student dashboard copy', () => {
    const { fixture, mockPageTitle, mockLayoutNavigation } = configureAndRender();

    expect(mockLayoutNavigation.clearContext).toHaveBeenCalled();
    expect(mockPageTitle.setTitle).toHaveBeenCalledWith('Student Dashboard');
    expect(fixture.nativeElement.textContent).toContain('Daily Challenge');
    expect(fixture.nativeElement.textContent).toContain("Try Today's Challenge!");
    expect(fixture.nativeElement.textContent).toContain('Average');
    expect(fixture.nativeElement.textContent).toContain('--');
  });

  it('should render average score from recent daily challenge results', () => {
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, JSON.stringify([90, 80, 70]));

    const { fixture } = configureAndRender();

    expect(fixture.nativeElement.textContent).toContain('Average');
    expect(fixture.nativeElement.textContent).toContain('80%');
  });

  it('should handle malformed and non-array stored scores safely', () => {
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, JSON.stringify({ bad: true }));
    let rendered = configureAndRender();
    expect(rendered.fixture.nativeElement.textContent).toContain('Average');
    expect(rendered.fixture.nativeElement.textContent).toContain('--');

    TestBed.resetTestingModule();
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, '{');
    rendered = configureAndRender();
    expect(rendered.fixture.nativeElement.textContent).toContain('Average');
    expect(rendered.fixture.nativeElement.textContent).toContain('--');
  });

  it('should handle missing localStorage gracefully', () => {
    vi.stubGlobal('localStorage', undefined);

    const { fixture } = configureAndRender();

    expect(fixture.nativeElement.textContent).toContain('Average');
    expect(fixture.nativeElement.textContent).toContain('--');
  });
});
