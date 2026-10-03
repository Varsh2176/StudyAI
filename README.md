# StudyAI: AI-Integrated Web Tool for Personalized Study Planning

A web platform that helps students plan their study time using **machine learning** (performance prediction, risk classification, priority scoring) and an **AI/LLM tutor with RAG** (explanations, study plans, and answers grounded in the student's own PDF notes).


---

## Table of Contents

- [Problem Definition](#problem-definition)
- [Objectives](#objectives)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Folder Structure](#folder-structure)
- [Installation and Setup](#installation-and-setup)
- [Usage](#usage)
- [Testing](#testing)
- [Documentation](#documentation)
- [Limitations](#limitations)
- [Contributing](#contributing)

---

## Problem Definition

Students often split study time evenly or by habit, without a data-driven view of which subjects are at risk, how much effort each needs, or how close the exams are. Generic study planners ignore a student's marks, attendance, quiz results, and available time, and generic chatbots do not use the student's own study material.

## Objectives

1. Collect academic and study-habit data (marks, attendance, assignments, quizzes, study hours, difficulty, exam dates, preferences).
2. Use ML to predict expected performance, classify subject risk (Low / Medium / High), and rank subject priority.
3. Generate a personalized daily/weekly timetable and revision schedule that respects the student's availability and exam dates.
4. Provide an AI tutor and a RAG-based Q&A feature over uploaded PDF notes, with citations.
5. Track sessions, quizzes, and progress, and adapt the plan when new data arrives.

## Key Features

| Area | Description |
|---|---|
| **ML module** | Score prediction, risk classification, priority score, recommended study hours. The final algorithm is chosen only after comparing candidates against baselines on validation data. |
| **Planner** | A rule-based scheduler enforces constraints (availability, exam dates, no overlaps). The LLM adds topic-wise tasks and explanations; invalid LLM output falls back to the rule-based plan. |
| **AI tutor** | Explanations and study suggestions using the student's ML results as context. |
| **RAG over notes** | PDF upload, chunking, embeddings, retrieval, and answers with page citations; replies "not found" when the notes do not cover the question. |
| **Tracking** | Study sessions, topics completed, quiz scores, streaks, and a progress dashboard. |
| **Adaptive plan** | Re-evaluates predictions and proposes a revised plan after new quizzes, marks, or missed sessions; the student approves changes. |
| **Admin** | User management, ML model version management, configuration, and audit log. |

**ML vs. AI/LLM:** ML produces the numbers (predictions, risk, priority, hours). The LLM produces language (explanations, tutoring, Q&A) and never overrides ML outputs.

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React.js, JavaScript, Tailwind CSS, Recharts / Chart.js |
| Backend | Python, FastAPI |
| ML | Pandas, NumPy, scikit-learn, XGBoost (only if justified), Matplotlib / Seaborn |
| AI | LLM API, prompt engineering, embeddings, RAG, vector database |
| Database | MongoDB / MongoDB Atlas |
| Deployment | Vercel (frontend), Render / Railway (backend), MongoDB Atlas |
| Tooling | Git, GitHub |

