/*
 * Copyright (c) 2026 Kris Jordan
 * SPDX-License-Identifier: MIT
 */

/** Request body for creating a Strive quiz submission. */
export type QuizCreateRequest = {
  mode: 'daily' | 'module';
  module_name?: string | null;
  topic?: string | null;
  question_count?: number;
};

/** Metadata returned after creating a Strive quiz submission. */
export type QuizCreateResponse = {
  id: number;
  activity_id: number;
  student_pid: number;
  status: string;
  started_at: string;
  question_count: number;
  mode: 'daily' | 'module';
  module_name?: string | null;
  topic?: string | null;
};

/** A single answer choice for an MCQ. */
export type ChoiceDTO = {
  id: number;
  text: string;
};

/** A single quiz question. */
export type QuizQuestionDTO = {
  question_id: number;
  text: string;
  choices: ChoiceDTO[];
};

/** Response model for fetching quiz questions. */
export type QuizQuestionsResponse = {
  id: number;
  activity_id: number;
  student_pid: number;
  status: string;
  mode: 'daily' | 'module';
  module_name?: string | null;
  topic?: string | null;
  questions: QuizQuestionDTO[];
};

/** A single submitted answer. */
export type QuizAnswerDTO = {
  question_id: number;
  selected_choice_id: number;
};

/** Request body for submitting quiz answers. */
export type QuizSubmitRequest = {
  answers: QuizAnswerDTO[];
};

/** Per-question feedback after grading. */
export type QuizFeedbackDTO = {
  question_id: number;
  correct: boolean;
  correct_choice_id?: number | null;
  explanation?: string | null;
};

/** Response model after quiz submission is graded. */
export type QuizSubmitResponse = {
  id: number;
  score: number;
  correct_count: number;
  total_count: number;
  feedback: QuizFeedbackDTO[];
  finished_at: string;
};
