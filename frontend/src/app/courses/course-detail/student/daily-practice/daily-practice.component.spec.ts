/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { DailyPractice } from './daily-practice.component';
import { PageTitleService } from '../../../../page-title.service';
import { ActivityService } from '../../activities/activity.service';
import { StriveQuizService } from './strive-quiz.service';
import { Activity } from '../../../../api/models';
import { QuizCreateResponse, QuizQuestionsResponse } from './strive-quiz.models';

const flush = () => new Promise((resolve) => setTimeout(resolve));

function createDeferred<T>() {
  let resolve: (value: T | PromiseLike<T>) => void;
  let reject: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });

  return {
    promise,
    resolve: resolve!,
    reject: reject!,
  };
}

const fakeStriveActivity: Activity = {
  id: 7,
  course_id: 1,
  created_at: '2026-04-20T00:00:00Z',
  release_date: '2026-04-20T00:00:00Z',
  due_date: '2026-04-21T00:00:00Z',
  late_date: null,
  title: 'Daily Strive Challenge',
  type: 'strive',
  active_submission_count: null,
};

const fakeCreateResponse: QuizCreateResponse = {
  id: 101,
  activity_id: 7,
  student_pid: 730611076,
  status: 'in_progress',
  started_at: '2026-04-20T12:00:00Z',
  question_count: 2,
  mode: 'daily',
  module_name: null,
  topic: 'Python Basics',
};

const fakeQuestionsResponse: QuizQuestionsResponse = {
  id: 101,
  activity_id: 7,
  student_pid: 730611076,
  status: 'in_progress',
  mode: 'daily',
  module_name: null,
  topic: 'Python Basics',
  questions: [
    {
      question_id: 1,
      text: 'Which keyword defines a function?',
      choices: [
        { id: 1, text: 'function' },
        { id: 2, text: 'def' },
        { id: 3, text: 'fn' },
        { id: 4, text: 'declare' },
      ],
    },
    {
      question_id: 2,
      text: 'Which structure stores key-value pairs?',
      choices: [
        { id: 1, text: 'Tuple' },
        { id: 2, text: 'Dictionary' },
        { id: 3, text: 'Set' },
        { id: 4, text: 'List' },
      ],
    },
  ],
};

