/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { ActivatedRoute, RouterLink } from '@angular/router';

/** Button that returns a student from a quiz flow back to the student dashboard. */
@Component({
  selector: 'app-back-to-student-dashboard-button',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, RouterLink],
  template: `
    <a mat-flat-button color="primary" [routerLink]="studentDashboardLink()">
      Back to Student Dashboard
    </a>
  `,
})
export class BackToStudentDashboardButton {
  private readonly route = inject(ActivatedRoute);

  protected readonly studentDashboardLink = computed(() => {
    const courseId = Number(this.route.parent?.parent?.snapshot.paramMap.get('id'));
    return Number.isNaN(courseId) ? ['/courses'] : ['/courses', courseId, 'student'];
  });
}
