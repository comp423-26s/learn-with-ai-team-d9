Authors
Siya Patel: https://github.com/psiya
Sanjana Nukala: https://github.com/nukalasanjana
Sophia Moloo: https://github.com/smoloo1
Medha Nagaluri: https://github.com/medhanagaluri

## Feature Description

The quiz experience feature gives students two ways to generate practice questions. A ‘Daily Challenge’ button generates a topic-based quiz (asynchronously) immediately, without requiring any uploaded sources. Separately, a student can navigate to the ‘Upload Sources’ sidebar, where they can upload one or more PDF source files and generate a personalized quiz based on their uploaded materials. Uploaded sources also persist across sessions, so when a student refreshes or returns to the site later, their previous uploads are still available and can be reused to generate new quizzes without needing to upload the same files again.

## Frontend

On the frontend, the student experience is split into two paths on the same page: a Daily Challenge quiz, and a source-based quiz where students upload one or more PDF sources and then generate a personalized quiz from the context. The UI integrates directly with the backend endpoints through Angular services that wrap the generated API client, so components can call methods to upload PDFs without handling HTTP details. These services also handle checking the status of asynchronous quiz generation jobs. Uploaded sources are reloaded from the backend on refresh, which keeps the dashboard consistent while the service layer handles requests, errors, and keeping the sources and quizzes in sync.

## Backend

On the backend, the Pydantic models in strive.py check and clean incoming API data, and make sure the frontend always receives consistent, well-structured JSON responses. For Sprint 1 (Daily Challenge), QuizCreateRequest validates the inputs needed to start a quiz, limits the mode to “daily” or “module,” and ensures exactly five questions are generated. QuizCreateResponse returns metadata like id, activity_id, student_pid, status, and started_at. When fetching quiz content, QuizQuestionsResponse includes submission metadata and a list of QuizQuestionDTO objects. Each QuizQuestionDTO contains a question_id, the question text, and an ordered list of multiple-choice options as ChoiceDTO, excluding the correct answer so the frontend can safely display the quiz. When a student submits answers, a list of QuizAnswerDTO entries is required, and the graded result is returned in QuizSubmitResponse.
For Sprint 2 (sources/persistence), SourceSummaryResponse defines how saved uploads are returned, allowing the uploads sidebar to persist after refresh. SourceQuizCreateRequest validates the inputs for generating a quiz from an existing stored source, ensuring quizzes can be safely regenerated from saved PDFs.

## Service Layer

The service layer in Strive handles the full workflow (upload → save → extract → generate quiz), while the FastAPI routes stay focused on handling HTTP requests. In Sprint 1, the main quiz routes were added:
POST /…/quizzes starts a new Daily Challenge quiz using StriveService.start_quiz
GET /…/quizzes/{submission_id} retrieves an in-progress quiz with StriveService.get_quiz
POST /…/quizzes/{submission_id}/submit submits answers and returns scoring feedback through StriveService.submit_quiz
In Sprint 2, support for saved sources was added to enable personalized quizzes and persistence:
POST /sources uploads one or more PDFs, saves them as StriveSource records, and generates a quiz using StriveService.generate_quiz_from_pdf
GET /sources returns the signed-in student’s previously uploaded files for UI persistence via StriveService.list_uploaded_sources
POST /sources/{source_id}/quizzes creates a new quiz from an existing saved source without re-uploading, using StriveService.generate_quiz_from_source
Data is stored using the StriveSource database model, which keeps details like filename and content type, and is accessed through striveSourceRepository for creating and listing sources by student. In the core service logic, these methods save the source, extract text from the PDF into JSON, and pass that content to the quiz generator.

### PDF Extractor

The PDF extractor converts a user-uploaded PDF into a normalized JSON that quiz generation can use. It parses the PDF with PyPDF2, normalizes the metadata, extracts text with whitespace normalization, and makes sure there is a maximum cap at 12,000 characters so large documents don’t overflow the prompt storage. The extractor has guardrails to raise errors if the PDF can’t be parsed or if no usable text is found. The upload route restricts uploads to 10MB file size as well.

## Persistence

The persistence in this feature is designed so uploaded sources stay available across page reloads and future sessions for users. When a student uploads one or more PDFs, the backend makes a source record for each file that is associated with the user and stores data like filename and content type. For PDFs, the extracted text is also persisted with the source so quiz generation can reuse the same content without requiring the student to re-upload the document.

## AI Integration

The AI integration for this project is implemented in the quiz question generation and end-of-quiz feedback. For the Daily Challenge, the backend calls the OpenAI API with a reusable prompt that generates a consistent set of 5 questions from the course’s stored topic context. For personalized quizzes, the AI uses a structured JSON created from user uploads (PDF lecture materials) as context to generate source-based questions that match the uploaded content. To keep outputs reliable, the system limits the amount of extracted text and keeps quiz sizing small, while returning results in a way that the frontend can render and grade before requesting LLM-generated feedback

## Deployment

We used the open-source Kubernetes deployment platform OKD to deploy our project.
To deploy this project, we first synchronized our local environment with the upstream repository via a Staging Hotfix to enable role-based testing features. After configuring our Secrets (such as database passwords and OpenAI keys) and manifests within the infra/ directory, we established a secure connection between OpenShift (OKD) and GitHub using an SSH Deploy Key.
With the connection live, we executed a deployment script to trigger a BuildConfig, which containerized the application and manually configured a Secure Route using TLS Edge termination to map the service to a team's public URL. To finalize the staging environment, we toggled the ENVIRONMENT variable to "stage" in both the build and deployment settings and initialized the Postgres database using a reset script.
The entire workflow was then automated by linking an OKD Webhook to our GitHub repository, ensuring that every merge to the main branch triggers an automatic build and redeployment.
In the case that we made new commits and wanted to do a manual rebuild, we were able to go into OKD’s build configs and start a new build and our deployment was accessed through our remote URL.

## Jobs

Strive uses asynchronous jobs to generate quizzes for both daily challenges and PDF/source-based content. Instead of blocking API requests while waiting on OpenAI, quiz creation queues a background job and returns a job ID immediately. The front end then checks the job status until the quiz is ready. Strive is integrated into the core background job system by adding a custom handler and payload. Then, the API routes and response models are updated to support the workflow. The frontend is then updated to check for job completion, and all t
A Strive-specific job payload and handler were added in learnwithai-core, and StriveService was connected to the AsyncJobRepository and JobQueue to manage job execution. Alongside this, the API response models and routes were updated, and the frontend was modified to support polling. OpenAPI-generated artifacts and tests were also updated to reflect the new asynchronous workflow.
