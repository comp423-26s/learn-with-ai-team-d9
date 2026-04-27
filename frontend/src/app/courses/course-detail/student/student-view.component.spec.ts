/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { StudentView } from './student-view.component';
import { PageTitleService } from '../../../page-title.service';
import { LayoutNavigationService } from '../../../layout/layout-navigation.service';
import { RECENT_DAILY_SCORES_STORAGE_KEY } from './daily-practice/daily-practice.component';
import { ActivityService } from '../activities/activity.service';
import { StriveQuizService } from './daily-practice/strive-quiz.service';

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

  function configureAndRender(
    options: {
      routeCourseId?: string | null;
      activeChildPath?: string | null;
    } = {},
  ) {
    const mockPageTitle = {
      setTitle: vi.fn(),
    };
    const mockLayoutNavigation = { clearContext: vi.fn() };
    const routeCourseId = options.routeCourseId === undefined ? '1' : options.routeCourseId;
    const mockRouter = { navigate: vi.fn(() => Promise.resolve(true)) };
    const mockActivityService = {
      list: vi.fn(() => Promise.resolve([{ id: 7 }])),
    };
    const mockStriveService = {
      uploadPdfAndGenerateQuiz: vi.fn(() =>
        Promise.resolve({
          id: 101,
          activity_id: 7,
          student_pid: 730611076,
          status: 'in_progress',
          mode: 'daily',
          module_name: null,
          topic: 'Python Basics',
          questions: [{ question_id: 1, text: 'What does def do?', choices: [] }],
        }),
      ),
      setPendingSourceQuiz: vi.fn(),
    };
    const mockRoute = {
      firstChild:
        options.activeChildPath === null
          ? null
          : options.activeChildPath
            ? { snapshot: { routeConfig: { path: options.activeChildPath } } }
            : null,
      parent: {
        snapshot: {
          paramMap: {
            get: (key: string) => (key === 'id' ? routeCourseId : null),
          },
        },
      },
    };

    TestBed.configureTestingModule({
      imports: [StudentView],
      providers: [
        { provide: PageTitleService, useValue: mockPageTitle },
        { provide: LayoutNavigationService, useValue: mockLayoutNavigation },
        { provide: Router, useValue: mockRouter },
        { provide: ActivatedRoute, useValue: mockRoute },
        { provide: ActivityService, useValue: mockActivityService },
        { provide: StriveQuizService, useValue: mockStriveService },
      ],
    });

    const fixture = TestBed.createComponent(StudentView);
    fixture.detectChanges();
    return {
      fixture,
      mockPageTitle,
      mockLayoutNavigation,
      mockRouter,
      mockActivityService,
      mockStriveService,
    };
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

  it('should hide dashboard sections while the quiz child route is active', () => {
    const { fixture } = configureAndRender({ activeChildPath: 'daily-practice' });

    expect(fixture.nativeElement.textContent).not.toContain('Daily Challenge');
    expect(fixture.nativeElement.textContent).not.toContain('Source Context');
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

  it('should add a selected source and create a source-based quiz', async () => {
    const { fixture, mockActivityService, mockStriveService, mockRouter } = configureAndRender();
    const component = fixture.componentInstance as StudentView;
    const file = new File(['fake pdf'], 'lesson-notes.pdf', { type: 'application/pdf' });

    (
      component as unknown as {
        onSourceFileSelected: (event: Event) => void;
      }
    ).onSourceFileSelected({
      target: { files: [file] },
    } as unknown as Event);

    (
      component as unknown as {
        addSource: () => void;
      }
    ).addSource();

    await (
      component as unknown as {
        createSourceBasedQuiz: () => Promise<void>;
      }
    ).createSourceBasedQuiz();
    fixture.detectChanges();

    expect(mockActivityService.list).toHaveBeenCalledWith(1);
    expect(mockStriveService.uploadPdfAndGenerateQuiz).toHaveBeenCalledWith(7, file, 5);
    expect(mockStriveService.setPendingSourceQuiz).toHaveBeenCalled();
    expect(mockRouter.navigate).toHaveBeenCalledWith(['daily-practice'], {
      relativeTo: expect.anything(),
      queryParams: { mode: 'source' },
    });
    expect(fixture.nativeElement.textContent).toContain('lesson-notes.pdf');
    expect(fixture.nativeElement.textContent).toContain('Create Source-Based Quiz (5 Questions)');
  });

  it('should display selected file name before adding it to sources', () => {
    const { fixture } = configureAndRender();
    const component = fixture.componentInstance as StudentView;
    const file = new File(['fake pdf'], 'my-document.pdf', { type: 'application/pdf' });

    expect(fixture.nativeElement.textContent).not.toContain('Selected:');

    (
      component as unknown as {
        onSourceFileSelected: (event: Event) => void;
      }
    ).onSourceFileSelected({
      target: { files: [file] },
    } as unknown as Event);

    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Selected: my-document.pdf');
  });
});
