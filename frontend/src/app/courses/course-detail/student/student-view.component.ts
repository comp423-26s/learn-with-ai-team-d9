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
import {
  RECENT_DAILY_SCORES_STORAGE_KEY,
  STREAK_DATES_STORAGE_KEY,
} from './daily-practice/daily-practice.component';

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
  private readonly streakDates = this.readStreakDates();

  protected readonly topLevelStats = computed<StudentTopLevelStat[]>(() => [
    {
      label: 'Streak',
      value: this.streakLabel(),
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

  private streakLabel(): string {
    const streak = this.calculateStreak(this.streakDates);
    if (streak === 0) return '--';
    return `${streak} day${streak === 1 ? '' : 's'}`;
  }

  private calculateStreak(dates: string[]): number {
    const uniqueDates = [...new Set(dates)].sort();
    if (uniqueDates.length === 0) return 0;

    let streak = 1;
    for (let i = uniqueDates.length - 1; i > 0; i--) {
      const curr = new Date(uniqueDates[i] + 'T00:00:00Z');
      const prev = new Date(uniqueDates[i - 1] + 'T00:00:00Z');
      const diffDays = (curr.getTime() - prev.getTime()) / (1000 * 60 * 60 * 24);
      if (Math.round(diffDays) === 1) {
        streak++;
      } else {
        break;
      }
    }
    return streak;
  }

  private readStreakDates(): string[] {
    if (typeof localStorage === 'undefined') return [];

    try {
      const raw = localStorage.getItem(STREAK_DATES_STORAGE_KEY);
      const parsed = raw ? (JSON.parse(raw) as unknown) : [];
      if (!Array.isArray(parsed)) return [];
      return parsed.filter((v): v is string => typeof v === 'string');
    } catch {
      return [];
    }
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
    if (typeof localStorage === 'undefined') return [];

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
