/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { BackToStudentDashboardButton } from './back-to-student-dashboard-button.component';

describe('BackToStudentDashboardButton', () => {
  function render(routeCourseId: string | null = '1') {
    TestBed.configureTestingModule({
      imports: [BackToStudentDashboardButton],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            parent: {
              parent: {
                snapshot: {
                  paramMap: {
                    get: (key: string) => (key === 'id' ? routeCourseId : null),
                  },
                },
              },
            },
          },
        },
      ],
    });

    const fixture = TestBed.createComponent(BackToStudentDashboardButton);
    fixture.detectChanges();
    return fixture;
  }

  it('should link back to the student dashboard for the current course', () => {
    const fixture = render();

    const anchor = fixture.nativeElement.querySelector('a') as HTMLAnchorElement;
    expect(anchor.getAttribute('href')).toContain('/courses/1/student');
    expect(fixture.nativeElement.textContent).toContain('Back to Student Dashboard');
  });

  it('should fall back to the courses list when course context is missing', () => {
    const fixture = render(null);

    const anchor = fixture.nativeElement.querySelector('a') as HTMLAnchorElement;
    expect(anchor.getAttribute('href')).toContain('/courses');
  });
});
