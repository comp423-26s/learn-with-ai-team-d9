/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { StudentView } from './student-view.component';
import { PageTitleService } from '../../../page-title.service';
import { LayoutNavigationService } from '../../../layout/layout-navigation.service';
import {
  RECENT_DAILY_SCORES_STORAGE_KEY,
  STREAK_DATES_STORAGE_KEY,
} from './daily-practice/daily-practice.component';

describe('StudentView', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('should set the page title and show student dashboard copy', () => {
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
    expect(mockLayoutNavigation.clearContext).toHaveBeenCalled();
    expect(mockPageTitle.setTitle).toHaveBeenCalledWith('Student Dashboard');
    expect(fixture.nativeElement.textContent).toContain('Daily Challenge');
    expect(fixture.nativeElement.textContent).toContain("Try Today's Challenge!");
    expect(fixture.nativeElement.textContent).toContain('Average');
    expect(fixture.nativeElement.textContent).toContain('--');
  });

  it('should show -- for streak when no dates are stored', () => {
    const mockPageTitle = { setTitle: vi.fn() };
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

    expect(fixture.nativeElement.textContent).toContain('Streak');
    expect(fixture.nativeElement.textContent).toContain('--');
  });

  it('should show 1 day streak for a single stored date', () => {
    const today = new Date().toISOString().slice(0, 10);
    localStorage.setItem(STREAK_DATES_STORAGE_KEY, JSON.stringify([today]));

    const mockPageTitle = { setTitle: vi.fn() };
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

    expect(fixture.nativeElement.textContent).toContain('1 day');
  });

  it('should show 3 days streak for three consecutive stored dates', () => {
    const dates = ['2026-04-19', '2026-04-20', '2026-04-21'];
    localStorage.setItem(STREAK_DATES_STORAGE_KEY, JSON.stringify(dates));

    const mockPageTitle = { setTitle: vi.fn() };
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

    expect(fixture.nativeElement.textContent).toContain('3 days');
  });

  it('should count only the most recent consecutive run when there is a gap', () => {
    // Gap between 04-17 and 04-19; streak should be 2 (04-19, 04-20)
    const dates = ['2026-04-17', '2026-04-19', '2026-04-20'];
    localStorage.setItem(STREAK_DATES_STORAGE_KEY, JSON.stringify(dates));

    const mockPageTitle = { setTitle: vi.fn() };
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

    expect(fixture.nativeElement.textContent).toContain('2 days');
  });

  it('should show -- for all stats when localStorage is not available', () => {
    vi.stubGlobal('localStorage', undefined);

    TestBed.configureTestingModule({
      imports: [StudentView],
      providers: [
        provideRouter([]),
        { provide: PageTitleService, useValue: { setTitle: vi.fn() } },
        { provide: LayoutNavigationService, useValue: { clearContext: vi.fn() } },
      ],
    });

    const fixture = TestBed.createComponent(StudentView);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('--');

    vi.unstubAllGlobals();
  });

  it('should show -- for streak when streak dates storage contains a non-array JSON value', () => {
    localStorage.setItem(STREAK_DATES_STORAGE_KEY, '"not-an-array"');

    const mockPageTitle = { setTitle: vi.fn() };
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

    expect(fixture.nativeElement.textContent).toContain('--');
  });

  it('should show -- for streak when streak dates storage contains invalid JSON', () => {
    localStorage.setItem(STREAK_DATES_STORAGE_KEY, 'not valid json');

    const mockPageTitle = { setTitle: vi.fn() };
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

    expect(fixture.nativeElement.textContent).toContain('Streak');
    expect(fixture.nativeElement.textContent).toContain('--');
  });

  it('should show -- for average when scores storage contains invalid JSON', () => {
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, 'not valid json');

    const mockPageTitle = { setTitle: vi.fn() };
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

    expect(fixture.nativeElement.textContent).toContain('Average');
    expect(fixture.nativeElement.textContent).toContain('--');
  });

  it('should show -- for average when scores storage contains a non-array value', () => {
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, '"not-an-array"');

    const mockPageTitle = { setTitle: vi.fn() };
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

    expect(fixture.nativeElement.textContent).toContain('Average');
    expect(fixture.nativeElement.textContent).toContain('--');
  });

  it('should render average score from recent daily challenge results', () => {
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, JSON.stringify([90, 80, 70]));

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

    expect(fixture.nativeElement.textContent).toContain('Average');
    expect(fixture.nativeElement.textContent).toContain('80%');
  });
});
