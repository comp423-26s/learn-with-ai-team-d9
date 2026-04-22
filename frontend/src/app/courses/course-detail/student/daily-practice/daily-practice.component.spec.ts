/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import {
  DailyPractice,
  RECENT_DAILY_SCORES_STORAGE_KEY,
  STREAK_DATES_STORAGE_KEY,
} from './daily-practice.component';
import { PageTitleService } from '../../../../page-title.service';
import { ActivityService } from '../../activities/activity.service';
import { StriveQuizService } from './strive-quiz.service';
import { Activity } from '../../../../api/models';
import {
  QuizCreateResponse,
  QuizQuestionsResponse,
  QuizSubmitResponse,
} from './strive-quiz.models';

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

const fakeSubmitResponse: QuizSubmitResponse = {
  id: 101,
  score: 50,
  correct_count: 1,
  total_count: 2,
  feedback: [
    {
      question_id: 1,
      correct: true,
      correct_choice_id: 2,
      explanation: 'def is the Python keyword used to define functions.',
    },
    {
      question_id: 2,
      correct: false,
      correct_choice_id: 2,
      explanation: 'A dictionary stores key-value pairs in Python.',
    },
  ],
  finished_at: '2026-04-20T12:05:00Z',
};

describe('DailyPractice', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  function setup(
    options: {
      activityList?: Activity[];
      routeCourseId?: string | null;
      loadActivities?: () => Promise<Activity[]>;
      startQuizResponse?: QuizCreateResponse;
      getQuizResponse?: QuizQuestionsResponse;
      submitQuizResponse?: QuizSubmitResponse;
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
      submitQuiz: vi.fn(() => Promise.resolve(options.submitQuizResponse ?? fakeSubmitResponse)),
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

  it('should move to next question after selecting an answer', async () => {
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
      nextLabel: () => string;
      answeredCount: () => number;
    };

    expect(state.totalQuestions()).toBe(0);
    expect(state.currentQuestion()).toBeNull();
    expect(state.currentChoices()).toEqual([]);
    expect(state.hasAnsweredCurrent()).toBe(false);
    expect(state.selectedChoiceForCurrent()).toBeNull();
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

  it('should submit answers, show AI grading feedback, and restart from the first question', async () => {
    const { fixture, mockQuizService } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (
      component as unknown as { selectChoice: (questionId: number, choiceId: number) => void }
    ).selectChoice(1, 2);
    fixture.detectChanges();
    (
      component as unknown as {
        onNext: () => Promise<void>;
      }
    ).onNext();
    await flush();
    fixture.detectChanges();

    (
      component as unknown as { selectChoice: (questionId: number, choiceId: number) => void }
    ).selectChoice(2, 3);
    fixture.detectChanges();
    (
      component as unknown as {
        onNext: () => Promise<void>;
      }
    ).onNext();
    await flush();
    fixture.detectChanges();

    expect(mockQuizService.submitQuiz).toHaveBeenCalledWith(101, {
      answers: [
        { question_id: 1, selected_choice_id: 2 },
        { question_id: 2, selected_choice_id: 3 },
      ],
    });
    expect(fixture.nativeElement.textContent).toContain('Challenge complete');
    expect(fixture.nativeElement.textContent).toContain('Score: 50% (1/2 correct)');
    expect(fixture.nativeElement.textContent).toContain('You answered 2 out of 2 questions.');
    expect(fixture.nativeElement.textContent).toContain('Correct');
    expect(fixture.nativeElement.textContent).toContain('Incorrect');
    expect(fixture.nativeElement.textContent).toContain(
      'A dictionary stores key-value pairs in Python.',
    );

    const restartButton = Array.from(fixture.nativeElement.querySelectorAll('button')).find(
      (button) => (button as HTMLButtonElement).textContent?.includes('Try Again'),
    ) as HTMLButtonElement | undefined;

    expect(restartButton).toBeTruthy();
    restartButton?.click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Which keyword defines a function?');
    expect(fixture.nativeElement.textContent).not.toContain('Challenge complete');
  });

  it('should show an error when no course activities are available', async () => {
    const { fixture, mockQuizService } = setup({ activityList: [] });
    await flush();
    fixture.detectChanges();

    expect(mockQuizService.startQuiz).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Quiz unavailable');
    expect(fixture.nativeElement.textContent).toContain(
      'Unable to load challenge questions because no course activities exist.',
    );
  });

  it('should show an error when the course context is missing', async () => {
    const { fixture, mockActivityService } = setup({ routeCourseId: 'not-a-number' });
    await flush();
    fixture.detectChanges();

    expect(mockActivityService.list).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Quiz unavailable');
    expect(fixture.nativeElement.textContent).toContain(
      'Unable to load challenge questions because course context is missing.',
    );
  });

  it('should show an error when quiz generation returns no questions', async () => {
    const emptyQuiz: QuizQuestionsResponse = {
      ...fakeQuestionsResponse,
      questions: [],
    };

    const { fixture, mockQuizService } = setup({ getQuizResponse: emptyQuiz });
    await flush();
    fixture.detectChanges();

    expect(mockQuizService.startQuiz).toHaveBeenCalled();
    expect(mockQuizService.getQuiz).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Quiz unavailable');
    expect(fixture.nativeElement.textContent).toContain('The quiz service returned no questions.');
  });

  it('should show an error when the quiz API rejects', async () => {
    const { fixture, mockActivityService, mockQuizService } = setup({
      loadActivities: () => Promise.reject(new Error('network error')),
    });
    await flush();
    fixture.detectChanges();

    expect(mockActivityService.list).toHaveBeenCalled();
    expect(mockQuizService.startQuiz).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Quiz unavailable');
    expect(fixture.nativeElement.textContent).toContain(
      'Unable to load challenge questions from the Strive quiz API.',
    );
  });

  it('should show an error when quiz submission fails', async () => {
    const { fixture, mockQuizService } = setup();
    mockQuizService.submitQuiz.mockImplementation(() =>
      Promise.reject(new Error('submission failed')),
    );
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (
      component as unknown as { selectChoice: (questionId: number, choiceId: number) => void }
    ).selectChoice(1, 2);
    await (
      component as unknown as {
        onNext: () => Promise<void>;
      }
    ).onNext();
    await flush();
    fixture.detectChanges();

    (
      component as unknown as { selectChoice: (questionId: number, choiceId: number) => void }
    ).selectChoice(2, 3);
    await (
      component as unknown as {
        onNext: () => Promise<void>;
      }
    ).onNext();
    await flush();
    fixture.detectChanges();

    expect(mockQuizService.submitQuiz).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).not.toContain('Challenge complete');
    expect(fixture.nativeElement.textContent).toContain(
      'Unable to submit quiz answers for grading. Please try again.',
    );
  });

  it('should show submitting state while quiz answers are being graded', async () => {
    const deferredSubmit = createDeferred<QuizSubmitResponse>();
    const { fixture, mockQuizService } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (component as unknown as { selectChoice: (q: number, c: number) => void }).selectChoice(1, 2);
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    fixture.detectChanges();

    mockQuizService.submitQuiz.mockReturnValue(deferredSubmit.promise);
    (component as unknown as { selectChoice: (q: number, c: number) => void }).selectChoice(2, 3);
    void (component as unknown as { onNext: () => Promise<void> }).onNext();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Submitting...');

    deferredSubmit.resolve(fakeSubmitResponse);
    await flush();
    fixture.detectChanges();
  });

  it('should default scorePercent to 0 and feedbackByQuestionId to an empty map when no result exists', async () => {
    const deferred = createDeferred<Activity[]>();
    const { fixture } = setup({ loadActivities: () => deferred.promise });

    const comp = fixture.componentInstance as unknown as {
      scorePercent: () => number;
      feedbackByQuestionId: () => Map<number, unknown>;
    };

    expect(comp.scorePercent()).toBe(0);
    expect(comp.feedbackByQuestionId().size).toBe(0);

    deferred.resolve([]);
    await flush();
  });

  it('should return early from submitCurrentQuiz when no quiz is loaded', async () => {
    const deferred = createDeferred<Activity[]>();
    const { fixture, mockQuizService } = setup({ loadActivities: () => deferred.promise });

    await (
      fixture.componentInstance as unknown as {
        submitCurrentQuiz: () => Promise<void>;
      }
    ).submitCurrentQuiz();

    expect(mockQuizService.submitQuiz).not.toHaveBeenCalled();

    deferred.resolve([]);
    await flush();
  });

  it('should render a message inside the complete section when both complete and message are set', async () => {
    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const comp = fixture.componentInstance as unknown as {
      complete: { set: (v: boolean) => void };
      message: { set: (v: string) => void };
    };
    comp.complete.set(true);
    comp.message.set('Something went wrong after grading.');
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Something went wrong after grading.');
  });

  it('should render the complete state without quiz feedback when quiz data is missing', async () => {
    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as unknown as {
      complete: { set: (value: boolean) => void };
      quiz: { set: (value: QuizQuestionsResponse | null) => void };
      submissionResult: { set: (value: QuizSubmitResponse | null) => void };
    };

    component.quiz.set(null);
    component.submissionResult.set({ ...fakeSubmitResponse, feedback: [] });
    component.complete.set(true);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Challenge complete');
    expect(fixture.nativeElement.textContent).not.toContain('Quiz feedback');
  });

  it('should persist today ISO date to streak storage on quiz completion', async () => {
    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      1,
      2,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    fixture.detectChanges();

    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      2,
      3,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    fixture.detectChanges();

    const stored = localStorage.getItem(STREAK_DATES_STORAGE_KEY);
    expect(stored).not.toBeNull();
    const dates = JSON.parse(stored as string) as unknown[];
    const today = new Date().toISOString().slice(0, 10);
    expect(dates).toContain(today);
  });

  it('should not duplicate today in streak storage on repeated submissions', async () => {
    const today = new Date().toISOString().slice(0, 10);
    localStorage.setItem(STREAK_DATES_STORAGE_KEY, JSON.stringify([today]));

    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      1,
      2,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      2,
      3,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    fixture.detectChanges();

    const stored = localStorage.getItem(STREAK_DATES_STORAGE_KEY);
    const dates = JSON.parse(stored as string) as unknown[];
    expect(dates.filter((d) => d === today).length).toBe(1);
  });

  it('should skip persistence when localStorage is not available during submission', async () => {
    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    vi.stubGlobal('localStorage', undefined);

    const component = fixture.componentInstance as DailyPractice;

    (component as unknown as { selectChoice: (q: number, c: number) => void }).selectChoice(1, 2);
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    (component as unknown as { selectChoice: (q: number, c: number) => void }).selectChoice(2, 3);
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Challenge complete');

    vi.unstubAllGlobals();
  });

  it('should recover gracefully when streak storage contains invalid JSON', async () => {
    localStorage.setItem(STREAK_DATES_STORAGE_KEY, 'not valid json');

    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      1,
      2,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      2,
      3,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    fixture.detectChanges();

    const stored = localStorage.getItem(STREAK_DATES_STORAGE_KEY);
    expect(stored).not.toBeNull();
    const dates = JSON.parse(stored as string) as unknown[];
    const today = new Date().toISOString().slice(0, 10);
    expect(dates).toContain(today);
  });

  it('should not persist score when quiz returns a non-finite score', async () => {
    const nanScoreResponse = { ...fakeSubmitResponse, score: NaN };
    const { fixture } = setup({ submitQuizResponse: nanScoreResponse });
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      1,
      2,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      2,
      3,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    fixture.detectChanges();

    expect(localStorage.getItem(RECENT_DAILY_SCORES_STORAGE_KEY)).toBeNull();
  });

  it('should append score to existing scores stored from a previous session', async () => {
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, JSON.stringify([80]));

    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      1,
      2,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      2,
      3,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    fixture.detectChanges();

    const stored = localStorage.getItem(RECENT_DAILY_SCORES_STORAGE_KEY);
    expect(JSON.parse(stored as string)).toEqual([50, 80]);
  });

  it('should recover gracefully when scores storage contains invalid JSON', async () => {
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, 'not valid json');

    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      1,
      2,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    (component as unknown as { selectChoice: (qid: number, cid: number) => void }).selectChoice(
      2,
      3,
    );
    await (component as unknown as { onNext: () => Promise<void> }).onNext();
    await flush();
    fixture.detectChanges();

    const stored = localStorage.getItem(RECENT_DAILY_SCORES_STORAGE_KEY);
    expect(JSON.parse(stored as string)).toEqual([50]);
  });

  it('should persist completed daily quiz score for dashboard averages', async () => {
    const { fixture } = setup();
    await flush();
    fixture.detectChanges();

    const component = fixture.componentInstance as DailyPractice;

    (
      component as unknown as { selectChoice: (questionId: number, choiceId: number) => void }
    ).selectChoice(1, 2);
    await (
      component as unknown as {
        onNext: () => Promise<void>;
      }
    ).onNext();
    await flush();
    fixture.detectChanges();

    (
      component as unknown as { selectChoice: (questionId: number, choiceId: number) => void }
    ).selectChoice(2, 3);
    await (
      component as unknown as {
        onNext: () => Promise<void>;
      }
    ).onNext();
    await flush();
    fixture.detectChanges();

    const stored = localStorage.getItem(RECENT_DAILY_SCORES_STORAGE_KEY);
    expect(stored).not.toBeNull();
    expect(JSON.parse(stored as string)).toEqual([50]);
  });
});
