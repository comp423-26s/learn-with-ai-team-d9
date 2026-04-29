/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { StriveQuizService } from './strive-quiz.service';
import { QuizQuestionsResponse } from './strive-quiz.models';

describe('StriveQuizService', () => {
  let service: StriveQuizService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(StriveQuizService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('should start a quiz', async () => {
    const promise = service.startQuiz(7, {
      mode: 'daily',
      question_count: 5,
    });

    const request = httpTesting.expectOne('/api/activities/7/quizzes');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      mode: 'daily',
      question_count: 5,
    });

    request.flush({
      id: 101,
      activity_id: 7,
      student_pid: 730611076,
      status: 'in_progress',
      started_at: '2026-04-20T12:00:00Z',
      question_count: 5,
      mode: 'daily',
      module_name: null,
      topic: 'Python Basics',
    });

    await expect(promise).resolves.toMatchObject({ id: 101, activity_id: 7 });
  });

  it('should get quiz questions', async () => {
    const promise = service.getQuiz(101);

    const request = httpTesting.expectOne('/api/quizzes/101');
    expect(request.request.method).toBe('GET');

    request.flush({
      id: 101,
      activity_id: 7,
      student_pid: 730611076,
      status: 'in_progress',
      mode: 'daily',
      module_name: null,
      topic: 'Python Basics',
      questions: [],
    });

    await expect(promise).resolves.toMatchObject({ id: 101, questions: [] });
  });

  it('should submit quiz answers', async () => {
    const promise = service.submitQuiz(101, {
      answers: [{ question_id: 1, selected_choice_id: 2 }],
    });

    const request = httpTesting.expectOne('/api/quizzes/101/submit');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      answers: [{ question_id: 1, selected_choice_id: 2 }],
    });

    request.flush({
      id: 101,
      score: 100,
      correct_count: 1,
      total_count: 1,
      feedback: [
        {
          question_id: 1,
          correct: true,
          correct_choice_id: 2,
          explanation: 'Correct.',
        },
      ],
      finished_at: '2026-04-20T12:30:00Z',
    });

    await expect(promise).resolves.toMatchObject({ id: 101, score: 100 });
  });

  it('should upload a PDF and request source-based quiz generation', async () => {
    const file = new File(['pdf'], 'source.pdf', { type: 'application/pdf' });
    const promise = service.uploadPdfAndGenerateQuiz(7, file, 5);

    const request = httpTesting.expectOne('/api/activities/7/quizzes/upload-pdf');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toBeInstanceOf(FormData);

    const formData = request.request.body as FormData;
    expect(formData.get('question_count')).toBe('5');
    const uploadedFile = formData.get('file');
    expect(uploadedFile).toBeInstanceOf(File);
    expect((uploadedFile as File).name).toBe('source.pdf');

    request.flush({
      id: 202,
      activity_id: 7,
      student_pid: 730611076,
      status: 'in_progress',
      mode: 'daily',
      module_name: null,
      topic: 'Source Topic',
      questions: [],
    });

    await expect(promise).resolves.toMatchObject({ id: 202, mode: 'daily' });
  });

  it('should list persisted sources', async () => {
    const promise = service.listSources();

    const request = httpTesting.expectOne('/api/sources');
    expect(request.request.method).toBe('GET');

    request.flush([
      {
        source_id: 31,
        activity_id: 7,
        filename: 'saved-notes.pdf',
        content_type: 'application/pdf',
        created_at: '2026-04-20T12:00:00Z',
      },
    ]);

    await expect(promise).resolves.toEqual([
      {
        source_id: 31,
        activity_id: 7,
        filename: 'saved-notes.pdf',
        content_type: 'application/pdf',
        created_at: '2026-04-20T12:00:00Z',
      },
    ]);
  });

  it('should create a quiz from a persisted source', async () => {
    const promise = service.createSourceQuiz(31, 5);

    const request = httpTesting.expectOne('/api/sources/31/quizzes');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ question_count: 5 });

    request.flush({
      id: 303,
      activity_id: 7,
      student_pid: 730611076,
      status: 'in_progress',
      started_at: '2026-04-20T12:00:00Z',
      question_count: 5,
      mode: 'daily',
      module_name: null,
      topic: 'Saved Source',
      questions: [],
    });

    await expect(promise).resolves.toMatchObject({ id: 303, activity_id: 7 });
  });

  it('should consume and clear the pending source quiz', () => {
    const pendingQuiz: QuizQuestionsResponse = {
      id: 303,
      activity_id: 7,
      student_pid: 730611076,
      status: 'in_progress',
      mode: 'daily',
      module_name: null,
      topic: 'Pending Source Quiz',
      questions: [],
    };

    service.setPendingSourceQuiz(pendingQuiz);

    expect(service.consumePendingSourceQuiz()).toEqual(pendingQuiz);
    expect(service.consumePendingSourceQuiz()).toBeNull();
  });
});