describe('DailyPractice', () => {
  function setup(
    options: {
      activityList?: Activity[];
      routeCourseId?: string | null;
      loadActivities?: () => Promise<Activity[]>;
      startQuizResponse?: QuizCreateResponse;
      getQuizResponse?: QuizQuestionsResponse;
    } = {},
  ) {
    const mockPageTitle = {
      setTitle: vi.fn(),
    };

    const activityList = options.activityList ?? [fakeStriveActivity];

    const mockActivityService = {
      list: vi.fn(() => options.loadActivities?.() ?? Promise.resolve(activityList)),
    };

    const routeCourseId = options.routeCourseId === undefined ? '1' : options.routeCourseId;

    const mockQuizService = {
      startQuiz: vi.fn(() => Promise.resolve(options.startQuizResponse ?? fakeCreateResponse)),
      getQuiz: vi.fn(() => Promise.resolve(options.getQuizResponse ?? fakeQuestionsResponse)),
      submitQuiz: vi.fn(),
    };

    const mockRoute = {
      parent: {
        parent: {
          snapshot: {
            paramMap: {
              get: (key: string) => (key === 'id' ? routeCourseId : null),
            },
          },
        },
      },
    };

    TestBed.configureTestingModule({
      imports: [DailyPractice, NoopAnimationsModule],
      providers: [
        { provide: PageTitleService, useValue: mockPageTitle },
        { provide: ActivityService, useValue: mockActivityService },
        { provide: StriveQuizService, useValue: mockQuizService },
        { provide: ActivatedRoute, useValue: mockRoute },
      ],
    });

    const fixture = TestBed.createComponent(DailyPractice);
    fixture.detectChanges();

    return { fixture, mockPageTitle, mockActivityService, mockQuizService };
  }

  it('should set title and render quiz question from API response', async () => {
    const { fixture, mockPageTitle, mockQuizService } = setup();
    await flush();
    fixture.detectChanges();

    expect(mockPageTitle.setTitle).toHaveBeenCalledWith("Today's Challenge");
    expect(mockQuizService.startQuiz).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Which keyword defines a function?');
  });

  it('should show immediate feedback after selecting an answer and move to next question', async () => {
    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (
      component as unknown as { selectChoice: (questionId: number, choiceId: number) => void }
    ).selectChoice(1, 2);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Immediate Feedback');

    (
      component as unknown as {
        onNext: () => void;
      }
    ).onNext();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Which structure stores key-value pairs?');
  });

  it('should keep the current question when Next is clicked without an answer', async () => {
    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;
    (
      component as unknown as {
        onNext: () => void;
      }
    ).onNext();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Which keyword defines a function?');
  });

  it('should expose the empty loading state before data resolves', () => {
    const { fixture } = setup({ loadActivities: () => createDeferred<Activity[]>().promise });
    const component = fixture.componentInstance as DailyPractice;
    const state = component as unknown as {
      totalQuestions: () => number;
      currentQuestion: () => unknown;
      currentChoices: () => unknown[];
      hasAnsweredCurrent: () => boolean;
      selectedChoiceForCurrent: () => unknown;
      immediateFeedbackForCurrent: () => string;
      nextLabel: () => string;
      answeredCount: () => number;
    };

    expect(state.totalQuestions()).toBe(0);
    expect(state.currentQuestion()).toBeNull();
    expect(state.currentChoices()).toEqual([]);
    expect(state.hasAnsweredCurrent()).toBe(false);
    expect(state.selectedChoiceForCurrent()).toBeNull();
    expect(state.immediateFeedbackForCurrent()).toBe('');
    expect(state.nextLabel()).toBe('Finish');
    expect(state.answeredCount()).toBe(0);
  });

  it('should wire radio selection and next through the template', async () => {
    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const radioInputs = fixture.nativeElement.querySelectorAll('mat-radio-button input');
    expect(radioInputs.length).toBeGreaterThan(1);

    (radioInputs[1] as HTMLInputElement).click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Immediate Feedback');

    const nextButton = fixture.nativeElement.querySelector(
      'button[mat-flat-button]',
    ) as HTMLButtonElement;
    nextButton.click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Which structure stores key-value pairs?');
  });

  it('should show the loading state before activities resolve', async () => {
    const deferredActivities = createDeferred<Activity[]>();
    const { fixture } = setup({ loadActivities: () => deferredActivities.promise });

    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Loading challenge questions...');

    deferredActivities.resolve([fakeStriveActivity]);
    await flush();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Which keyword defines a function?');
  });

  it('should show completion state and restart from the first question', async () => {
    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (
      component as unknown as { selectChoice: (questionId: number, choiceId: number) => void }
    ).selectChoice(1, 2);
    fixture.detectChanges();
    (
      component as unknown as {
        onNext: () => void;
      }
    ).onNext();
    fixture.detectChanges();

    (
      component as unknown as { selectChoice: (questionId: number, choiceId: number) => void }
    ).selectChoice(2, 3);
    fixture.detectChanges();
    (
      component as unknown as {
        onNext: () => void;
      }
    ).onNext();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Challenge complete');
    expect(fixture.nativeElement.textContent).toContain('You answered 2 out of 2 questions.');

    const restartButton = Array.from(fixture.nativeElement.querySelectorAll('button')).find(
      (button) => (button as HTMLButtonElement).textContent?.includes('Try Again'),
    ) as HTMLButtonElement | undefined;

    expect(restartButton).toBeTruthy();
    restartButton?.click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Which keyword defines a function?');
    expect(fixture.nativeElement.textContent).not.toContain('Challenge complete');
  });

  it('should fall back to mock quiz mode when no strive activity is available', async () => {
    const { fixture, mockQuizService } = setup({ activityList: [] });
    await flush();
    fixture.detectChanges();

    expect(mockQuizService.startQuiz).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain(
      'Showing sample challenge questions while Strive activities are unavailable.',
    );
    expect(fixture.nativeElement.textContent).toContain(
      'Which keyword is used to define a function in Python?',
    );
  });

  it('should fall back when the course context is missing', async () => {
    const { fixture, mockActivityService } = setup({ routeCourseId: 'not-a-number' });
    await flush();
    fixture.detectChanges();

    expect(mockActivityService.list).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain(
      'Showing sample challenge questions because course context is missing.',
    );
  });

  it('should fall back when quiz generation returns no questions', async () => {
    const emptyQuiz: QuizQuestionsResponse = {
      ...fakeQuestionsResponse,
      questions: [],
    };

    const { fixture, mockQuizService } = setup({ getQuizResponse: emptyQuiz });
    await flush();
    fixture.detectChanges();

    expect(mockQuizService.startQuiz).toHaveBeenCalled();
    expect(mockQuizService.getQuiz).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain(
      'Showing sample challenge questions while quiz questions are being generated.',
    );
  });

  it('should fall back when the quiz API rejects', async () => {
    const { fixture, mockActivityService, mockQuizService } = setup({
      loadActivities: () => Promise.reject(new Error('network error')),
    });
    await flush();
    fixture.detectChanges();

    expect(mockActivityService.list).toHaveBeenCalled();
    expect(mockQuizService.startQuiz).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain(
      'Showing sample challenge questions while the Strive quiz API is unavailable.',
    );
  });
});
