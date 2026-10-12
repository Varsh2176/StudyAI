from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal


class StudentProfile(BaseModel):
    email: str
    age: int
    course: str
    year: int
    branch: str
    study_hours: float
    attendance: float
    previous_cgpa: float
    subjects: List[str]


class ExamScorePredictionRequest(BaseModel):
    # Exactly the 6 numeric features required by the trained model pipeline
    Hours_Studied: float = Field(..., ge=0, le=50, description="Hours studied per week (0-50)")
    Attendance: float = Field(..., ge=0, le=100, description="Attendance percentage (0-100)")
    Sleep_Hours: float = Field(..., ge=0, le=24, description="Average sleep hours per night (0-24)")
    Previous_Scores: float = Field(..., ge=0, le=100, description="Previous exam or test score percentage (0-100)")
    Tutoring_Sessions: int = Field(..., ge=0, le=20, description="Number of tutoring sessions per month (0-20)")
    Physical_Activity: float = Field(..., ge=0, le=20, description="Hours of physical activity per week (0-20)")

    # Exactly the 13 categorical features required by the trained model pipeline
    Parental_Involvement: Literal["Low", "Medium", "High"] = Field(..., description="Low, Medium, or High")
    Access_to_Resources: Literal["Low", "Medium", "High"] = Field(..., description="Low, Medium, or High")
    Extracurricular_Activities: Literal["Yes", "No"] = Field(..., description="Yes or No")
    Motivation_Level: Literal["Low", "Medium", "High"] = Field(..., description="Low, Medium, or High")
    Internet_Access: Literal["Yes", "No"] = Field(..., description="Yes or No")
    Family_Income: Literal["Low", "Medium", "High"] = Field(..., description="Low, Medium, or High")
    Teacher_Quality: Literal["Low", "Medium", "High"] = Field(..., description="Low, Medium, or High")
    School_Type: Literal["Public", "Private"] = Field(..., description="Public or Private")
    Peer_Influence: Literal["Positive", "Neutral", "Negative"] = Field(..., description="Positive, Neutral, or Negative")
    Learning_Disabilities: Literal["Yes", "No"] = Field(..., description="Yes or No")
    Parental_Education_Level: Literal["High School", "College", "Postgraduate"] = Field(..., description="High School, College, or Postgraduate")
    Distance_from_Home: Literal["Near", "Moderate", "Far"] = Field(..., description="Near, Moderate, or Far")
    Gender: Literal["Male", "Female"] = Field(..., description="Male or Female")

    # Optional student identification to link with database profile
    email: Optional[str] = None


class ExamScorePredictionResponse(BaseModel):
    predicted_exam_score: float
    model_used: str
    metrics: Dict[str, float]
    risk_assessment: Dict[str, Any]


# Study Planner Schemas (Milestone 11 / Phase D)
class PlanSubject(BaseModel):
    name: str = Field(..., min_length=1, description="Subject name")
    difficulty: Literal["Low", "Medium", "High", "low", "medium", "high"] = Field(
        default="Medium", description="Subject difficulty level"
    )
    exam_date: Optional[str] = Field(default=None, description="Upcoming exam date (YYYY-MM-DD)")
    current_score: Optional[float] = Field(default=60.0, ge=0.0, le=100.0, description="Current score (0-100)")
    target_score: Optional[float] = Field(default=85.0, ge=0.0, le=100.0, description="Target score (0-100)")


class StudyPlanGenerateRequest(BaseModel):
    email: Optional[str] = None
    daily_study_hours: Optional[float] = Field(default=4.0, ge=0.5, le=16.0, description="Requested daily study hours")
    daily_available_hours: Optional[float] = Field(default=None, ge=0.5, le=16.0, description="Available daily hours")
    preferred_start_time: str = Field(default="09:00", description="HH:MM format")
    subjects: List[PlanSubject] = Field(..., min_length=1, description="Subjects to schedule")
    days_to_plan: int = Field(default=7, ge=1, le=30, description="Days to plan ahead (1-30)")
    risk_category: Optional[Literal["Low Risk", "Moderate Risk", "High Risk", "Medium Risk"]] = Field(
        default=None, description="Optional academic risk category"
    )
    max_daily_limit: Optional[float] = Field(
        default=8.0, ge=2.0, le=12.0, description="Maximum daily study limit to prevent burnout"
    )
    plan_date: Optional[str] = Field(default=None, description="Anchor date for plan generation (YYYY-MM-DD)")
    attendance: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Student attendance percentage for dynamic risk assessment"
    )
    previous_scores: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Student previous score percentage for dynamic risk assessment"
    )
    predicted_exam_score: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="ML predicted exam score for dynamic risk assessment"
    )


