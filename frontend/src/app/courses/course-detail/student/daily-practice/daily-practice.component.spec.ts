/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { DailyPractice, RECENT_DAILY_SCORES_STORAGE_KEY } from './daily-practice.component';
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
      quizMode?: 'daily' | 'source';
      loadActivities?: () => Promise<Activity[]>;
      startQuizResponse?: QuizCreateResponse;
      getQuizResponse?: QuizQuestionsResponse;
      submitQuizResponse?: QuizSubmitResponse;
      pendingSourceQuiz?: QuizQuestionsResponse | null;
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
    const quizMode = options.quizMode ?? 'daily';

    const mockQuizService = {
      startQuiz: vi.fn(() => Promise.resolve(options.startQuizResponse ?? fakeCreateResponse)),
      getQuiz: vi.fn(() => Promise.resolve(options.getQuizResponse ?? fakeQuestionsResponse)),
      submitQuiz: vi.fn(() => Promise.resolve(options.submitQuizResponse ?? fakeSubmitResponse)),
      consumePendingSourceQuiz: vi.fn(() => options.pendingSourceQuiz ?? null),
    };

    const mockRoute = {
      snapshot: {
        queryParamMap: {
          get: (key: string) => (key === 'mode' && quizMode === 'source' ? 'source' : null),
        },
      },
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

  it('should load a source-based quiz from pending source context', async () => {
    const { fixture, mockPageTitle, mockQuizService } = setup({
      quizMode: 'source',
      pendingSourceQuiz: fakeQuestionsResponse,
    });
    await flush();
    fixture.detectChanges();

    expect(mockPageTitle.setTitle).toHaveBeenCalledWith('Source-Based Quiz');
    expect(mockQuizService.consumePendingSourceQuiz).toHaveBeenCalled();
    expect(mockQuizService.startQuiz).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Which keyword defines a function?');
  });

  it('should show an error when source-based quiz mode has no pending quiz', async () => {
    const { fixture, mockQuizService } = setup({
      quizMode: 'source',
      pendingSourceQuiz: null,
    });
    await flush();
    fixture.detectChanges();

    expect(mockQuizService.consumePendingSourceQuiz).toHaveBeenCalled();
    expect(mockQuizService.startQuiz).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain(
      'No source-based quiz is ready. Add sources from the dashboard first.',
    );
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

  it('should restart quiz state to the first question', async () => {
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
    fixture.detectChanges();

    const state = component as unknown as {
      restart: () => void;
      questionNumber: () => number;
      answeredCount: () => number;
      complete: { set: (value: boolean) => void };
      submissionResult: { set: (value: QuizSubmitResponse | null) => void };
    };

    state.complete.set(true);
    state.submissionResult.set(fakeSubmitResponse);
    state.restart();
    fixture.detectChanges();

    expect(state.questionNumber()).toBe(1);
    expect(state.answeredCount()).toBe(0);
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

    const restartButton = fixture.nativeElement.querySelector(
      'app-back-to-student-dashboard-button a',
    ) as HTMLAnchorElement | null;

    expect(restartButton).toBeTruthy();
    expect(restartButton?.textContent).toContain('Back to Student Dashboard');
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

  it('should show submitting status while final quiz submission is pending', async () => {
    const deferredSubmit = createDeferred<QuizSubmitResponse>();
    const { fixture, mockQuizService } = setup();
    mockQuizService.submitQuiz.mockReturnValueOnce(deferredSubmit.promise);
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

    const submitPromise = (
      component as unknown as {
        onNext: () => Promise<void>;
      }
    ).onNext();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Submitting...');

    deferredSubmit.resolve(fakeSubmitResponse);
    await submitPromise;
    await flush();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Challenge complete');
  });

  it('should show message content in the completed state when present', async () => {
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

    (component as unknown as { message: { set: (message: string) => void } }).message.set(
      'Review complete.',
    );
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Review complete.');
  });

  it('should expose score and feedback maps after completion', async () => {
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

    const state = component as unknown as {
      scorePercent: () => number;
      feedbackByQuestionId: () => Map<number, { correct: boolean }>;
    };

    expect(state.scorePercent()).toBe(50);
    expect(state.feedbackByQuestionId().get(1)?.correct).toBe(true);
    expect(state.feedbackByQuestionId().get(2)?.correct).toBe(false);
  });

  it('should render completion view when result metadata is missing', async () => {
    const { fixture } = setup();
    await flush();

    const component = fixture.componentInstance as DailyPractice;
    const state = component as unknown as {
      loading: { set: (value: boolean) => void };
      complete: { set: (value: boolean) => void };
      quiz: { set: (value: QuizQuestionsResponse | null) => void };
      submissionResult: { set: (value: QuizSubmitResponse | null) => void };
      selectedChoicesByQuestion: { set: (value: Record<number, number>) => void };
      message: { set: (value: string) => void };
    };

    state.loading.set(false);
    state.complete.set(true);
    state.quiz.set(fakeQuestionsResponse);
    state.submissionResult.set(null);
    state.selectedChoicesByQuestion.set({ 1: 2 });
    state.message.set('');
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Challenge complete');
    expect(fixture.nativeElement.textContent).toContain('You answered 1 out of 2 questions.');
    expect(fixture.nativeElement.textContent).not.toContain('Score:');
    expect(fixture.nativeElement.textContent).not.toContain('Correct');
  });

  it('should return early when submission runs without a quiz loaded', async () => {
    const { fixture, mockQuizService } = setup();
    await flush();

    const component = fixture.componentInstance as DailyPractice;
    const state = component as unknown as {
      quiz: { set: (value: QuizQuestionsResponse | null) => void };
      submitCurrentQuiz: () => Promise<void>;
    };

    state.quiz.set(null);
    await state.submitCurrentQuiz();
    fixture.detectChanges();

    expect(mockQuizService.submitQuiz).not.toHaveBeenCalled();
  });

  it('should compute zero score when no submission result exists', async () => {
    const { fixture } = setup();
    await flush();

    const component = fixture.componentInstance as DailyPractice;
    const state = component as unknown as {
      scorePercent: () => number;
      submissionResult: { set: (value: QuizSubmitResponse | null) => void };
    };

    state.submissionResult.set(null);
    fixture.detectChanges();

    expect(state.scorePercent()).toBe(0);
  });

  it('should render completion summary without quiz feedback details', async () => {
    const { fixture } = setup();
    await flush();

    const component = fixture.componentInstance as DailyPractice;
    const state = component as unknown as {
      loading: { set: (value: boolean) => void };
      complete: { set: (value: boolean) => void };
      quiz: { set: (value: QuizQuestionsResponse | null) => void };
      submissionResult: { set: (value: QuizSubmitResponse | null) => void };
      selectedChoicesByQuestion: { set: (value: Record<number, number>) => void };
      message: { set: (value: string) => void };
    };

    state.loading.set(false);
    state.complete.set(true);
    state.quiz.set(null);
    state.submissionResult.set(fakeSubmitResponse);
    state.selectedChoicesByQuestion.set({ 1: 2 });
    state.message.set('');
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Challenge complete');
    expect(fixture.nativeElement.textContent).toContain('Score: 50% (1/2 correct)');
    expect(fixture.nativeElement.textContent).not.toContain('Which keyword defines a function?');
  });

  it('should persist only finite previous scores and prepend the latest score', async () => {
    localStorage.setItem(
      RECENT_DAILY_SCORES_STORAGE_KEY,
      JSON.stringify([88, 'bad', null, 76, Number.POSITIVE_INFINITY]),
    );

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
    expect(JSON.parse(stored as string)).toEqual([50, 88, 76]);
  });

  it('should recover from malformed existing score history while persisting', async () => {
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, '{');

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

  it('should not persist non-finite scores', async () => {
    const { fixture } = setup({
      submitQuizResponse: {
        ...fakeSubmitResponse,
        score: Number.NaN,
      },
    });
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

    expect(localStorage.getItem(RECENT_DAILY_SCORES_STORAGE_KEY)).toBeNull();
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
