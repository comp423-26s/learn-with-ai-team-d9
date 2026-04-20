/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import {
  QuizCreateRequest,
  QuizCreateResponse,
  QuizQuestionsResponse,
  QuizSubmitRequest,
  QuizSubmitResponse,
} from './strive-quiz.models';

/** Wraps Strive quiz route calls used by the student daily challenge UI. */
@Injectable({ providedIn: 'root' })
export class StriveQuizService {
  private readonly http = inject(HttpClient);

  /** Starts a new quiz submission for the given activity. */
  startQuiz(activityId: number, body: QuizCreateRequest): Promise<QuizCreateResponse> {
    return firstValueFrom(
      this.http.post<QuizCreateResponse>(`/api/activities/${activityId}/quizzes`, body),
    );
  }

  /** Retrieves quiz questions for an existing quiz submission. */
  getQuiz(quizSubmissionId: number): Promise<QuizQuestionsResponse> {
    return firstValueFrom(this.http.get<QuizQuestionsResponse>(`/api/quizzes/${quizSubmissionId}`));
  }

  /** Submits answers for grading. */
  submitQuiz(quizSubmissionId: number, body: QuizSubmitRequest): Promise<QuizSubmitResponse> {
    return firstValueFrom(
      this.http.post<QuizSubmitResponse>(`/api/quizzes/${quizSubmissionId}/submit`, body),
    );
  }
}
