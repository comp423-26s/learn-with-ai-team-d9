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
      activityList?: Array<{ id: number }>;
      activityListError?: boolean;
      persistedSources?: Array<{
        source_id: number;
        activity_id: number;
        filename: string | null;
        content_type: string;
        created_at: string;
      }>;
      uploadError?: boolean;
      generationJobResponse?: { job: { id: number; status: 'pending'; completed_at: null } };
    } = {},
  ) {
    const mockPageTitle = {
      setTitle: vi.fn(),
    };
    const mockLayoutNavigation = { clearContext: vi.fn() };
    const routeCourseId = options.routeCourseId === undefined ? '1' : options.routeCourseId;
    const mockRouter = { navigate: vi.fn(() => Promise.resolve(true)) };
    const mockActivityService = {
      list: vi.fn(() => {
        if (options.activityListError) {
          return Promise.reject(new Error('failed to list activities'));
        }

        return Promise.resolve(options.activityList ?? [{ id: 7 }]);
      }),
    };
    const mockStriveService = {
      listSources: vi.fn(() => Promise.resolve(options.persistedSources ?? [])),
      uploadPdfAndGenerateQuiz: vi.fn(() => {
        if (options.uploadError) {
          return Promise.reject(new Error('failed to upload source'));
        }

        return Promise.resolve(
          options.generationJobResponse ?? {
            id: 101,
            activity_id: 7,
            student_pid: 730611076,
            status: 'in_progress',
            mode: 'daily',
            module_name: null,
            topic: 'Python Basics',
            questions: [{ question_id: 1, text: 'What does def do?', choices: [] }],
          },
        );
      }),
      createSourceQuiz: vi.fn(() => {
        return Promise.resolve(
          options.generationJobResponse ?? {
            id: 202,
            activity_id: 7,
            student_pid: 730611076,
            status: 'in_progress',
            mode: 'daily',
            module_name: null,
            topic: 'Python Basics',
            questions: [{ question_id: 1, text: 'What does def do?', choices: [] }],
          },
        );
      }),
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

  it('should navigate to source quiz polling when generation returns a job', async () => {
    const { fixture, mockStriveService, mockRouter } = configureAndRender({
      generationJobResponse: { job: { id: 404, status: 'pending', completed_at: null } },
    });
    const component = fixture.componentInstance as StudentView;
    const file = new File(['fake pdf'], 'async-notes.pdf', { type: 'application/pdf' });

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

    expect(mockStriveService.setPendingSourceQuiz).not.toHaveBeenCalled();
    expect(mockRouter.navigate).toHaveBeenCalledWith(['daily-practice'], {
      relativeTo: expect.anything(),
      queryParams: { mode: 'source', jobId: 404 },
    });
  });

  it('should load persisted sources and create a quiz from saved context after refresh', async () => {
    const { fixture, mockActivityService, mockStriveService, mockRouter } = configureAndRender({
      persistedSources: [
        {
          source_id: 31,
          activity_id: 7,
          filename: 'saved-notes.pdf',
          content_type: 'application/pdf',
          created_at: '2026-04-20T12:00:00Z',
        },
      ],
    });
    const component = fixture.componentInstance as StudentView;

    await Promise.resolve();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('saved-notes.pdf');

    await (
      component as unknown as {
        createSourceBasedQuiz: () => Promise<void>;
      }
    ).createSourceBasedQuiz();
    fixture.detectChanges();

    expect(mockActivityService.list).toHaveBeenCalledWith(1);
    expect(mockStriveService.createSourceQuiz).toHaveBeenCalledWith(31, 5);
    expect(mockStriveService.uploadPdfAndGenerateQuiz).not.toHaveBeenCalled();
    expect(mockStriveService.setPendingSourceQuiz).toHaveBeenCalled();
    expect(mockRouter.navigate).toHaveBeenCalledWith(['daily-practice'], {
      relativeTo: expect.anything(),
      queryParams: { mode: 'source' },
    });
  });

  it('should fall back to a generated source name when a persisted source has no filename', async () => {
    const { fixture } = configureAndRender({
      persistedSources: [
        {
          source_id: 44,
          activity_id: 7,
          filename: null,
          content_type: 'application/pdf',
          created_at: '2026-04-20T12:00:00Z',
        },
      ],
    });

    await Promise.resolve();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Source 44');
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

  it('should show validation message for non-PDF source selection', () => {
    const { fixture } = configureAndRender();
    const component = fixture.componentInstance as StudentView;
    const file = new File(['bad'], 'notes.txt', { type: 'text/plain' });

    (
      component as unknown as {
        onSourceFileSelected: (event: Event) => void;
      }
    ).onSourceFileSelected({
      target: { files: [file] },
    } as unknown as Event);

    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Please choose a PDF source file.');
  });

  it('should trigger hidden input click when choose-file button is pressed', () => {
    const { fixture } = configureAndRender();

    const input = fixture.nativeElement.querySelector('#student-source-upload') as HTMLInputElement;
    const inputClickSpy = vi.spyOn(input, 'click');
    const chooseButtons = fixture.nativeElement.querySelectorAll(
      'button',
    ) as NodeListOf<HTMLButtonElement>;
    const chooseButton = Array.from(chooseButtons).find((button) =>
      button.textContent?.includes('Choose PDF File'),
    );

    expect(chooseButton).toBeTruthy();
    chooseButton?.click();

    expect(inputClickSpy).toHaveBeenCalled();
  });

  it('should handle empty file change events from the template', () => {
    const { fixture } = configureAndRender();
    const component = fixture.componentInstance as StudentView;

    const input = fixture.nativeElement.querySelector('#student-source-upload') as HTMLInputElement;
    const selectionSpy = vi.spyOn(
      component as unknown as { onSourceFileSelected: (event: Event) => void },
      'onSourceFileSelected',
    );

    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(selectionSpy).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).not.toContain('Selected:');
  });

  it('should trigger add source via template click and show added source list', () => {
    const { fixture } = configureAndRender();
    const component = fixture.componentInstance as StudentView;
    const file = new File(['fake pdf'], 'from-template.pdf', { type: 'application/pdf' });

    (
      component as unknown as {
        onSourceFileSelected: (event: Event) => void;
      }
    ).onSourceFileSelected({
      target: { files: [file] },
    } as unknown as Event);
    fixture.detectChanges();

    const buttons = Array.from(
      fixture.nativeElement.querySelectorAll('button'),
    ) as HTMLButtonElement[];
    const addSourceButton = buttons.find((button) =>
      button.textContent?.includes('Add Source To Context'),
    );
    expect(addSourceButton).toBeTruthy();

    addSourceButton?.click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Added sources');
    expect(fixture.nativeElement.textContent).toContain('from-template.pdf');
  });

  it('should show message when add source is called without a selected file', () => {
    const { fixture } = configureAndRender();
    const component = fixture.componentInstance as StudentView;

    (
      component as unknown as {
        addSource: () => void;
      }
    ).addSource();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Choose a PDF source before adding it.');
  });

  it('should show missing-source message when creating quiz without sources', async () => {
    const { fixture } = configureAndRender();
    const component = fixture.componentInstance as StudentView;

    await (
      component as unknown as {
        createSourceBasedQuiz: () => Promise<void>;
      }
    ).createSourceBasedQuiz();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain(
      'Add at least one source before creating a source-based quiz.',
    );
  });

  it('should show course-context error for invalid course id when creating source quiz', async () => {
    const { fixture, mockActivityService } = configureAndRender({ routeCourseId: 'invalid-id' });
    const component = fixture.componentInstance as StudentView;
    const file = new File(['fake pdf'], 'invalid-course.pdf', { type: 'application/pdf' });

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

    expect(mockActivityService.list).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain(
      'Unable to resolve course context for source upload.',
    );
  });

  it('should show no-activity message when source quiz generation has no activities', async () => {
    const { fixture, mockStriveService } = configureAndRender({ activityList: [] });
    const component = fixture.componentInstance as StudentView;
    const file = new File(['fake pdf'], 'empty-activities.pdf', { type: 'application/pdf' });

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

    expect(mockStriveService.uploadPdfAndGenerateQuiz).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain(
      'No activity is available for source-aware quiz generation.',
    );
  });

  it('should show upload failure message when source quiz creation throws', async () => {
    const { fixture, mockStriveService } = configureAndRender({ uploadError: true });
    const component = fixture.componentInstance as StudentView;
    const file = new File(['fake pdf'], 'upload-error.pdf', { type: 'application/pdf' });

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

    expect(mockStriveService.uploadPdfAndGenerateQuiz).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain(
      'Unable to add source context right now. Please try again.',
    );
  });

  it('should show creating state while template create button runs', async () => {
    let resolveActivities: ((value: Array<{ id: number }>) => void) | undefined;
    const deferredActivities = new Promise<Array<{ id: number }>>((resolve) => {
      resolveActivities = resolve;
    });

    const { fixture, mockActivityService } = configureAndRender();
    const component = fixture.componentInstance as StudentView;
    const file = new File(['fake pdf'], 'creating-state.pdf', { type: 'application/pdf' });

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

    mockActivityService.list.mockReturnValueOnce(deferredActivities);

    fixture.detectChanges();
    const createButtons = fixture.nativeElement.querySelectorAll(
      'button',
    ) as NodeListOf<HTMLButtonElement>;
    const createButton = Array.from(createButtons).find((button) =>
      button.textContent?.includes('Create Source-Based Quiz (5 Questions)'),
    );

    expect(createButton).toBeTruthy();
    createButton?.click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Creating Quiz...');

    if (resolveActivities) {
      resolveActivities([{ id: 7 }]);
    }
    await deferredActivities;
    await Promise.resolve();
  });

  it('should throw when requireSelectedSourceFile is called with no file attached', () => {
    const { fixture } = configureAndRender();
    const component = fixture.componentInstance as StudentView;

    const sourceWithNoFile = { name: 'ghost.pdf' };

    expect(() => {
      (
        component as unknown as {
          requireSelectedSourceFile: (source: { name: string }) => File;
        }
      ).requireSelectedSourceFile(sourceWithNoFile);
    }).toThrow('Selected source file is unavailable.');
  });
});
