from pydantic import BaseModel, Field
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


# Study Planner Schemas (Phase D)
class PlanSubject(BaseModel):
    name: str
    difficulty: str = Field(default="Medium", description="Low, Medium, or High")
    exam_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    current_score: Optional[float] = Field(default=60.0, ge=0, le=100)
    target_score: Optional[float] = Field(default=85.0, ge=0, le=100)


class StudyPlanGenerateRequest(BaseModel):
    email: Optional[str] = None
    daily_study_hours: float = Field(default=4.0, ge=1.0, le=12.0)
    preferred_start_time: str = Field(default="09:00", description="HH:MM format")
    subjects: List[PlanSubject]
    days_to_plan: int = Field(default=7, ge=1, le=30)


# Progress & Quiz Schemas (Phase G)
class StudySessionLog(BaseModel):
    email: str
    subject: str
    topic: str
    duration_minutes: int = Field(..., ge=1, le=600)
    completed: bool = True
    date: Optional[str] = None


class QuizScoreLog(BaseModel):
    email: str
    subject: str
    quiz_title: str
    score: float = Field(..., ge=0)
    total_marks: float = Field(default=100.0, gt=0)
    date: Optional[str] = None


# AI Notes & Q&A Schemas (Phase F)
class AskTutorRequest(BaseModel):
    email: Optional[str] = None
    question: str
    subject: Optional[str] = None
    note_id: Optional[str] = None


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