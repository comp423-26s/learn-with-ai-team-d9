/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { DatePipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatRadioModule } from '@angular/material/radio';
import { PageTitleService } from '../../../../page-title.service';
import { LayoutNavigationService } from '../../../../layout/layout-navigation.service';
import { CourseService } from '../../../course.service';
import { ActivityService } from '../activity.service';
import { StriveQuizService } from '../../student/daily-practice/strive-quiz.service';
import {
  QuizQuestionsResponse,
  QuizSubmitResponse,
} from '../../student/daily-practice/strive-quiz.models';
import { RECENT_DAILY_SCORES_STORAGE_KEY } from '../../student/daily-practice/daily-practice.component';
import { buildActivityContextNav } from '../activity-nav';
import { Activity } from '../../../../api/models';

type QuizMode = 'standard' | 'pdf';

/** Student view for taking a Strive quiz tied to a specific activity. */
@Component({
  selector: 'app-strive-submit',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, MatButtonModule, MatCardModule, MatRadioModule],
  templateUrl: './strive-submit.component.html',
})
export class StriveSubmit {
  private readonly titleService = inject(PageTitleService);
  private readonly route = inject(ActivatedRoute);
  private readonly activityService = inject(ActivityService);
  private readonly striveQuizService = inject(StriveQuizService);
  private readonly layoutNavigation = inject(LayoutNavigationService);
  private readonly courseService = inject(CourseService);

  protected readonly courseId: number;
  protected readonly activityId: number;
  protected readonly dateTimeFormat = 'MMM d, y, h:mm a';

  // Page load state
  protected readonly loaded = signal(false);
  protected readonly loadError = signal('');

  // Mode selection
  protected readonly quizMode = signal<QuizMode | null>(null);

  // Activity metadata
  protected readonly activity = signal<Activity | null>(null);

  // Score history (read from localStorage, updated after each submission)
  protected readonly recentScores = signal<number[]>(this.readRecentScores());
  protected readonly averageScoreLabel = computed(() => {
    const scores = this.recentScores();
    if (scores.length === 0) return '--';
    return `${Math.round(scores.reduce((sum, s) => sum + s, 0) / scores.length)}%`;
  });

  // PDF upload state
  protected readonly selectedPdfFile = signal<File | null>(null);
  protected readonly pdfStatusMessage = signal('');
  protected readonly generatingPdfQuiz = signal(false);
  protected readonly selectedPdfFileName = computed(() => this.selectedPdfFile()?.name ?? null);

  // Quiz state
  protected readonly loading = signal(false);
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
    this.courseId = Number(this.route.parent?.parent?.snapshot.paramMap.get('id'));
    this.activityId = Number(this.route.snapshot.paramMap.get('activityId'));
    void this.loadData();
  }

  protected async selectStandardMode(): Promise<void> {
    this.quizMode.set('standard');
    await this.startNewQuiz();
  }

  protected selectPdfMode(): void {
    this.quizMode.set('pdf');
    this.pdfStatusMessage.set('');
  }

  protected onPdfFileSelected(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    if (file === null) {
      this.selectedPdfFile.set(null);
      return;
    }
    if (file.type !== 'application/pdf') {
      this.selectedPdfFile.set(null);
      this.pdfStatusMessage.set('Please choose a PDF file.');
      return;
    }
    this.selectedPdfFile.set(file);
    this.pdfStatusMessage.set('');
  }

  protected async generatePdfQuiz(): Promise<void> {
    const file = this.selectedPdfFile();
    if (file === null) return;

    this.generatingPdfQuiz.set(true);
    this.pdfStatusMessage.set('');
    try {
      const quiz = await this.striveQuizService.uploadPdfAndGenerateQuiz(this.activityId, file, 5);
      if (quiz.questions.length === 0) {
        this.pdfStatusMessage.set('The quiz service returned no questions from your PDF.');
        return;
      }
      this.quiz.set({
        ...quiz,
        questions: quiz.questions.map((q) => ({ ...q, choices: q.choices.slice(0, 4) })),
      });
    } catch {
      this.pdfStatusMessage.set('Unable to generate quiz from your PDF. Please try again.');
    } finally {
      this.generatingPdfQuiz.set(false);
    }
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

  protected tryAgain(): void {
    this.quizMode.set(null);
    this.quiz.set(null);
    this.submissionResult.set(null);
    this.complete.set(false);
    this.currentQuestionIndex.set(0);
    this.selectedChoicesByQuestion.set({});
    this.selectedPdfFile.set(null);
    this.pdfStatusMessage.set('');
    this.message.set('');
  }

  private async loadData(): Promise<void> {
    try {
      const [activities, courses] = await Promise.all([
        this.activityService.list(this.courseId),
        this.courseService.getMyCourses(),
      ]);
      const activityResult = activities.find((a) => a.id === this.activityId) ?? null;
      if (activityResult === null) {
        this.loadError.set('Activity not found.');
        this.layoutNavigation.clearContext();
        this.loaded.set(true);
        return;
      }
      const course = courses.find((candidate) => candidate.id === this.courseId);
      const isStaff = course?.membership.type !== 'student';
      this.activity.set(activityResult);
      this.titleService.setTitle(activityResult.title);
      this.layoutNavigation.setContextSection(
        buildActivityContextNav({
          courseId: this.courseId,
          activityId: this.activityId,
          role: isStaff ? 'staff' : 'student',
          submitPath: 'strive-submit',
        }),
      );
    } catch {
      this.loadError.set('Failed to load activity.');
      this.layoutNavigation.clearContext();
    } finally {
      this.loaded.set(true);
    }
  }

  private async startNewQuiz(): Promise<void> {
    this.loading.set(true);
    this.message.set('');
    try {
      const created = await this.striveQuizService.startQuiz(this.activityId, {
        mode: 'daily',
        question_count: 5,
      });
      const quiz = await this.striveQuizService.getQuiz(created.id);
      if (quiz.questions.length === 0) {
        this.message.set('The quiz service returned no questions.');
        return;
      }
      this.quiz.set({
        ...quiz,
        questions: quiz.questions.map((q) => ({ ...q, choices: q.choices.slice(0, 4) })),
      });
    } catch {
      this.message.set('Unable to load quiz questions. Please try again.');
    } finally {
      this.loading.set(false);
    }
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
      this.persistRecentScore(result.score);
      this.message.set('');
      this.complete.set(true);
    } catch {
      this.message.set('Unable to submit quiz answers for grading. Please try again.');
    } finally {
      this.submitting.set(false);
    }
  }

  private persistRecentScore(score: number): void {
    if (typeof localStorage === 'undefined' || !Number.isFinite(score)) return;
    const updated = [score, ...this.recentScores()].slice(0, 10);
    localStorage.setItem(RECENT_DAILY_SCORES_STORAGE_KEY, JSON.stringify(updated));
    this.recentScores.set(updated);
  }

  private readRecentScores(): number[] {
    if (typeof localStorage === 'undefined') return [];
    try {
      const raw = localStorage.getItem(RECENT_DAILY_SCORES_STORAGE_KEY);
      const parsed = raw ? (JSON.parse(raw) as unknown) : [];
      if (!Array.isArray(parsed)) return [];
      return parsed.filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
    } catch {
      return [];
    }
  }
}