class TimetableSlot(BaseModel):
    slot_order: int
    slot_id: str
    subject: str
    difficulty: str
    priority_level: str
    duration_minutes: int
    start_time: str
    end_time: str
    break_duration_minutes: int
    break_time: str
    recommended_focus: str
    completed: bool = False


class SubjectAllocationSummary(BaseModel):
    subject: str
    difficulty: str
    priority_score: float
    allocated_ratio: float
    allocated_study_minutes: int
    allocated_study_hours: float
    slots_count: int


class StudyPlanResponse(BaseModel):
    plan_date: str
    daily_study_hours: float
    daily_available_hours: float
    m10_recommended_daily_hours: float
    m10_recommended_weekly_hours: Optional[float] = None
    total_scheduled_study_minutes: int
    total_scheduled_study_hours: float
    total_break_minutes: int
    risk_category_applied: Optional[str] = "Low Risk"
    risk_assessment_details: Optional[Dict[str, Any]] = None
    m10_recommendation: Optional[Dict[str, Any]] = None
    burnout_guardrail_applied: bool
    days_planned: int
    subjects_weighted: List[Dict[str, Any]]
    daily_schedule: List[Dict[str, Any]]
    weekly_schedule: Dict[str, List[Dict[str, Any]]]
    timetable: List[TimetableSlot]
    subject_allocations: List[SubjectAllocationSummary]
    summary: str
    notes: str
    disclaimer: Optional[str] = None


