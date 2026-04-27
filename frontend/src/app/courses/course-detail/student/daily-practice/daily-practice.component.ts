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
import { QuizQuestionsResponse, QuizSubmitResponse } from './strive-quiz.models';
import { StriveQuizService } from './strive-quiz.service';

export const RECENT_DAILY_SCORES_STORAGE_KEY = 'lwai-recent-daily-scores';
const MAX_RECENT_DAILY_SCORES = 10;

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
  private readonly sourceQuizMode = this.route.snapshot.queryParamMap.get('mode') === 'source';
  protected readonly isSourceQuizMode = this.sourceQuizMode;

  protected readonly loading = signal(true);
  protected readonly submitting = signal(false);
  protected readonly message = signal('');
  protected readonly quiz = signal<QuizQuestionsResponse | null>(null);
  protected readonly submissionResult = signal<QuizSubmitResponse | null>(null);
  protected readonly currentQuestionIndex = signal(0);
  protected readonly selectedChoicesByQuestion = signal<Record<number, number>>({});
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
  protected readonly nextLabel = computed(() =>
    this.questionNumber() >= this.totalQuestions() ? 'Finish' : 'Next',
  );
  protected readonly answeredCount = computed(
    () => Object.keys(this.selectedChoicesByQuestion()).length,
  );
  protected readonly scorePercent = computed(() => Math.round(this.submissionResult()?.score ?? 0));
  protected readonly feedbackByQuestionId = computed(() => {
    const feedback = this.submissionResult()?.feedback ?? [];
    return new Map(feedback.map((entry) => [entry.question_id, entry]));
  });

  constructor() {
    this.titleService.setTitle(this.sourceQuizMode ? 'Source-Based Quiz' : "Today's Challenge");
    void this.loadChallenge();
  }

  protected selectChoice(questionId: number, choiceId: number): void {
    this.selectedChoicesByQuestion.update((state) => ({
      ...state,
      [questionId]: choiceId,
    }));
  }

  protected async onNext(): Promise<void> {
    if (!this.hasAnsweredCurrent()) return;

    if (this.questionNumber() >= this.totalQuestions()) {
      await this.submitCurrentQuiz();
      return;
    }

    this.currentQuestionIndex.update((index) => index + 1);
  }

  protected restart(): void {
    this.currentQuestionIndex.set(0);
    this.selectedChoicesByQuestion.set({});
    this.submissionResult.set(null);
    this.complete.set(false);
  }

  private async loadChallenge(): Promise<void> {
    if (this.sourceQuizMode) {
      this.loadSourceChallenge();
      return;
    }

    const courseId = Number(this.route.parent?.parent?.snapshot.paramMap.get('id'));

    if (Number.isNaN(courseId)) {
      this.setLoadError('Unable to load challenge questions because course context is missing.');
      return;
    }

    try {
      const activities = await this.activityService.list(courseId);
      const quizActivity = activities[0] ?? null;

      if (quizActivity === null) {
        this.setLoadError('Unable to load challenge questions because no course activities exist.');
        return;
      }

      const createdQuiz = await this.striveQuizService.startQuiz(quizActivity.id, {
        mode: 'daily',
        question_count: 5,
      });
      const quiz = await this.striveQuizService.getQuiz(createdQuiz.id);

      this.applyLoadedQuiz(quiz);
    } catch {
      this.setLoadError('Unable to load challenge questions from the Strive quiz API.');
    } finally {
      this.loading.set(false);
    }
  }

  private loadSourceChallenge(): void {
    const sourceQuiz = this.striveQuizService.consumePendingSourceQuiz();
    if (sourceQuiz === null) {
      this.setLoadError('No source-based quiz is ready. Add sources from the dashboard first.');
      return;
    }

    this.applyLoadedQuiz(sourceQuiz);
    this.loading.set(false);
  }

  private applyLoadedQuiz(quiz: QuizQuestionsResponse): void {
    if (quiz.questions.length === 0) {
      this.setLoadError('The quiz service returned no questions.');
      return;
    }

    this.quiz.set({
      ...quiz,
      questions: quiz.questions.map((question) => ({
        ...question,
        choices: question.choices.slice(0, 4),
      })),
    });
    this.submissionResult.set(null);
    this.message.set('');
  }

  private async submitCurrentQuiz(): Promise<void> {
    const quiz = this.quiz();
    if (quiz === null) return;

    this.submitting.set(true);

    try {
      const answers = quiz.questions.map((question) => ({
        question_id: question.question_id,
        selected_choice_id: this.selectedChoicesByQuestion()[question.question_id],
      }));

      const result = await this.striveQuizService.submitQuiz(quiz.id, { answers });
      this.submissionResult.set(result);
      this.persistRecentDailyScore(result.score);
      this.message.set('');
      this.complete.set(true);
    } catch {
      this.message.set('Unable to submit quiz answers for grading. Please try again.');
    } finally {
      this.submitting.set(false);
    }
  }

  private persistRecentDailyScore(score: number): void {
    if (typeof localStorage === 'undefined' || !Number.isFinite(score)) {
      return;
    }

    let existingScores: number[] = [];
    try {
      const raw = localStorage.getItem(RECENT_DAILY_SCORES_STORAGE_KEY);
      const parsed = raw ? (JSON.parse(raw) as unknown) : [];
      if (Array.isArray(parsed)) {
        existingScores = parsed.filter(
          (value): value is number => typeof value === 'number' && Number.isFinite(value),
        );
      }
    } catch {
      existingScores = [];
    }

    const updated = [score, ...existingScores].slice(0, MAX_RECENT_DAILY_SCORES);
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, JSON.stringify(updated));
  }

  private setLoadError(message: string): void {
    this.quiz.set(null);
    this.message.set(message);
    this.loading.set(false);
  }
}
