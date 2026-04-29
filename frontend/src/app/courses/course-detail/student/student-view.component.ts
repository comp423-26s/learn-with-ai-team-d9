/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { Component, ChangeDetectionStrategy, computed, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { ActivatedRoute, Router, RouterLink, RouterOutlet } from '@angular/router';
import { PageTitleService } from '../../../page-title.service';
import { LayoutNavigationService } from '../../../layout/layout-navigation.service';
import { RECENT_DAILY_SCORES_STORAGE_KEY } from './daily-practice/daily-practice.component';
import { ActivityService } from '../activities/activity.service';
import { SourceSummary, StriveQuizService } from './daily-practice/strive-quiz.service';

type StudentTopLevelStat = {
  label: string;
  value: string;
  description: string;
};

type UploadedSource = {
  name: string;
  file?: File;
  sourceId?: number;
  activityId?: number;
  contentType?: string;
  createdAt?: string;
};

/** Student-facing dashboard with a daily challenge call to action and mock performance stats. */
@Component({
  selector: 'app-student-view',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, MatCardModule, RouterLink, RouterOutlet],
  templateUrl: './student-view.component.html',
})
export class StudentView {
  private titleService = inject(PageTitleService);
  private layoutNavigation = inject(LayoutNavigationService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private activityService = inject(ActivityService);
  private striveQuizService = inject(StriveQuizService);
  private readonly recentDailyScores = this.readRecentDailyScores();

  protected readonly selectedSourceFile = signal<File | null>(null);
  protected readonly uploadedSources = signal<UploadedSource[]>([]);
  protected readonly sourceStatusMessage = signal('');
  protected readonly creatingSourceQuiz = signal(false);

  protected readonly selectedSourceFileName = computed(() => {
    const file = this.selectedSourceFile();
    return file ? file.name : null;
  });

  protected readonly topLevelStats = computed<StudentTopLevelStat[]>(() => [
    {
      label: 'Streak',
      value: '6 days',
      description: 'Consecutive daily challenges completed',
    },
    {
      label: 'Rank',
      value: '#14',
      description: 'Leaderboard position among active learners',
    },
    {
      label: 'Average',
      value: this.averageScoreLabel(),
      description: 'Average score across recent daily challenges',
    },
  ]);

  constructor() {
    this.layoutNavigation.clearContext();
    this.titleService.setTitle('Student Dashboard');
    void this.loadPersistedSources();
  }

  protected isQuizRouteActive(): boolean {
    return this.route.firstChild !== null;
  }

  protected onSourceFileSelected(event: Event): void {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0] ?? null;

    if (file === null) {
      this.selectedSourceFile.set(null);
      return;
    }

    if (file.type !== 'application/pdf') {
      this.selectedSourceFile.set(null);
      this.sourceStatusMessage.set('Please choose a PDF source file.');
      return;
    }

    this.selectedSourceFile.set(file);
    this.sourceStatusMessage.set('');
  }

  protected addSource(): void {
    const file = this.selectedSourceFile();
    if (file === null) {
      this.sourceStatusMessage.set('Choose a PDF source before adding it.');
      return;
    }

    this.uploadedSources.update((existing) => [{ name: file.name, file }, ...existing]);
    this.sourceStatusMessage.set(`Added source "${file.name}".`);
    this.selectedSourceFile.set(null);
  }

  protected async createSourceBasedQuiz(): Promise<void> {
    const source = this.uploadedSources()[0] ?? null;
    if (source === null) {
      this.sourceStatusMessage.set('Add at least one source before creating a source-based quiz.');
      return;
    }

    const courseId = Number(this.route.parent?.snapshot.paramMap.get('id'));
    if (Number.isNaN(courseId)) {
      this.sourceStatusMessage.set('Unable to resolve course context for source upload.');
      return;
    }

    this.creatingSourceQuiz.set(true);
    this.sourceStatusMessage.set('');

    try {
      const activities = await this.activityService.list(courseId);
      const quizActivity = activities[0] ?? null;

      if (quizActivity === null) {
        this.sourceStatusMessage.set('No activity is available for source-aware quiz generation.');
        return;
      }

      const quiz =
        source.sourceId !== undefined
          ? await this.striveQuizService.createSourceQuiz(source.sourceId, 5)
          : await this.striveQuizService.uploadPdfAndGenerateQuiz(
              quizActivity.id,
              this.requireSelectedSourceFile(source),
              5,
            );
      this.striveQuizService.setPendingSourceQuiz(quiz);
      this.sourceStatusMessage.set(`Created a 5-question source-based quiz from "${source.name}".`);
      await this.router.navigate(['daily-practice'], {
        relativeTo: this.route,
        queryParams: { mode: 'source' },
      });
    } catch {
      this.sourceStatusMessage.set('Unable to add source context right now. Please try again.');
    } finally {
      this.creatingSourceQuiz.set(false);
    }
  }

  private async loadPersistedSources(): Promise<void> {
    try {
      const sources = await this.striveQuizService.listSources();
      this.uploadedSources.update((existing) => [
        ...sources.map((source) => this.toUploadedSource(source)),
        ...existing.filter((source) => source.file !== undefined),
      ]);
    } catch {
      // Keep the dashboard usable even if saved sources cannot be loaded yet.
    }
  }

  private toUploadedSource(source: SourceSummary): UploadedSource {
    return {
      sourceId: source.source_id,
      activityId: source.activity_id,
      contentType: source.content_type,
      createdAt: source.created_at,
      name: source.filename ?? `Source ${source.source_id}`,
    };
  }

  private requireSelectedSourceFile(source: UploadedSource): File {
    if (source.file === undefined) {
      throw new Error('Selected source file is unavailable.');
    }

    return source.file;
  }

  private averageScoreLabel(): string {
    const scores = this.recentDailyScores;
    if (scores.length === 0) {
      return '--';
    }

    const total = scores.reduce((sum, score) => sum + score, 0);
    return `${Math.round(total / scores.length)}%`;
  }

  private readRecentDailyScores(): number[] {
    if (typeof localStorage === 'undefined') {
      return [];
    }

    try {
      const raw = localStorage.getItem(RECENT_DAILY_SCORES_STORAGE_KEY);
      const parsed = raw ? (JSON.parse(raw) as unknown) : [];
      if (!Array.isArray(parsed)) {
        return [];
      }

      return parsed.filter(
        (value): value is number => typeof value === 'number' && Number.isFinite(value),
      );
    } catch {
      return [];
    }
  }
}