# Progress & Quiz Schemas (M17)
class StudySessionLog(BaseModel):
    """
    Log a study session outcome for progress tracking.
    status: completed | partial | missed
    planned_minutes vs actual_minutes supports planned-versus-actual reporting.
    duration_minutes / completed remain accepted for backward compatibility.
    """
    email: str = Field(..., min_length=3, max_length=254)
    subject: str = Field(..., min_length=1, max_length=120)
    topic: str = Field(default="", max_length=200)
    status: Literal["completed", "partial", "missed"] = "completed"
    planned_minutes: int = Field(default=50, ge=1, le=600)
    actual_minutes: Optional[int] = Field(default=None, ge=0, le=600)
    duration_minutes: Optional[int] = Field(
        default=None,
        ge=0,
        le=600,
        description="Legacy alias for actual_minutes when status is completed/partial",
    )
    completed: Optional[bool] = Field(
        default=None,
        description="Legacy flag; mapped to status when status is omitted by older clients",
    )
    date: Optional[str] = Field(default=None, description="Session date YYYY-MM-DD")
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = (value or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("A valid student email is required.")
        return email

    @field_validator("subject", "topic")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()


class QuizScoreLog(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    subject: str = Field(..., min_length=1, max_length=120)
    quiz_title: str = Field(..., min_length=1, max_length=200)
    score: float = Field(..., ge=0)
    total_marks: float = Field(default=100.0, gt=0)
    date: Optional[str] = Field(default=None, description="Quiz date YYYY-MM-DD")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = (value or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("A valid student email is required.")
        return email


class AdaptPlanRequest(BaseModel):
    """M18 — Adapt the stored study plan from logged progress (email-scoped)."""
    email: str = Field(..., min_length=3, max_length=254)
    daily_available_hours: Optional[float] = Field(
        default=None,
        ge=0.5,
        le=16.0,
        description="Optional override for available daily study hours (never raises above original plan daily hours)",
    )
    days_to_plan: Optional[int] = Field(default=None, ge=1, le=30)
    plan_date: Optional[str] = Field(
        default=None,
        description="Optional YYYY-MM-DD start for the adapted horizon (default: tomorrow)",
    )
    max_daily_limit: Optional[float] = Field(default=None, ge=2.0, le=12.0)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = (value or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("A valid student email is required.")
        return email


# AI Notes & Q&A Schemas (Phase F / M15–M16 RAG path)
class AskTutorRequest(BaseModel):
    email: Optional[str] = None
    question: str
    subject: Optional[str] = None
    note_id: Optional[str] = None


# M14 — General AI Tutor (non-RAG conversational assistant)
class TutorChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class TutorChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Academic question for the tutor")
    email: Optional[str] = Field(default=None, description="Optional student email for profile context")
    subject: Optional[str] = Field(default=None, max_length=120, description="Optional subject/topic focus")
    conversation_history: List[TutorChatMessage] = Field(
        default_factory=list,
        max_length=20,
        description="Prior turns in the active UI session (not server-persisted)",
    )
    include_profile_context: bool = Field(
        default=True,
        description="When email is provided, optionally include basic academic profile fields",
    )

    @field_validator("question")
    @classmethod
    def validate_question_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty.")
        return cleaned

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class TutorChatResponse(BaseModel):
    answer: str
    provider: str
    model_used: str
    configured: bool = True
    profile_context_used: bool = False
    disclaimer: str


# M16 — RAG over uploaded study documents
class RagAskRequest(BaseModel):
    email: str = Field(..., min_length=3, description="Student email that owns the documents")
    question: str = Field(..., min_length=1, max_length=2000)
    document_id: Optional[str] = Field(
        default=None,
        description="Optional specific document ID; omit to search all indexed owned documents",
    )
    top_k: int = Field(default=4, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def validate_rag_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty.")
        return cleaned


class RagSourceCitation(BaseModel):
    document_id: str
    filename: str
    page: int
    chunk_id: str
    snippet: str
    similarity_score: float


class RagAskResponse(BaseModel):
    answer: str
    grounded: bool
    mode: Literal["llm", "retrieval_only", "no_results"]
    sources: List[RagSourceCitation]
    provider: Optional[str] = None
    model_used: Optional[str] = None
    retrieved_count: int = 0
    document_scope: str


# Study-Hour Recommendation Schemas (Milestone 10)
class StudyHourSubjectInput(BaseModel):
    name: str = Field(..., min_length=1, description="Subject name")
    difficulty: Literal["Low", "Medium", "High"] = Field(default="Medium", description="Subject difficulty")
    current_score: float = Field(default=60.0, ge=0.0, le=100.0, description="Current score or prior marks (0-100)")
    target_score: float = Field(default=85.0, ge=0.0, le=100.0, description="Goal score (0-100)")
    exam_date: Optional[str] = Field(default=None, description="Upcoming exam date (YYYY-MM-DD)")


class StudyHourRecommendationRequest(BaseModel):
    daily_available_hours: float = Field(..., ge=0.5, le=16.0, description="Declared available study hours per day (0.5 - 16)")
    subjects: List[StudyHourSubjectInput] = Field(..., min_length=1, description="Subjects to allocate study time across")
    risk_category: Optional[Literal["Low Risk", "Moderate Risk", "High Risk", "Medium Risk"]] = Field(
        default=None, description="Optional academic risk category from risk assessment"
    )
    max_daily_limit: Optional[float] = Field(
        default=8.0, ge=2.0, le=12.0, description="Maximum daily study limit to prevent burnout"
    )
    email: Optional[str] = None
    attendance: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Student attendance percentage for dynamic risk assessment"
    )
    previous_scores: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Student previous score percentage for dynamic risk assessment"
    )
    predicted_exam_score: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="ML predicted exam score for dynamic risk assessment"
    )


class SubjectHourBreakdown(BaseModel):
    subject: str
    difficulty: str
    score_gap: float
    weekly_hours: float
    daily_hours: float
    percentage_share: float
    focus_priority: str


class StudyHourRecommendationResponse(BaseModel):
    recommended_weekly_hours: float
    recommended_daily_hours: float
    available_daily_hours: float
    max_daily_limit: float
    risk_category_applied: str
    burnout_guardrail_applied: bool
    subject_breakdown: List[SubjectHourBreakdown]
    concise_explanation: str
    methodology_notes: str
    disclaimer: str
    risk_assessment_details: Optional[Dict[str, Any]] = None