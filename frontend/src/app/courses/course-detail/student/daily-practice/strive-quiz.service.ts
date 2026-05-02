/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import {
  QuizCreateRequest,
  QuizGenerationJobResponse,
  QuizQuestionsResponse,
  QuizSubmitRequest,
  QuizSubmitResponse,
} from './strive-quiz.models';

export type SourceSummary = {
  source_id: number;
  activity_id: number;
  filename: string | null;
  content_type: string;
  created_at: string;
};

/** Wraps Strive quiz route calls used by the student daily challenge UI. */
@Injectable({ providedIn: 'root' })
export class StriveQuizService {
  private readonly http = inject(HttpClient);
  private pendingSourceQuiz: QuizQuestionsResponse | null = null;

  /** Starts a new quiz submission for the given activity. */
  startQuiz(activityId: number, body: QuizCreateRequest): Promise<QuizGenerationJobResponse> {
    return firstValueFrom(
      this.http.post<QuizGenerationJobResponse>(`/api/activities/${activityId}/quizzes`, body),
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

  /** Uploads a PDF source and generates questions grounded in that source. */
  uploadPdfAndGenerateQuiz(
    activityId: number,
    file: File,
    questionCount: number,
  ): Promise<QuizGenerationJobResponse> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    formData.append('question_count', String(questionCount));

    return firstValueFrom(
      this.http.post<QuizGenerationJobResponse>(
        `/api/activities/${activityId}/quizzes/upload-pdf`,
        formData,
      ),
    );
  }

  /** Loads persisted source files for the current student. */
  listSources(): Promise<SourceSummary[]> {
    return firstValueFrom(this.http.get<SourceSummary[]>(`/api/sources`));
  }

  /** Generates a quiz from a previously saved source. */
  createSourceQuiz(sourceId: number, questionCount: number): Promise<QuizGenerationJobResponse> {
    return firstValueFrom(
      this.http.post<QuizGenerationJobResponse>(`/api/sources/${sourceId}/quizzes`, {
        question_count: questionCount,
      }),
    );
  }

  /** Waits for a queued quiz-generation job and returns the generated quiz. */
  async waitForGeneratedQuiz(jobId: number): Promise<QuizQuestionsResponse> {
    const maxAttempts = 90;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      try {
        return await this.getQuiz(jobId);
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
    }

    throw new Error('Timed out waiting for generated quiz.');
  }

  /** Stores a generated source-based quiz so the quiz page can consume it. */
  setPendingSourceQuiz(quiz: QuizQuestionsResponse): void {
    this.pendingSourceQuiz = quiz;
  }

  /** Returns and clears the most recently generated source-based quiz. */
  consumePendingSourceQuiz(): QuizQuestionsResponse | null {
    const pending = this.pendingSourceQuiz;
    this.pendingSourceQuiz = null;
    return pending;
  }
}
