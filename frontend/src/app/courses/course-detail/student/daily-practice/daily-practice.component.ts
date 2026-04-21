/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatRadioModule } from '@angular/material/radio';
import { computed, signal } from '@angular/core';
import { PageTitleService } from '../../../../page-title.service';
import { ActivityService } from '../../activities/activity.service';
import { Activity } from '../../../../api/models';
import { QuizQuestionsResponse } from './strive-quiz.models';
import { StriveQuizService } from './strive-quiz.service';

const IMMEDIATE_FEEDBACK_PLACEHOLDER =
  'Good effort. Detailed feedback will be available in the next iteration.';

const FALLBACK_QUIZ: QuizQuestionsResponse = {
  id: 0,
  activity_id: 0,
  student_pid: 0,
  status: 'in_progress',
  mode: 'daily',
  module_name: null,
  topic: 'Python Basics',
  questions: [
    {
      question_id: 1,
      text: 'Which keyword is used to define a function in Python?',
      choices: [
        { id: 1, text: 'function' },
        { id: 2, text: 'def' },
        { id: 3, text: 'lambda' },
        { id: 4, text: 'fun' },
      ],
    },
    {
      question_id: 2,
      text: 'Which data structure stores key-value pairs?',
      choices: [
        { id: 1, text: 'List' },
        { id: 2, text: 'Tuple' },
        { id: 3, text: 'Dictionary' },
        { id: 4, text: 'Set' },
      ],
    },
    {
      question_id: 3,
      text: 'What does len([1, 2, 3, 4]) return?',
      choices: [
        { id: 1, text: '3' },
        { id: 2, text: '4' },
        { id: 3, text: '5' },
        { id: 4, text: 'Error' },
      ],
    },
  ],
};

/** Placeholder page for the daily-practice experience. */
@Component({
  selector: 'app-daily-practice',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, MatCardModule, MatRadioModule],
  templateUrl: './daily-practice.component.html',
})
export class DailyPractice {
  private readonly titleService = inject(PageTitleService);
  private readonly route = inject(ActivatedRoute);
  private readonly activityService = inject(ActivityService);
  private readonly striveQuizService = inject(StriveQuizService);

  protected readonly loading = signal(true);
  protected readonly message = signal('');
  protected readonly usingMockData = signal(false);
  protected readonly quiz = signal<QuizQuestionsResponse | null>(null);
  protected readonly currentQuestionIndex = signal(0);
  protected readonly selectedChoicesByQuestion = signal<Record<number, number>>({});
  protected readonly immediateFeedbackByQuestion = signal<Record<number, string>>({});
  protected readonly complete = signal(false);

  protected readonly totalQuestions = computed(() => this.quiz()?.questions.length ?? 0);
  protected readonly currentQuestion = computed(
    () => this.quiz()?.questions[this.currentQuestionIndex()] ?? null,
  );
  protected readonly currentChoices = computed(
    () => this.currentQuestion()?.choices.slice(0, 4) ?? [],
  );
  protected readonly questionNumber = computed(() => this.currentQuestionIndex() + 1);
  protected readonly hasAnsweredCurrent = computed(() => {
    const question = this.currentQuestion();
    if (question === null) return false;
    return this.selectedChoicesByQuestion()[question.question_id] !== undefined;
  });
  protected readonly selectedChoiceForCurrent = computed(() => {
    const question = this.currentQuestion();
    if (question === null) return null;
    return this.selectedChoicesByQuestion()[question.question_id] ?? null;
  });
  protected readonly immediateFeedbackForCurrent = computed(() => {
    const question = this.currentQuestion();
    if (question === null) return '';
    return this.immediateFeedbackByQuestion()[question.question_id] ?? '';
  });
  protected readonly nextLabel = computed(() =>
    this.questionNumber() >= this.totalQuestions() ? 'Finish' : 'Next',
  );
  protected readonly answeredCount = computed(
    () => Object.keys(this.selectedChoicesByQuestion()).length,
  );

  constructor() {
    this.titleService.setTitle("Today's Challenge");
    void this.loadChallenge();
  }

  protected selectChoice(questionId: number, choiceId: number): void {
    this.selectedChoicesByQuestion.update((state) => ({
      ...state,
      [questionId]: choiceId,
    }));
    this.immediateFeedbackByQuestion.update((state) => ({
      ...state,
      [questionId]: IMMEDIATE_FEEDBACK_PLACEHOLDER,
    }));
  }

  protected onNext(): void {
    if (!this.hasAnsweredCurrent()) return;

    if (this.questionNumber() >= this.totalQuestions()) {
      this.complete.set(true);
      return;
    }

    this.currentQuestionIndex.update((index) => index + 1);
  }

  protected restart(): void {
    this.currentQuestionIndex.set(0);
    this.selectedChoicesByQuestion.set({});
    this.immediateFeedbackByQuestion.set({});
    this.complete.set(false);
  }

  private async loadChallenge(): Promise<void> {
    const courseId = Number(this.route.parent?.parent?.snapshot.paramMap.get('id'));

    if (Number.isNaN(courseId)) {
      this.loadFallbackQuiz(
        'Showing sample challenge questions because course context is missing.',
      );
      return;
    }

    try {
      const activities = await this.activityService.list(courseId);
      const striveActivity = this.findStriveActivity(activities);

      if (striveActivity === null) {
        this.loadFallbackQuiz(
          'Showing sample challenge questions while Strive activities are unavailable.',
        );
        return;
      }

      const createdQuiz = await this.striveQuizService.startQuiz(striveActivity.id, {
        mode: 'daily',
        question_count: 5,
      });
      const quiz = await this.striveQuizService.getQuiz(createdQuiz.id);

      if (quiz.questions.length === 0) {
        this.loadFallbackQuiz(
          'Showing sample challenge questions while quiz questions are being generated.',
        );
        return;
      }

      this.quiz.set({
        ...quiz,
        questions: quiz.questions.map((question) => ({
          ...question,
          choices: question.choices.slice(0, 4),
        })),
      });
      this.message.set('');
      this.usingMockData.set(false);
    } catch {
      this.loadFallbackQuiz(
        'Showing sample challenge questions while the Strive quiz API is unavailable.',
      );
    } finally {
      this.loading.set(false);
    }
  }

  private findStriveActivity(activities: Activity[]): Activity | null {
    const match = activities.find((activity) => activity.type.toLowerCase().includes('strive'));
    return match ?? null;
  }

  private loadFallbackQuiz(message: string): void {
    this.quiz.set(FALLBACK_QUIZ);
    this.message.set(message);
    this.usingMockData.set(true);
    this.loading.set(false);
  }
}
