/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { RouterLink, RouterOutlet } from '@angular/router';
import { PageTitleService } from '../../../page-title.service';
import { LayoutNavigationService } from '../../../layout/layout-navigation.service';

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

  protected readonly topLevelStats: StudentTopLevelStat[] = [
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
      value: '87%',
      description: 'Average score across recent daily challenges',
    },
  ];

  constructor() {
    this.layoutNavigation.clearContext();
    this.titleService.setTitle('Student Dashboard');
  }
}
