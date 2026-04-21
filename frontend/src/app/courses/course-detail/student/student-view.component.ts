/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { Component, ChangeDetectionStrategy, computed, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { RouterLink, RouterOutlet } from '@angular/router';
import { PageTitleService } from '../../../page-title.service';
import { LayoutNavigationService } from '../../../layout/layout-navigation.service';
import { RECENT_DAILY_SCORES_STORAGE_KEY } from './daily-practice/daily-practice.component';

type StudentTopLevelStat = {
  label: string;
  value: string;
  description: string;
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
  private readonly recentDailyScores = this.readRecentDailyScores();

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
