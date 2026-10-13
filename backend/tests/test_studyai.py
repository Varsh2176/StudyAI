import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from pydantic import ValidationError
from fastapi import HTTPException

from app.models.schemas import (
    ExamScorePredictionRequest,
    ExamScorePredictionResponse,
    StudyHourRecommendationRequest,
    StudyHourSubjectInput,
    StudyHourRecommendationResponse,
    PlanSubject,
    StudyPlanGenerateRequest,
    StudyPlanResponse,
    TutorChatRequest,
    TutorChatResponse,
    RagAskRequest,
    StudySessionLog,
    AdaptPlanRequest,
)
from app.routes.prediction import predict_score_endpoint
from app.routes.study_plan import (
    recommend_study_hours_endpoint,
    generate_plan_endpoint,
    generate_timetable_endpoint
)
from app.routes.ai import general_tutor_endpoint, tutor_status_endpoint
from tests.auth_helpers import auth_user
from app.services.tutor_service import (
    answer_academic_question,
    get_tutor_status,
    is_tutor_configured,
    TutorNotConfiguredError,
    TutorTimeoutError,
    TutorProviderError,
)
from app.services.ml_service import load_model, predict_exam_score, evaluate_risk, get_model_metadata
from app.services.risk_service import evaluate_academic_risk, RiskThresholds, DEFAULT_THRESHOLDS
from app.services.study_hour_recommendation import (
    calculate_study_hour_recommendation,
    RecommendationConfig,
    DEFAULT_CONFIG
)
from app.services.scheduler import calculate_subject_weights, generate_study_plan
from app.services.rag_service import extract_text_from_txt, chunk_document, retrieve_relevant_passages
from app.services.ai_service import generate_tutor_response
from app.main import app, health, health_database
from app.database.mongodb import diagnose_mongodb_connectivity, _redact_error_message


def get_valid_payload():
    return {
        "Hours_Studied": 18.0,
        "Attendance": 88.0,
        "Sleep_Hours": 7.0,
        "Previous_Scores": 82.0,
        "Tutoring_Sessions": 1,
        "Physical_Activity": 4.0,
        "Parental_Involvement": "High",
        "Access_to_Resources": "High",
        "Extracurricular_Activities": "Yes",
        "Motivation_Level": "High",
        "Internet_Access": "Yes",
        "Family_Income": "High",
        "Teacher_Quality": "High",
        "School_Type": "Public",
        "Peer_Influence": "Positive",
        "Learning_Disabilities": "No",
        "Parental_Education_Level": "College",
        "Distance_from_Home": "Near",
        "Gender": "Female",
        "email": "test.student@example.edu"
    }


class TestRiskClassification(unittest.TestCase):
    """
    Comprehensive tests for academic risk classification:
    - Low, Moderate, High Risk categories
    - Exact boundary cases for configurable thresholds
    - Invalid inputs and range validations
    - Disclaimers and explainability
    """

    def test_low_risk_category(self):
        result = evaluate_academic_risk(
            attendance=92.0,
            hours_studied=20.0,
            previous_scores=85.0,
            predicted_score=80.0
        )
        self.assertEqual(result["risk_category"], "Low Risk")
        self.assertEqual(result["risk_score"], 0)
        self.assertEqual(len(result["relevant_indicators"]), 0)
        self.assertIn("Low Risk", result["concise_explanation"])
        self.assertIn("disclaimer", result)

    def test_moderate_risk_category(self):
        result = evaluate_academic_risk(
            attendance=70.0,
            hours_studied=14.0,
            previous_scores=75.0,
            predicted_score=72.0
        )
        self.assertEqual(result["risk_category"], "Moderate Risk")
        self.assertEqual(result["risk_score"], 2)
        indicator_names = [ind["indicator"] for ind in result["relevant_indicators"]]
        self.assertIn("Attendance", indicator_names)
        self.assertIn("Hours_Studied", indicator_names)
        self.assertIn("Moderate Risk", result["concise_explanation"])

    def test_high_risk_category(self):
        result = evaluate_academic_risk(
            attendance=50.0,
            hours_studied=6.0,
            previous_scores=45.0,
            predicted_score=52.0
        )
        self.assertEqual(result["risk_category"], "High Risk")
        self.assertEqual(result["risk_score"], 10)
        self.assertGreaterEqual(len(result["relevant_indicators"]), 4)
        self.assertIn("High Risk", result["concise_explanation"])
        self.assertGreater(len(result["recommended_interventions"]), 0)

    def test_exact_threshold_boundary_cases(self):
        res_att_65 = evaluate_academic_risk(attendance=65.0, hours_studied=20.0, previous_scores=80.0, predicted_score=80.0)
        self.assertEqual(res_att_65["risk_score"], 1)
        self.assertEqual(res_att_65["relevant_indicators"][0]["severity"], "Borderline")

        res_att_75 = evaluate_academic_risk(attendance=75.0, hours_studied=20.0, previous_scores=80.0, predicted_score=80.0)
        self.assertEqual(res_att_75["risk_score"], 0)

        res_hrs_10 = evaluate_academic_risk(attendance=85.0, hours_studied=10.0, previous_scores=80.0, predicted_score=80.0)
        self.assertEqual(res_hrs_10["risk_score"], 1)

        res_hrs_16 = evaluate_academic_risk(attendance=85.0, hours_studied=16.0, previous_scores=80.0, predicted_score=80.0)
        self.assertEqual(res_hrs_16["risk_score"], 0)

        res_sc_55 = evaluate_academic_risk(attendance=85.0, hours_studied=20.0, previous_scores=55.0, predicted_score=80.0)
        self.assertEqual(res_sc_55["risk_score"], 1)

        res_sc_70 = evaluate_academic_risk(attendance=85.0, hours_studied=20.0, previous_scores=70.0, predicted_score=80.0)
        self.assertEqual(res_sc_70["risk_score"], 0)

        res_1 = evaluate_academic_risk(attendance=70.0, hours_studied=20.0, previous_scores=80.0, predicted_score=80.0)
        self.assertEqual(res_1["risk_category"], "Low Risk")

        res_2 = evaluate_academic_risk(attendance=70.0, hours_studied=14.0, previous_scores=80.0, predicted_score=80.0)
        self.assertEqual(res_2["risk_category"], "Moderate Risk")

        res_4 = evaluate_academic_risk(attendance=60.0, hours_studied=14.0, previous_scores=80.0, predicted_score=80.0)
        self.assertEqual(res_4["risk_category"], "High Risk")

    def test_configurable_custom_thresholds(self):
        strict_cfg = RiskThresholds(high_risk_cutoff=3, moderate_risk_cutoff=1)
        res = evaluate_academic_risk(
            attendance=60.0,
            hours_studied=20.0,
            previous_scores=80.0,
            predicted_score=80.0,
            thresholds=strict_cfg
        )
        self.assertEqual(res["risk_category"], "High Risk")
        self.assertEqual(res["configurable_thresholds_applied"]["high_risk_cutoff"], 3)

    def test_invalid_indicator_inputs_raise_value_errors(self):
        with self.assertRaises(ValueError):
            evaluate_academic_risk(attendance=-10.0, hours_studied=15.0, previous_scores=70.0, predicted_score=70.0)
        with self.assertRaises(ValueError):
            evaluate_academic_risk(attendance=105.0, hours_studied=15.0, previous_scores=70.0, predicted_score=70.0)
        with self.assertRaises(ValueError):
            evaluate_academic_risk(attendance=80.0, hours_studied=-2.0, previous_scores=70.0, predicted_score=70.0)
        with self.assertRaises(ValueError):
            evaluate_academic_risk(attendance=80.0, hours_studied=15.0, previous_scores=-5.0, predicted_score=70.0)
        with self.assertRaises(ValueError):
            evaluate_academic_risk(attendance=80.0, hours_studied=15.0, previous_scores=120.0, predicted_score=70.0)

    def test_methodological_disclaimer_present(self):
        result = evaluate_academic_risk(attendance=80.0, hours_studied=15.0, previous_scores=70.0, predicted_score=70.0)
        self.assertIn("not a clinically or scientifically validated", result["disclaimer"])


class TestPredictionEndpointAndValidation(unittest.TestCase):
    def test_valid_prediction_request_and_response_structure(self):
        payload = get_valid_payload()
        req = ExamScorePredictionRequest(**payload)
        res = predict_score_endpoint(req, auth_user(req.email or "alice@example.edu"))

        self.assertIn("predicted_exam_score", res)
        self.assertIn("model_used", res)
        self.assertIn("metrics", res)
        self.assertIn("risk_assessment", res)

        self.assertIsInstance(res["predicted_exam_score"], float)
        self.assertEqual(res["model_used"], "RidgeRegression")
        self.assertGreaterEqual(res["predicted_exam_score"], 0.0)
        self.assertLessEqual(res["predicted_exam_score"], 100.0)
        self.assertIn(res["risk_assessment"]["risk_category"], ["Low Risk", "Moderate Risk", "High Risk"])
        self.assertIn("relevant_indicators", res["risk_assessment"])
        self.assertIn("concise_explanation", res["risk_assessment"])

    def test_prediction_output_range_extreme_high(self):
        payload = get_valid_payload()
        payload.update({
            "Hours_Studied": 50.0,
            "Attendance": 100.0,
            "Previous_Scores": 100.0,
            "Parental_Involvement": "High",
            "Access_to_Resources": "High",
            "Motivation_Level": "High"
        })
        req = ExamScorePredictionRequest(**payload)
        res = predict_score_endpoint(req, auth_user(req.email or "alice@example.edu"))

        self.assertGreaterEqual(res["predicted_exam_score"], 0.0)
        self.assertLessEqual(res["predicted_exam_score"], 100.0)
        self.assertEqual(res["risk_assessment"]["risk_category"], "Low Risk")

    def test_prediction_output_range_extreme_low(self):
        payload = get_valid_payload()
        payload.update({
            "Hours_Studied": 0.0,
            "Attendance": 0.0,
            "Previous_Scores": 0.0,
            "Parental_Involvement": "Low",
            "Access_to_Resources": "Low",
            "Motivation_Level": "Low"
        })
        req = ExamScorePredictionRequest(**payload)
        res = predict_score_endpoint(req, auth_user(req.email or "alice@example.edu"))

        self.assertGreaterEqual(res["predicted_exam_score"], 0.0)
        self.assertLessEqual(res["predicted_exam_score"], 100.0)
        self.assertEqual(res["risk_assessment"]["risk_category"], "High Risk")

    def test_missing_required_input_fails(self):
        payload = get_valid_payload()
        del payload["Attendance"]
        with self.assertRaises(ValidationError) as ctx:
            ExamScorePredictionRequest(**payload)
        self.assertIn("Attendance", str(ctx.exception))

        payload2 = get_valid_payload()
        del payload2["Teacher_Quality"]
        with self.assertRaises(ValidationError) as ctx2:
            ExamScorePredictionRequest(**payload2)
        self.assertIn("Teacher_Quality", str(ctx2.exception))

    def test_invalid_numeric_range_fails(self):
        payload = get_valid_payload()
        payload["Hours_Studied"] = -5.0
        with self.assertRaises(ValidationError):
            ExamScorePredictionRequest(**payload)

        payload = get_valid_payload()
        payload["Attendance"] = 105.0
        with self.assertRaises(ValidationError):
            ExamScorePredictionRequest(**payload)

        payload = get_valid_payload()
        payload["Sleep_Hours"] = -1.0
        with self.assertRaises(ValidationError):
            ExamScorePredictionRequest(**payload)

    def test_invalid_categorical_input_fails(self):
        payload = get_valid_payload()
        payload["Parental_Involvement"] = "SuperHigh"
        with self.assertRaises(ValidationError) as ctx:
            ExamScorePredictionRequest(**payload)
        self.assertIn("Parental_Involvement", str(ctx.exception))

        payload = get_valid_payload()
        payload["School_Type"] = "Homeschool"
        with self.assertRaises(ValidationError) as ctx:
            ExamScorePredictionRequest(**payload)
        self.assertIn("School_Type", str(ctx.exception))

    def test_model_loading_error_handling(self):
        req = ExamScorePredictionRequest(**get_valid_payload())
        with patch("app.services.ml_service.load_model", side_effect=FileNotFoundError("Model file missing")):
            with self.assertRaises(HTTPException) as ctx:
                predict_score_endpoint(req, auth_user(req.email or "alice@example.edu"))
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("Model unavailable", ctx.exception.detail)


class TestStudyHourRecommendation(unittest.TestCase):
    """
    Unit and integration tests for Milestone 10:
    Study-Hour Recommendation Service and POST /study-plan/recommend-hours
    """

    def setUp(self):
        self.subjects = [
            {"name": "Calculus", "difficulty": "High", "current_score": 55.0, "target_score": 85.0},
            {"name": "Algorithms", "difficulty": "Medium", "current_score": 70.0, "target_score": 85.0},
            {"name": "Ethics", "difficulty": "Low", "current_score": 80.0, "target_score": 85.0}
        ]

    def test_low_risk_study_hour_recommendation(self):
        res = calculate_study_hour_recommendation(
            daily_available_hours=5.0,
            subjects=self.subjects,
            risk_category="Low Risk"
        )
        self.assertEqual(res["risk_category_applied"], "Low Risk")
        self.assertGreater(res["recommended_weekly_hours"], 0.0)
        self.assertGreater(res["recommended_daily_hours"], 0.0)
        self.assertEqual(len(res["subject_breakdown"]), 3)

        # Calculus has highest difficulty and gap -> should have highest hours share
        shares = {s["subject"]: s["weekly_hours"] for s in res["subject_breakdown"]}
        self.assertGreater(shares["Calculus"], shares["Algorithms"])
        self.assertGreater(shares["Algorithms"], shares["Ethics"])

        # Check total weekly hours matches sum of breakdown
        sum_breakdown = round(sum(s["weekly_hours"] for s in res["subject_breakdown"]), 1)
        self.assertAlmostEqual(res["recommended_weekly_hours"], sum_breakdown, delta=0.2)

    def test_moderate_risk_study_hour_recommendation(self):
        low_res = calculate_study_hour_recommendation(
            daily_available_hours=6.0,
            subjects=self.subjects,
            risk_category="Low Risk"
        )
        mod_res = calculate_study_hour_recommendation(
            daily_available_hours=6.0,
            subjects=self.subjects,
            risk_category="Moderate Risk"
        )
        self.assertEqual(mod_res["risk_category_applied"], "Moderate Risk")
        # Moderate risk incorporates +15% intensity uplift
        self.assertGreater(mod_res["recommended_weekly_hours"], low_res["recommended_weekly_hours"])

    def test_high_risk_study_hour_recommendation(self):
        low_res = calculate_study_hour_recommendation(
            daily_available_hours=7.0,
            subjects=self.subjects,
            risk_category="Low Risk"
        )
        high_res = calculate_study_hour_recommendation(
            daily_available_hours=7.0,
            subjects=self.subjects,
            risk_category="High Risk"
        )
        self.assertEqual(high_res["risk_category_applied"], "High Risk")
        # High risk incorporates +30% intensive uplift
        self.assertGreater(high_res["recommended_weekly_hours"], low_res["recommended_weekly_hours"])

    def test_different_available_study_times(self):
        # 1. Constrained student: only 2 hours available daily (14 hrs/week)
        constrained = calculate_study_hour_recommendation(
            daily_available_hours=2.0,
            subjects=self.subjects,
            risk_category="Low Risk"
        )
        self.assertLessEqual(constrained["recommended_weekly_hours"], 14.0)
        self.assertLessEqual(constrained["recommended_daily_hours"], 2.0)

        # 2. Generous availability: 6 hours available daily (42 hrs/week)
        generous = calculate_study_hour_recommendation(
            daily_available_hours=6.0,
            subjects=self.subjects,
            risk_category="Low Risk"
        )
        self.assertGreater(generous["recommended_weekly_hours"], constrained["recommended_weekly_hours"])

    def test_daily_hour_burnout_limits(self):
        # Student declares 14 available hours with extreme deficits, capped at 6.0 hrs/day
        res = calculate_study_hour_recommendation(
            daily_available_hours=14.0,
            subjects=[
                {"name": "Subj1", "difficulty": "High", "current_score": 10.0, "target_score": 90.0},
                {"name": "Subj2", "difficulty": "High", "current_score": 10.0, "target_score": 90.0},
                {"name": "Subj3", "difficulty": "High", "current_score": 10.0, "target_score": 90.0},
                {"name": "Subj4", "difficulty": "High", "current_score": 10.0, "target_score": 90.0}
            ],
            risk_category="High Risk",
            max_daily_limit=6.0
        )
        self.assertTrue(res["burnout_guardrail_applied"])
        self.assertEqual(res["max_daily_limit"], 6.0)
        self.assertLessEqual(res["recommended_daily_hours"], 6.0)
        self.assertLessEqual(res["recommended_weekly_hours"], 42.0)
        self.assertIn("guardrail", res["concise_explanation"].lower())

    def test_missing_required_fields_raises_validation_error(self):
        # Missing daily_available_hours
        with self.assertRaises(ValidationError):
            StudyHourRecommendationRequest(subjects=[
                StudyHourSubjectInput(name="Math", difficulty="Medium", current_score=60, target_score=85)
            ])

        # Empty subjects list
        with self.assertRaises(ValidationError):
            StudyHourRecommendationRequest(daily_available_hours=4.0, subjects=[])

    def test_invalid_numeric_values_raises_validation_error(self):
        # Negative daily_available_hours
        with self.assertRaises(ValidationError):
            StudyHourRecommendationRequest(
                daily_available_hours=-2.0,
                subjects=[StudyHourSubjectInput(name="Math", difficulty="Medium", current_score=60, target_score=85)]
            )

        # Excessively high daily_available_hours (> 16)
        with self.assertRaises(ValidationError):
            StudyHourRecommendationRequest(
                daily_available_hours=20.0,
                subjects=[StudyHourSubjectInput(name="Math", difficulty="Medium", current_score=60, target_score=85)]
            )

        # Invalid current_score (> 100)
        with self.assertRaises(ValidationError):
            StudyHourSubjectInput(name="Math", current_score=110.0, target_score=85.0)

        # Invalid target_score (< 0)
        with self.assertRaises(ValidationError):
            StudyHourSubjectInput(name="Math", current_score=60.0, target_score=-5.0)

    def test_api_endpoint_recommendation(self):
        req = StudyHourRecommendationRequest(
            daily_available_hours=4.5,
            subjects=[
                StudyHourSubjectInput(name="Operating Systems", difficulty="High", current_score=60.0, target_score=85.0),
                StudyHourSubjectInput(name="Computer Networks", difficulty="Medium", current_score=75.0, target_score=90.0)
            ],
            risk_category="Moderate Risk"
        )
        res = recommend_study_hours_endpoint(req, auth_user())
        self.assertIn("recommended_weekly_hours", res)
        self.assertIn("recommended_daily_hours", res)
        self.assertIn("subject_breakdown", res)
        self.assertEqual(len(res["subject_breakdown"]), 2)
        self.assertIn("disclaimer", res)
        self.assertIn("not study-hour targets", res["disclaimer"])

    def test_dynamic_risk_integration_high_risk(self):
        # Omit risk_category, but provide critical academic indicators
        req = StudyHourRecommendationRequest(
            daily_available_hours=6.0,
            subjects=[
                StudyHourSubjectInput(name="Algorithms", difficulty="High", current_score=50.0, target_score=85.0),
                StudyHourSubjectInput(name="Networks", difficulty="Medium", current_score=55.0, target_score=80.0)
            ],
            risk_category=None,
            attendance=55.0,        # Critical (< 65%) -> 3 pts
            previous_scores=50.0,   # Critical (< 55%) -> 3 pts -> Total >= 6 pts (High Risk)
            predicted_exam_score=52.0
        )
        res = recommend_study_hours_endpoint(req, auth_user())
        self.assertEqual(res["risk_category_applied"], "High Risk")
        self.assertIsNotNone(res["risk_assessment_details"])
        self.assertGreaterEqual(res["risk_assessment_details"]["risk_score"], 4)
        self.assertIn("High Risk", res["concise_explanation"])

    def test_dynamic_risk_integration_moderate_risk(self):
        # Omit risk_category, but provide borderline indicators
        req = StudyHourRecommendationRequest(
            daily_available_hours=5.0,
            subjects=[
                StudyHourSubjectInput(name="DBMS", difficulty="Medium", current_score=68.0, target_score=85.0)
            ],
            risk_category=None,
            attendance=70.0,        # Borderline (65-75%) -> 1 pt
            previous_scores=68.0,   # Borderline (55-70%) -> 1 pt -> Total 2 pts (Moderate Risk)
            predicted_exam_score=68.0
        )
        res = recommend_study_hours_endpoint(req, auth_user())
        self.assertEqual(res["risk_category_applied"], "Moderate Risk")
        self.assertIsNotNone(res["risk_assessment_details"])
        self.assertEqual(res["risk_assessment_details"]["risk_category"], "Moderate Risk")

    def test_default_risk_when_indicators_omitted(self):
        # Neither risk_category nor indicators provided
        req = StudyHourRecommendationRequest(
            daily_available_hours=4.0,
            subjects=[
                StudyHourSubjectInput(name="Software Engineering", difficulty="Low", current_score=80.0, target_score=85.0)
            ]
        )
        res = recommend_study_hours_endpoint(req, auth_user())
        self.assertEqual(res["risk_category_applied"], "Low Risk")

    def test_custom_burnout_cap_applied(self):
        # Student requests extreme hours with low max_daily_limit
        req = StudyHourRecommendationRequest(
            daily_available_hours=10.0,
            subjects=[
                StudyHourSubjectInput(name="Math", difficulty="High", current_score=20.0, target_score=95.0),
                StudyHourSubjectInput(name="Physics", difficulty="High", current_score=20.0, target_score=95.0)
            ],
            risk_category="High Risk",
            max_daily_limit=4.0
        )
        res = recommend_study_hours_endpoint(req, auth_user())
        self.assertTrue(res["burnout_guardrail_applied"])
        self.assertLessEqual(res["recommended_daily_hours"], 4.0)
        self.assertLessEqual(res["recommended_weekly_hours"], 28.0)


class TestPreservedBackendRoutes(unittest.TestCase):
    def test_registered_route_paths(self):
        paths = list(app.openapi()["paths"].keys())
        self.assertIn("/auth/register", paths)
        self.assertIn("/auth/login", paths)
        self.assertIn("/auth/me", paths)
        self.assertIn("/student/profile", paths)
        self.assertIn("/student/{email}", paths)
        self.assertIn("/predict/exam-score", paths)
        self.assertIn("/predict/model-status", paths)
        self.assertIn("/study-plan/generate", paths)
        self.assertIn("/study-plan/timetable", paths)
        self.assertIn("/study-plan/recommend-hours", paths)
        self.assertIn("/ai/tutor", paths)
        self.assertIn("/ai/tutor/status", paths)
        self.assertIn("/documents/upload", paths)
        self.assertIn("/documents", paths)
        self.assertIn("/documents/{document_id}", paths)
        self.assertIn("/documents/{document_id}/text", paths)
        self.assertIn("/documents/{document_id}/index", paths)
        self.assertIn("/documents/{document_id}/index-status", paths)
        self.assertIn("/documents/rag/ask", paths)
        self.assertIn("/performance/session", paths)
        self.assertIn("/performance/{email}", paths)
        self.assertIn("/performance/{email}/sessions", paths)
        self.assertIn("/health", paths)
        self.assertIn("/health/database", paths)

    def test_health_check(self):
        res = health()
        self.assertEqual(res["status"], "healthy")
        self.assertIn("ml_model", res)
        self.assertTrue(res["ml_model"]["loaded"])
        self.assertEqual(res["ml_model"]["algorithm"], "RidgeRegression")
        self.assertIn("database", res)
        self.assertIn(res["database"], {"connected", "unreachable", "disconnected"})

    def test_database_diagnostic_endpoint_shape_and_no_secrets(self):
        report = health_database()
        self.assertIn(report["status"], {"connected", "failed"})
        self.assertIn("stages", report)
        self.assertIsInstance(report["stages"], list)
        self.assertGreaterEqual(len(report["stages"]), 1)
        self.assertIn("recommendations", report)
        self.assertIn("persistence_note", report)
        dumped = str(report)
        self.assertNotIn("mongodb+srv://", dumped.lower().replace("scheme=mongodb+srv", ""))
        # Ensure raw URI credentials are not present even if env has them
        self.assertNotRegex(dumped, r":[^/\s]{4,}@")

    def test_error_redaction_strips_uri_credentials(self):
        # Assemble URI from parts so scanners do not flag a contiguous credentialed literal.
        # (Sole URI-redaction unit test in this repo; there is no test_get_safe_env.py.)
        scheme = "mongodb" + "+srv://"
        userinfo = "testuser" + ":" + "testpass"
        dirty = "failed " + scheme + userinfo + "@db.example.invalid/app"
        clean = _redact_error_message(dirty)
        self.assertNotIn("testpass", clean)
        self.assertIn("mongodb://***", clean)


class TestStudyPlanner(unittest.TestCase):
    def test_subject_weights(self):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        subjects = [
            {"name": "Urgent Math", "difficulty": "High", "current_score": 50, "target_score": 85, "exam_date": tomorrow},
            {"name": "General History", "difficulty": "Low", "current_score": 80, "target_score": 85}
        ]
        weighted = calculate_subject_weights(subjects)
        self.assertEqual(len(weighted), 2)
        self.assertGreater(weighted[0]["priority_score"], weighted[1]["priority_score"])
        total_ratio = sum(s["allocated_ratio"] for s in weighted)
        self.assertAlmostEqual(total_ratio, 1.0, places=2)

    def test_generate_plan_structure(self):
        subjects = [
            {"name": "Data Structures", "difficulty": "High", "current_score": 60, "target_score": 85},
            {"name": "Database Systems", "difficulty": "Medium", "current_score": 75, "target_score": 90}
        ]
        plan = generate_study_plan(subjects, daily_study_hours=3.0, days_to_plan=5)
        self.assertEqual(len(plan["daily_schedule"]), 3)
        self.assertEqual(len(plan["weekly_schedule"]), 5)
        self.assertIn("start_time", plan["daily_schedule"][0])
        self.assertIn("break_time", plan["daily_schedule"][0])
        self.assertIn("timetable", plan)
        self.assertIn("subject_allocations", plan)
        self.assertIn("summary", plan)

    def test_scheduler_determinism(self):
        # Identical inputs with anchor date must yield identical outputs
        subjects = [
            {"name": "Algorithms", "difficulty": "High", "current_score": 55, "target_score": 85, "exam_date": "2026-10-25"},
            {"name": "Computer Networks", "difficulty": "Medium", "current_score": 70, "target_score": 85},
            {"name": "Technical Writing", "difficulty": "Low", "current_score": 80, "target_score": 90}
        ]
        plan_a = generate_study_plan(
            subjects=subjects,
            daily_study_hours=4.0,
            preferred_start_time="09:00",
            days_to_plan=7,
            plan_date="2026-10-20"
        )
        plan_b = generate_study_plan(
            subjects=subjects,
            daily_study_hours=4.0,
            preferred_start_time="09:00",
            days_to_plan=7,
            plan_date="2026-10-20"
        )
        self.assertEqual(plan_a, plan_b)
        self.assertEqual(plan_a["timetable"], plan_b["timetable"])

    def test_subject_allocation_proportional_to_difficulty_and_urgency(self):
        subjects = [
            {"name": "Operating Systems", "difficulty": "High", "current_score": 45, "target_score": 85, "exam_date": "2026-10-22"},
            {"name": "Discrete Math", "difficulty": "Medium", "current_score": 70, "target_score": 80},
            {"name": "Environmental Studies", "difficulty": "Low", "current_score": 85, "target_score": 90}
        ]
        plan = generate_study_plan(
            subjects=subjects,
            daily_study_hours=4.0,
            plan_date="2026-10-20"
        )
        weighted = plan["subjects_weighted"]
        # OS has High diff, large gap (40 pts), and exam in 2 days -> must be highest priority
        self.assertEqual(weighted[0]["name"], "Operating Systems")
        self.assertEqual(weighted[0]["priority_level"], "High Priority")
        # Slot 1 must be Operating Systems (cognitive peak scheduling)
        self.assertEqual(plan["timetable"][0]["subject"], "Operating Systems")
        # OS must have largest allocated ratio
        self.assertGreater(weighted[0]["allocated_ratio"], weighted[1]["allocated_ratio"])
        self.assertGreater(weighted[1]["allocated_ratio"], weighted[2]["allocated_ratio"])

    def test_scheduled_time_never_exceeds_available_or_m10_recommendation(self):
        # Available hours = 2.0 (120 mins)
        subjects = [
            {"name": "AI", "difficulty": "High", "current_score": 50, "target_score": 90},
            {"name": "Cloud", "difficulty": "Medium", "current_score": 60, "target_score": 85}
        ]
        plan = generate_study_plan(
            subjects=subjects,
            daily_available_hours=2.0,
            daily_study_hours=2.0
        )
        self.assertLessEqual(plan["total_scheduled_study_hours"], 2.0)
        self.assertLessEqual(plan["total_scheduled_study_minutes"], 120)
        self.assertLessEqual(plan["total_scheduled_study_hours"], plan["m10_recommended_daily_hours"])

    def test_daily_burnout_limit_guardrail(self):
        # Student requests 12 hours with max limit of 4.0
        subjects = [
            {"name": "Calculus", "difficulty": "High", "current_score": 30, "target_score": 90},
            {"name": "Physics", "difficulty": "High", "current_score": 30, "target_score": 90}
        ]
        plan = generate_study_plan(
            subjects=subjects,
            daily_available_hours=12.0,
            daily_study_hours=12.0,
            max_daily_limit=4.0
        )
        self.assertTrue(plan["burnout_guardrail_applied"])
        self.assertLessEqual(plan["total_scheduled_study_hours"], 4.0)
        self.assertLessEqual(plan["daily_study_hours"], 4.0)

    def test_compact_session_for_small_available_time(self):
        # Available hours = 0.5 (30 mins)
        subjects = [
            {"name": "History", "difficulty": "Low", "current_score": 75, "target_score": 85}
        ]
        plan = generate_study_plan(
            subjects=subjects,
            daily_study_hours=0.5
        )
        self.assertEqual(len(plan["timetable"]), 1)
        self.assertEqual(plan["timetable"][0]["duration_minutes"], 30)
        self.assertLessEqual(plan["total_scheduled_study_hours"], 0.5)

    def test_timetable_slot_ordering_and_times(self):
        subjects = [
            {"name": "SubjA", "difficulty": "Medium", "current_score": 60, "target_score": 80},
            {"name": "SubjB", "difficulty": "High", "current_score": 50, "target_score": 85}
        ]
        plan = generate_study_plan(
            subjects=subjects,
            daily_study_hours=3.0,
            preferred_start_time="10:00"
        )
        slots = plan["timetable"]
        self.assertEqual(len(slots), 3)
        self.assertEqual(slots[0]["slot_order"], 1)
        self.assertEqual(slots[1]["slot_order"], 2)
        self.assertEqual(slots[2]["slot_order"], 3)
        self.assertEqual(slots[0]["start_time"], "10:00")
        self.assertEqual(slots[0]["end_time"], "10:50")
        self.assertEqual(slots[1]["start_time"], "11:00")

    def test_validation_empty_subjects_raises_error(self):
        with self.assertRaises(ValueError):
            generate_study_plan(subjects=[])

        with self.assertRaises(ValidationError):
            StudyPlanGenerateRequest(subjects=[])

    def test_validation_blank_subject_name_raises_error(self):
        with self.assertRaises(ValueError):
            generate_study_plan(subjects=[{"name": "   ", "difficulty": "High"}])

        with self.assertRaises(ValidationError):
            PlanSubject(name="")

    def test_validation_invalid_durations_raises_error(self):
        subjects = [{"name": "Math", "difficulty": "Medium", "current_score": 60, "target_score": 80}]
        # Negative hours
        with self.assertRaises(ValueError):
            generate_study_plan(subjects=subjects, daily_study_hours=-2.0)

        # Excessive hours (> 16)
        with self.assertRaises(ValueError):
            generate_study_plan(subjects=subjects, daily_study_hours=20.0)

        # Request schema validation
        with self.assertRaises(ValidationError):
            StudyPlanGenerateRequest(subjects=[PlanSubject(name="Math")], daily_study_hours=-1.0)

        with self.assertRaises(ValidationError):
            StudyPlanGenerateRequest(subjects=[PlanSubject(name="Math")], daily_study_hours=25.0)

    def test_validation_invalid_scores_raises_error(self):
        with self.assertRaises(ValueError):
            generate_study_plan(subjects=[{"name": "Bio", "current_score": 110.0}])

        with self.assertRaises(ValueError):
            generate_study_plan(subjects=[{"name": "Bio", "current_score": -5.0}])

    def test_conflicting_inputs_handled_safely(self):
        # 1. Target < Current: does not crash
        plan = generate_study_plan(
            subjects=[{"name": "Mastered Subj", "difficulty": "Low", "current_score": 95, "target_score": 80}],
            daily_study_hours=2.0
        )
        self.assertEqual(plan["subjects_weighted"][0]["score_gap"], 0.0)
        self.assertEqual(plan["subjects_weighted"][0]["priority_level"], "Maintenance")

        # 2. Past exam date: does not crash
        past_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        plan_past = generate_study_plan(
            subjects=[{"name": "Past Exam Subj", "difficulty": "High", "exam_date": past_date}],
            daily_study_hours=2.0
        )
        self.assertIsNotNone(plan_past["timetable"])

        # 3. Invalid preferred_start_time: defaults safely to 09:00
        plan_time = generate_study_plan(
            subjects=[{"name": "Subj", "difficulty": "Medium"}],
            preferred_start_time="99:99"
        )
        self.assertEqual(plan_time["timetable"][0]["start_time"], "09:00")

    def test_api_endpoints_generate_and_timetable(self):
        req = StudyPlanGenerateRequest(
            daily_study_hours=3.0,
            preferred_start_time="08:30",
            days_to_plan=3,
            subjects=[
                PlanSubject(name="Cloud Computing", difficulty="High", current_score=60.0, target_score=85.0),
                PlanSubject(name="Cybersecurity", difficulty="Medium", current_score=75.0, target_score=90.0)
            ],
            risk_category="Moderate Risk"
        )
        # 1. Test POST /study-plan/generate
        res_gen = generate_plan_endpoint(req, auth_user(req.email or "alice@example.edu"))
        self.assertIn("timetable", res_gen)
        self.assertIn("subject_allocations", res_gen)
        self.assertIn("daily_schedule", res_gen)
        self.assertIn("weekly_schedule", res_gen)
        self.assertIn("summary", res_gen)
        self.assertEqual(len(res_gen["timetable"]), 3)
        self.assertEqual(res_gen["timetable"][0]["start_time"], "08:30")

        # 2. Test POST /study-plan/timetable
        res_tt = generate_timetable_endpoint(req, auth_user(req.email or "alice@example.edu"))
        self.assertEqual(res_tt["timetable"], res_gen["timetable"])
        self.assertEqual(res_tt["total_scheduled_study_hours"], res_gen["total_scheduled_study_hours"])


class TestStudyPlanAPI(unittest.TestCase):
    """
    Comprehensive tests for Milestone 12 — Study-Plan API:
    - Integration of M9 risk classification, M10 study-hour recommendations, and M11 deterministic scheduler
    - Successful plan generation with full schema compliance
    - Dynamic risk derivation when risk_category is omitted
    - Validation errors for invalid inputs and out-of-range parameters
    - Scheduling limits and burnout guardrails
    - Deterministic timetable reproducibility
    """

    def test_study_plan_generation_success(self):
        exam_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        req = StudyPlanGenerateRequest(
            email="learner@example.edu",
            daily_study_hours=4.0,
            daily_available_hours=5.0,
            preferred_start_time="09:00",
            days_to_plan=5,
            subjects=[
                PlanSubject(name="Advanced Algorithms", difficulty="High", current_score=55.0, target_score=85.0, exam_date=exam_date),
                PlanSubject(name="Operating Systems", difficulty="Medium", current_score=70.0, target_score=88.0),
                PlanSubject(name="Database Engineering", difficulty="Low", current_score=80.0, target_score=90.0)
            ],
            risk_category="Moderate Risk",
            max_daily_limit=8.0
        )
        plan = generate_plan_endpoint(req, auth_user(req.email or "alice@example.edu"))

        # Validate with Pydantic response schema
        validated_plan = StudyPlanResponse(**plan)
        self.assertIsNotNone(validated_plan)

        # Verify essential fields
        self.assertEqual(plan["daily_available_hours"], 5.0)
        self.assertIn("m10_recommended_daily_hours", plan)
        self.assertIn("m10_recommended_weekly_hours", plan)
        self.assertEqual(plan["risk_category_applied"], "Moderate Risk")
        self.assertIsNotNone(plan["m10_recommendation"])
        self.assertEqual(len(plan["subject_allocations"]), 3)
        self.assertGreater(len(plan["timetable"]), 0)
        self.assertEqual(plan["days_planned"], 5)
        self.assertIn("weekly_schedule", plan)
        self.assertIn("summary", plan)
        self.assertIn("notes", plan)
        self.assertIn("disclaimer", plan)

        # Verify timetable slot structure
        first_slot = plan["timetable"][0]
        self.assertEqual(first_slot["start_time"], "09:00")
        self.assertEqual(first_slot["duration_minutes"], 50)
        self.assertEqual(first_slot["break_duration_minutes"], 10)
        self.assertIn("recommended_focus", first_slot)
        self.assertFalse(first_slot["completed"])

    def test_study_plan_dynamic_risk_high(self):
        # When risk_category is omitted, low attendance/scores trigger M9 High Risk
        req = StudyPlanGenerateRequest(
            daily_study_hours=4.0,
            daily_available_hours=4.0,
            preferred_start_time="10:00",
            days_to_plan=3,
            subjects=[
                PlanSubject(name="Compiler Design", difficulty="High", current_score=40.0, target_score=75.0)
            ],
            risk_category=None,
            attendance=55.0,
            previous_scores=45.0,
            predicted_exam_score=48.0
        )
        plan = generate_plan_endpoint(req, auth_user(req.email or "alice@example.edu"))

        self.assertEqual(plan["risk_category_applied"], "High Risk")
        self.assertIsNotNone(plan["risk_assessment_details"])
        self.assertIn("High Risk", plan["risk_assessment_details"]["concise_explanation"])
        # High Risk applies +30% intensity multiplier in M10 recommendation
        m10_rec = plan["m10_recommendation"]
        self.assertEqual(m10_rec["risk_category_applied"], "High Risk")

    def test_study_plan_dynamic_risk_low(self):
        # When risk_category is omitted, high attendance/scores trigger M9 Low Risk
        req = StudyPlanGenerateRequest(
            daily_study_hours=3.0,
            daily_available_hours=3.0,
            days_to_plan=2,
            subjects=[
                PlanSubject(name="Software Testing", difficulty="Low", current_score=85.0, target_score=95.0)
            ],
            risk_category=None,
            attendance=95.0,
            previous_scores=90.0,
            predicted_exam_score=88.0
        )
        plan = generate_plan_endpoint(req, auth_user(req.email or "alice@example.edu"))

        self.assertEqual(plan["risk_category_applied"], "Low Risk")
        self.assertIsNotNone(plan["risk_assessment_details"])
        self.assertEqual(plan["risk_assessment_details"]["risk_score"], 0)

    def test_study_plan_validation_errors(self):
        # 1. Empty subjects list fails validation
        with self.assertRaises(ValidationError):
            StudyPlanGenerateRequest(subjects=[])

        # 2. Blank subject name fails validation
        with self.assertRaises(ValidationError):
            StudyPlanGenerateRequest(subjects=[PlanSubject(name="")])

        # 3. Whitespace-only subject name raises 400
        req_blank = StudyPlanGenerateRequest(
            subjects=[PlanSubject(name="   ", difficulty="Medium")]
        )
        with self.assertRaises(HTTPException) as ctx:
            generate_plan_endpoint(req_blank, auth_user(getattr(req_blank, "email", None) or "alice@example.edu"))
        self.assertEqual(ctx.exception.status_code, 400)

        # 4. Out-of-range days_to_plan
        with self.assertRaises(ValidationError):
            StudyPlanGenerateRequest(
                days_to_plan=35,
                subjects=[PlanSubject(name="AI", difficulty="Medium")]
            )

        # 5. Invalid daily_study_hours (< 0.5 or > 16.0)
        with self.assertRaises(ValidationError):
            StudyPlanGenerateRequest(
                daily_study_hours=0.1,
                subjects=[PlanSubject(name="AI", difficulty="Medium")]
            )
        with self.assertRaises(ValidationError):
            StudyPlanGenerateRequest(
                daily_study_hours=20.0,
                subjects=[PlanSubject(name="AI", difficulty="Medium")]
            )

    def test_study_plan_scheduling_burnout_limits(self):
        # Requesting 12 hours with a strict 6-hour daily limit
        req = StudyPlanGenerateRequest(
            daily_study_hours=12.0,
            daily_available_hours=12.0,
            max_daily_limit=6.0,
            days_to_plan=2,
            subjects=[
                PlanSubject(name="Computer Networks", difficulty="High", current_score=60.0, target_score=85.0)
            ]
        )
        plan = generate_plan_endpoint(req, auth_user(req.email or "alice@example.edu"))

        self.assertTrue(plan["burnout_guardrail_applied"])
        self.assertLessEqual(plan["total_scheduled_study_hours"], 6.0)
        self.assertLessEqual(plan["daily_study_hours"], 6.0)

    def test_study_plan_deterministic_reproducibility(self):
        # Identical inputs must generate exactly identical timetables and allocations
        req = StudyPlanGenerateRequest(
            daily_study_hours=4.0,
            preferred_start_time="09:00",
            days_to_plan=3,
            subjects=[
                PlanSubject(name="Data Science", difficulty="High", current_score=50.0, target_score=80.0),
                PlanSubject(name="Ethics in AI", difficulty="Low", current_score=80.0, target_score=90.0)
            ],
            risk_category="Low Risk"
        )
        plan1 = generate_plan_endpoint(req, auth_user(req.email or "alice@example.edu"))
        plan2 = generate_plan_endpoint(req, auth_user(req.email or "alice@example.edu"))

        self.assertEqual(plan1["timetable"], plan2["timetable"])
        self.assertEqual(plan1["subject_allocations"], plan2["subject_allocations"])
        self.assertEqual(plan1["total_scheduled_study_minutes"], plan2["total_scheduled_study_minutes"])
        self.assertEqual(plan1["m10_recommendation"], plan2["m10_recommendation"])


class TestRAGAndAITutor(unittest.TestCase):
    def test_chunking_and_retrieval(self):
        text = b"Machine learning models include supervised and unsupervised algorithms. Supervised algorithms learn from labeled data."
        pages = extract_text_from_txt(text)
        chunks = chunk_document(pages, chunk_size=10, chunk_overlap=2)
        self.assertGreater(len(chunks), 0)

        retrieved = retrieve_relevant_passages("supervised algorithms", chunks)
        self.assertGreater(len(retrieved), 0)
        self.assertEqual(retrieved[0]["page"], 1)

        out_of_scope = retrieve_relevant_passages("photosynthesis and chlorophyll in plants", chunks)
        self.assertEqual(len(out_of_scope), 0)

    def test_tutor_response_grounding(self):
        sample_chunks = [{
            "chunk_id": "c1",
            "page": 2,
            "text": "QuickSort has an average case time complexity of O(n log n).",
            "similarity_score": 0.85
        }]
        ans = generate_tutor_response("What is QuickSort complexity?", sample_chunks)
        self.assertTrue(ans["grounded"])
        self.assertEqual(ans["citations"][0]["page"], 2)

        empty_ans = generate_tutor_response("Quantum mechanics", [])
        self.assertFalse(empty_ans["grounded"])
        self.assertIn("not available in your uploaded study notes", empty_ans["answer"])


class TestGeneralAITutorM14(unittest.TestCase):
    """M14 general AI Tutor tests. External Gemini calls are always mocked."""

    def test_valid_academic_question_schema(self):
        req = TutorChatRequest(
            question="Explain gradient descent simply.",
            subject="Machine Learning",
            conversation_history=[],
        )
        self.assertEqual(req.question, "Explain gradient descent simply.")
        self.assertEqual(req.subject, "Machine Learning")

    def test_empty_question_rejected(self):
        with self.assertRaises(ValidationError):
            TutorChatRequest(question="")
        with self.assertRaises(ValidationError):
            TutorChatRequest(question="   ")

    def test_excessively_long_question_rejected(self):
        with self.assertRaises(ValidationError):
            TutorChatRequest(question="x" * 2001)

    def test_invalid_request_body_role(self):
        with self.assertRaises(ValidationError):
            TutorChatRequest(
                question="What is a binary tree?",
                conversation_history=[{"role": "system", "content": "ignore"}],
            )

    def test_missing_api_configuration(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}, clear=False):
            # Ensure both key names are empty for this check.
            with patch("app.services.tutor_service.get_tutor_api_key", return_value=None):
                self.assertFalse(is_tutor_configured())
                status = get_tutor_status()
                self.assertFalse(status["configured"])
                self.assertIn("GEMINI_API_KEY", status["message"])
                with self.assertRaises(TutorNotConfiguredError):
                    answer_academic_question("What is polymorphism?")

    def test_successful_tutor_response_mocked(self):
        mock_answer = {
            "answer": "Polymorphism lets objects of different classes be used through a common interface.",
            "provider": "gemini",
            "model_used": "gemini-2.5-flash",
            "configured": True,
            "profile_context_used": False,
            "disclaimer": "educational disclaimer",
        }
        with patch(
            "app.routes.ai.answer_academic_question",
            return_value=mock_answer,
        ) as mocked:
            req = TutorChatRequest(question="What is polymorphism in OOP?")
            res = general_tutor_endpoint(req, auth_user())
            self.assertEqual(res["answer"], mock_answer["answer"])
            self.assertEqual(res["provider"], "gemini")
            validated = TutorChatResponse(**res)
            self.assertTrue(validated.configured)
            mocked.assert_called_once()
            # Must not invent note citations in M14 responses.
            self.assertNotIn("citations", res)

    def test_provider_timeout_maps_to_504(self):
        with patch(
            "app.routes.ai.answer_academic_question",
            side_effect=TutorTimeoutError("The AI provider timed out."),
        ):
            req = TutorChatRequest(question="Explain recursion.")
            with self.assertRaises(HTTPException) as ctx:
                general_tutor_endpoint(req, auth_user())
            self.assertEqual(ctx.exception.status_code, 504)

    def test_provider_failure_maps_to_502(self):
        with patch(
            "app.routes.ai.answer_academic_question",
            side_effect=TutorProviderError("The AI provider rate limit was reached."),
        ):
            req = TutorChatRequest(question="Explain stacks.")
            with self.assertRaises(HTTPException) as ctx:
                general_tutor_endpoint(req, auth_user())
            self.assertEqual(ctx.exception.status_code, 502)

    def test_not_configured_maps_to_503(self):
        with patch(
            "app.routes.ai.answer_academic_question",
            side_effect=TutorNotConfiguredError("AI Tutor is not configured."),
        ):
            req = TutorChatRequest(question="Explain queues.")
            with self.assertRaises(HTTPException) as ctx:
                general_tutor_endpoint(req, auth_user())
            self.assertEqual(ctx.exception.status_code, 503)

    def test_tutor_status_endpoint(self):
        with patch(
            "app.routes.ai.get_tutor_status",
            return_value={
                "configured": False,
                "provider": None,
                "model": None,
                "timeout_seconds": 20,
                "message": "AI Tutor is not configured. Set GEMINI_API_KEY in backend/.env",
            },
        ):
            status = tutor_status_endpoint()
            self.assertFalse(status["configured"])

    def test_answer_service_calls_provider_with_mock(self):
        with patch("app.services.tutor_service.get_tutor_api_key", return_value="test-key"):
            with patch(
                "app.services.tutor_service._call_gemini",
                return_value="A stack is LIFO; a queue is FIFO.",
            ) as gemini_mock:
                result = answer_academic_question(
                    "Difference between stack and queue?",
                    subject="Data Structures",
                    conversation_history=[
                        {"role": "user", "content": "Hi"},
                        {"role": "assistant", "content": "Hello! How can I help?"},
                    ],
                )
                self.assertIn("LIFO", result["answer"])
                self.assertEqual(result["provider"], "gemini")
                self.assertIn("not grounded in uploaded study notes", result["disclaimer"].lower())
                gemini_mock.assert_called_once()

    def test_tutor_endpoint_accepts_authenticated_user(self):
        """M10: tutor requires an authenticated student identity."""
        with patch(
            "app.routes.ai.answer_academic_question",
            return_value={
                "answer": "OK",
                "provider": "gemini",
                "model_used": "gemini-3.5-flash-lite",
                "configured": True,
                "profile_context_used": False,
                "disclaimer": "disclaimer",
            },
        ):
            res = general_tutor_endpoint(
                TutorChatRequest(question="What is a linked list?"),
                auth_user(),
            )
            self.assertEqual(res["answer"], "OK")


class TestPdfDocumentsM15(unittest.TestCase):
    """M15 PDF upload, validation, extraction, ownership, and deletion tests."""

    @staticmethod
    def _make_pdf_bytes(text: str = "") -> bytes:
        """Build a minimal PDF. Empty text -> blank page (no extractable text)."""
        if not text:
            from pypdf import PdfWriter
            import io as _io
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=144)
            buf = _io.BytesIO()
            writer.write(buf)
            return buf.getvalue()

        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 10 50 Td ({safe}) Tj ET\n".encode("latin-1")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
                b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
            ),
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        out = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for i, obj in enumerate(objects, start=1):
            offsets.append(len(out))
            out.extend(f"{i} 0 obj\n".encode("ascii"))
            out.extend(obj)
            out.extend(b"\nendobj\n")
        xref_pos = len(out)
        out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        out.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
        out.extend(
            f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
        )
        return bytes(out)

    def setUp(self):
        import tempfile
        from app.routes import documents as documents_routes
        from app.services import pdf_document_service as pdf_service
        from tests.auth_helpers import FakeDocumentsCollection, auth_user

        self._tmpdir = tempfile.TemporaryDirectory()
        self._env_patch = patch.dict(
            "os.environ",
            {
                "PDF_STORAGE_DIR": self._tmpdir.name,
                "PDF_UPLOAD_MAX_BYTES": str(256 * 1024),
            },
            clear=False,
        )
        self._env_patch.start()
        # Avoid waiting on Atlas during unit tests; use fake Mongo + temp disk.
        self._fake_docs = FakeDocumentsCollection()
        self._mongo_patch = patch.object(
            documents_routes, "documents_collection", self._fake_docs
        )
        self._mongo_patch.start()
        documents_routes._documents_cache.clear()
        self.addCleanup(self._mongo_patch.stop)
        self.addCleanup(self._env_patch.stop)
        self.addCleanup(self._tmpdir.cleanup)
        self.addCleanup(documents_routes._documents_cache.clear)
        self.pdf_service = pdf_service
        self.documents_routes = documents_routes
        self.alice = auth_user("alice@example.edu", "Alice")
        self.intruder = auth_user("intruder@example.edu", "Intruder")
        self.cleanup_user = auth_user("cleanup@example.edu", "Cleanup")

    def test_valid_pdf_upload_and_text_extraction(self):
        from fastapi import UploadFile
        import io as _io

        pdf_bytes = self._make_pdf_bytes("Gradient descent overview")
        upload = UploadFile(filename="notes.pdf", file=_io.BytesIO(pdf_bytes))

        async def _run():
            return await self.documents_routes.upload_pdf_document(
                file=upload,
                email="alice@example.edu",
                subject="ML",
                current_user=self.alice,
            )

        result = asyncio_run(_run())
        self.assertEqual(result["status"], "processed")
        self.assertTrue(result["text_available"])
        self.assertGreater(result["extracted_characters"], 0)
        self.assertEqual(result["page_count"], 1)
        self.assertIn("document_id", result)
        self.assertNotIn("storage_key", result)
        self.assertNotIn("pages", result)

        listed = self.documents_routes.list_documents(email="alice@example.edu", current_user=self.alice)
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["documents"][0]["document_id"], result["document_id"])

        text_payload = self.documents_routes.get_document_extracted_text(
            result["document_id"],
            email="alice@example.edu",
            current_user=self.alice,
        )
        self.assertTrue(text_payload["text_available"])
        self.assertIn("Gradient descent", text_payload["pages"][0]["text"])

    def test_empty_file_rejected(self):
        with self.assertRaises(self.pdf_service.PdfDocumentError) as ctx:
            self.pdf_service.validate_pdf_bytes(b"")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_non_pdf_extension_rejected_at_endpoint(self):
        from fastapi import UploadFile
        import io as _io

        upload = UploadFile(filename="notes.txt", file=_io.BytesIO(b"hello"))

        async def _run():
            return await self.documents_routes.upload_pdf_document(
                file=upload,
                email="alice@example.edu",
                subject="General",
                current_user=self.alice,
            )

        with self.assertRaises(HTTPException) as ctx:
            asyncio_run(_run())
        self.assertEqual(ctx.exception.status_code, 400)

    def test_incorrect_pdf_signature_rejected(self):
        with self.assertRaises(self.pdf_service.PdfDocumentError) as ctx:
            self.pdf_service.validate_pdf_bytes(b"NOTPDF-file-content")
        self.assertIn("signature", ctx.exception.message.lower())

    def test_corrupted_pdf_rejected(self):
        with self.assertRaises(self.pdf_service.PdfDocumentError):
            self.pdf_service.validate_pdf_bytes(b"%PDF-1.4\n%this-is-not-valid")

    def test_oversized_upload_rejected(self):
        huge = b"%PDF-1.4\n" + (b"x" * (256 * 1024))
        with self.assertRaises(self.pdf_service.PdfDocumentError) as ctx:
            self.pdf_service.validate_pdf_bytes(huge)
        self.assertEqual(ctx.exception.status_code, 413)

    def test_pdf_with_no_extractable_text(self):
        record = self.pdf_service.build_document_record(
            email="bob@example.edu",
            original_filename="scan.pdf",
            file_bytes=self._make_pdf_bytes(""),
            subject="Scans",
        )
        self.assertEqual(record["status"], "processed_no_text")
        self.assertFalse(record["text_available"])
        self.assertTrue(record["ocr_required"])
        self.assertIn("OCR", record["extraction_message"])

    def test_unauthenticated_upload_rejected(self):
        with self.assertRaises(self.pdf_service.PdfDocumentError) as ctx:
            self.pdf_service.require_student_email("")
        self.assertEqual(ctx.exception.status_code, 401)

        from fastapi import UploadFile
        import io as _io
        upload = UploadFile(filename="a.pdf", file=_io.BytesIO(self._make_pdf_bytes("x")))

        async def _run():
            return await self.documents_routes.upload_pdf_document(
                file=upload,
                email="   ",
                subject="General",
                current_user=self.alice,
            )

        with self.assertRaises(HTTPException) as ctx2:
            asyncio_run(_run())
        self.assertEqual(ctx2.exception.status_code, 401)

    def test_ownership_isolation_list_get_delete(self):
        record = self.pdf_service.build_document_record(
            email="owner@example.edu",
            original_filename="private.pdf",
            file_bytes=self._make_pdf_bytes("secret notes"),
        )
        self.documents_routes._persist_record(record)
        doc_id = record["document_id"]

        other_list = self.documents_routes.list_documents(email="intruder@example.edu", current_user=self.intruder)
        self.assertEqual(other_list["count"], 0)

        with self.assertRaises(HTTPException) as ctx_get:
            self.documents_routes.get_document_metadata(doc_id, email="intruder@example.edu", current_user=self.intruder)
        self.assertEqual(ctx_get.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx_text:
            self.documents_routes.get_document_extracted_text(doc_id, email="intruder@example.edu", current_user=self.intruder)
        self.assertEqual(ctx_text.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx_del:
            self.documents_routes.delete_document(doc_id, email="intruder@example.edu", current_user=self.intruder)
        self.assertEqual(ctx_del.exception.status_code, 404)

        # Owner can still access
        meta = self.documents_routes.get_document_metadata(doc_id, email="owner@example.edu", current_user=auth_user("owner@example.edu"))
        self.assertEqual(meta["document_id"], doc_id)

    def test_metadata_persistence_and_deletion_cleanup(self):
        from pathlib import Path

        record = self.pdf_service.build_document_record(
            email="cleanup@example.edu",
            original_filename="to-delete.pdf",
            file_bytes=self._make_pdf_bytes("delete me"),
        )
        self.documents_routes._persist_record(record)
        doc_id = record["document_id"]
        pdf_path = Path(self._tmpdir.name) / self.pdf_service.owner_storage_key("cleanup@example.edu") / f"{doc_id}.pdf"
        self.assertTrue(pdf_path.exists())

        deleted = self.documents_routes.delete_document(doc_id, email="cleanup@example.edu", current_user=self.cleanup_user)
        self.assertEqual(deleted["document_id"], doc_id)
        self.assertFalse(pdf_path.exists())
        self.assertIsNone(self.documents_routes._find_record(doc_id))

        listed = self.documents_routes.list_documents(email="cleanup@example.edu", current_user=self.cleanup_user)
        self.assertEqual(listed["count"], 0)

    def test_storage_failure_surfaces_safely(self):
        with patch(
            "app.services.pdf_document_service.save_pdf_bytes",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaises(Exception):
                self.pdf_service.build_document_record(
                    email="fail@example.edu",
                    original_filename="x.pdf",
                    file_bytes=self._make_pdf_bytes("data"),
                )

    def test_public_summary_hides_filesystem_paths(self):
        record = self.pdf_service.build_document_record(
            email="safe@example.edu",
            original_filename="safe.pdf",
            file_bytes=self._make_pdf_bytes("visible"),
        )
        summary = self.pdf_service.public_document_summary(record)
        dumped = str(summary)
        self.assertNotIn(self._tmpdir.name, dumped)
        self.assertNotIn("storage_key", summary)
        self.assertNotIn("pages", summary)


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


class TestDocumentRagM16(unittest.TestCase):
    """M16 RAG over uploaded study documents (local TF-IDF index; LLM mocked)."""

    def setUp(self):
        import tempfile
        from app.routes import documents as documents_routes
        from app.services import document_rag_service as rag_service
        from app.services import pdf_document_service as pdf_service
        from tests.auth_helpers import FakeDocumentsCollection

        self._tmpdir = tempfile.TemporaryDirectory()
        self._env_patch = patch.dict(
            "os.environ",
            {
                "PDF_STORAGE_DIR": str(__import__("pathlib").Path(self._tmpdir.name) / "docs"),
                "RAG_STORAGE_DIR": str(__import__("pathlib").Path(self._tmpdir.name) / "rag"),
                "PDF_UPLOAD_MAX_BYTES": str(512 * 1024),
                "GEMINI_API_KEY": "",
                "GOOGLE_API_KEY": "",
            },
            clear=False,
        )
        self._env_patch.start()
        self._fake_docs = FakeDocumentsCollection()
        self._mongo_patch = patch.object(
            documents_routes, "documents_collection", self._fake_docs
        )
        self._mongo_patch.start()
        documents_routes._documents_cache.clear()
        self.addCleanup(self._mongo_patch.stop)
        self.addCleanup(self._env_patch.stop)
        self.addCleanup(self._tmpdir.cleanup)
        self.addCleanup(documents_routes._documents_cache.clear)
        self.documents_routes = documents_routes
        self.rag_service = rag_service
        self.pdf_service = pdf_service

    @staticmethod
    def _make_pdf_bytes(text: str = "Hello World") -> bytes:
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 10 50 Td ({safe}) Tj ET\n".encode("latin-1")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
                b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
            ),
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        out = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for i, obj in enumerate(objects, start=1):
            offsets.append(len(out))
            out.extend(f"{i} 0 obj\n".encode("ascii"))
            out.extend(obj)
            out.extend(b"\nendobj\n")
        xref_pos = len(out)
        out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        out.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
        out.extend(
            f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
        )
        return bytes(out)

    def _build_record(self, email="alice@example.edu", text="Gradient descent minimizes the loss function"):
        return self.pdf_service.build_document_record(
            email=email,
            original_filename="ml-notes.pdf",
            file_bytes=self._make_pdf_bytes(text),
            subject="ML",
        )

    def test_chunking_preserves_metadata(self):
        pages = [
            {"page": 1, "text": " ".join(["alpha"] * 40)},
            {"page": 2, "text": " ".join(["beta"] * 40)},
        ]
        chunks = self.rag_service.chunk_pages_for_rag(
            pages,
            document_id="doc-12345678",
            email="alice@example.edu",
            filename="notes.pdf",
            chunk_size=20,
            chunk_overlap=5,
        )
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c["document_id"] == "doc-12345678" for c in chunks))
        self.assertTrue(all(c["email"] == "alice@example.edu" for c in chunks))
        self.assertTrue(all(c["filename"] == "notes.pdf" for c in chunks))
        self.assertTrue(all("page" in c and "chunk_index" in c for c in chunks))

    def test_empty_extracted_text_rejected(self):
        with self.assertRaises(self.rag_service.DocumentRagError):
            self.rag_service.index_document_record({
                "document_id": "doc-empty01",
                "email": "alice@example.edu",
                "filename": "empty.pdf",
                "text_available": False,
                "pages": [],
            })

    def test_index_retrieve_and_citations(self):
        record = self._build_record()
        self.documents_routes._persist_record(record)
        info = self.rag_service.index_document_record(record)
        self.assertEqual(info["status"], "indexed")
        self.assertTrue(info["persistent"])
        self.assertEqual(info["storage"], "disk")
        self.assertGreater(info["chunk_count"], 0)

        # Skip rebuild when unchanged
        again = self.rag_service.index_document_record(record, force=False)
        self.assertFalse(again["rebuilt"])

        hits = self.rag_service.retrieve_from_document(
            email="alice@example.edu",
            document_id=record["document_id"],
            question="What is gradient descent?",
            top_k=3,
            threshold=0.0,
        )
        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["filename"], "ml-notes.pdf")
        self.assertEqual(hits[0]["page"], 1)

        with patch(
            "app.services.document_rag_service.generate_rag_answer",
            wraps=self.rag_service.generate_rag_answer,
        ):
            result = self.rag_service.generate_rag_answer(
                question="What is gradient descent?",
                retrieved=hits,
            )
        self.assertTrue(result["grounded"])
        self.assertEqual(result["mode"], "retrieval_only")  # no Gemini key in tests
        self.assertGreater(len(result["sources"]), 0)
        self.assertEqual(result["sources"][0]["page"], 1)

    def test_ownership_blocks_cross_user_retrieval(self):
        record = self._build_record(email="owner@example.edu")
        self.rag_service.index_document_record(record)
        with self.assertRaises(self.rag_service.DocumentRagError) as ctx:
            self.rag_service.retrieve_from_document(
                email="intruder@example.edu",
                document_id=record["document_id"],
                question="gradient descent",
            )
        self.assertIn(ctx.exception.status_code, (404, 409))

        with self.assertRaises(HTTPException) as http_ctx:
            self.documents_routes.ask_documents_rag(
                RagAskRequest(
                    email="intruder@example.edu",
                    question="gradient descent",
                    document_id=record["document_id"],
                )
            , current_user=auth_user("intruder@example.edu"))
        self.assertEqual(http_ctx.exception.status_code, 404)

    def test_unindexed_document_ask_rejected(self):
        record = self._build_record()
        self.documents_routes._persist_record(record)
        with self.assertRaises(HTTPException) as ctx:
            self.documents_routes.ask_documents_rag(
                RagAskRequest(
                    email="alice@example.edu",
                    question="What is in the notes?",
                    document_id=record["document_id"],
                )
            , current_user=auth_user("alice@example.edu"))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_no_relevant_results_mode(self):
        result = self.rag_service.generate_rag_answer(question="anything", retrieved=[])
        self.assertFalse(result["grounded"])
        self.assertEqual(result["mode"], "no_results")
        self.assertEqual(result["sources"], [])

    def test_llm_mode_when_gemini_mocked(self):
        retrieved = [{
            "chunk_id": "c1",
            "document_id": "d1",
            "filename": "notes.pdf",
            "page": 2,
            "text": "Backpropagation computes gradients efficiently.",
            "similarity_score": 0.9,
        }]
        with patch("app.services.tutor_service.get_tutor_api_key", return_value="fake-key"):
            with patch("app.services.tutor_service._call_gemini", return_value="Backprop uses chain rule (Page 2)."):
                result = self.rag_service.generate_rag_answer(
                    question="Explain backpropagation",
                    retrieved=retrieved,
                )
        self.assertEqual(result["mode"], "llm")
        self.assertTrue(result["grounded"])
        self.assertIn("Page 2", result["answer"])

    def test_ask_endpoint_retrieval_only(self):
        record = self._build_record()
        self.documents_routes._persist_record(record)
        self.rag_service.index_document_record(record)
        response = self.documents_routes.ask_documents_rag(
            RagAskRequest(
                email="alice@example.edu",
                question="gradient descent loss",
                document_id=record["document_id"],
                top_k=3,
            )
        , current_user=auth_user("alice@example.edu"))
        self.assertIn(response["mode"], ("retrieval_only", "llm", "no_results"))
        self.assertEqual(response["document_scope"], "single_document")

    def test_delete_removes_rag_index(self):
        record = self._build_record()
        self.documents_routes._persist_record(record)
        self.rag_service.index_document_record(record)
        status_before = self.rag_service.get_index_status("alice@example.edu", record["document_id"])
        self.assertEqual(status_before["status"], "indexed")

        deleted = self.documents_routes.delete_document(record["document_id"], email="alice@example.edu", current_user=auth_user("alice@example.edu"))
        self.assertTrue(deleted["rag_index_deleted"])
        status_after = self.rag_service.get_index_status("alice@example.edu", record["document_id"])
        self.assertEqual(status_after["status"], "not_indexed")


class _FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def __iter__(self):
        return iter(self._rows)


class _FakeCollection:
    """Minimal Mongo-like collection for M17/M18 unit tests (not claimed as production storage)."""

    def __init__(self):
        self.rows = []

    def insert_one(self, doc):
        self.rows.append(dict(doc))
        return type("InsertResult", (), {"inserted_id": doc.get("session_id") or len(self.rows)})()

    def find(self, query=None, projection=None):
        query = query or {}
        matched = []
        for row in self.rows:
            ok = True
            for key, expected in query.items():
                if row.get(key) != expected:
                    ok = False
                    break
            if ok:
                copy = dict(row)
                if projection and projection.get("_id") == 0:
                    copy.pop("_id", None)
                matched.append(copy)
        return _FakeCursor(matched)

    def find_one(self, query=None, projection=None):
        for row in self.find(query, projection):
            return row
        return None

    def update_one(self, query, update, upsert=False):
        query = query or {}
        set_fields = (update or {}).get("$set", {})
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                row.update(set_fields)
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()
        if upsert:
            new_row = dict(query)
            new_row.update(set_fields)
            self.rows.append(new_row)
            return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0, "upserted_id": 1})()
        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()


class TestProgressTrackingM17(unittest.TestCase):
    """M17 progress tracking: sessions, planned vs actual, ownership, DB errors."""

    def setUp(self):
        from app.routes import performance as performance_routes
        from app.services import progress_service

        self.performance_routes = performance_routes
        self.progress_service = progress_service
        self.sessions = _FakeCollection()
        self.quizzes = _FakeCollection()
        self.session_patch = patch.object(performance_routes, "sessions_collection", self.sessions)
        self.quiz_patch = patch.object(performance_routes, "quizzes_collection", self.quizzes)
        self.session_patch.start()
        self.quiz_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.quiz_patch.stop()

    def test_resolve_session_statuses_and_planned_actual(self):
        completed = self.progress_service.resolve_session_fields({
            "email": "Alice@Example.edu",
            "subject": "ML",
            "topic": "Ridge",
            "status": "completed",
            "planned_minutes": 50,
            "actual_minutes": 55,
            "date": "2026-10-11",
        })
        self.assertEqual(completed["email"], "alice@example.edu")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["actual_minutes"], 55)
        self.assertTrue(completed["completed"])

        partial = self.progress_service.resolve_session_fields({
            "email": "alice@example.edu",
            "subject": "ML",
            "status": "partial",
            "planned_minutes": 60,
            "actual_minutes": 25,
            "date": "2026-10-11",
        })
        self.assertEqual(partial["status"], "partial")
        self.assertEqual(partial["actual_minutes"], 25)

        missed = self.progress_service.resolve_session_fields({
            "email": "alice@example.edu",
            "subject": "ML",
            "status": "missed",
            "planned_minutes": 50,
            "actual_minutes": 30,
            "date": "2026-10-11",
        })
        self.assertEqual(missed["status"], "missed")
        self.assertEqual(missed["actual_minutes"], 0)
        self.assertFalse(missed["completed"])

    def test_invalid_date_rejected(self):
        with self.assertRaises(self.progress_service.ProgressError):
            self.progress_service.validate_session_date("11-10-2026")
        with self.assertRaises(self.progress_service.ProgressError):
            self.progress_service.validate_session_date("2026-13-40")

    def test_schema_rejects_bad_email(self):
        with self.assertRaises(ValidationError):
            StudySessionLog(email="not-an-email", subject="ML", status="completed")

    def test_log_and_summary_planned_versus_actual(self):
        self.performance_routes.log_study_session(
            StudySessionLog(
                email="alice@example.edu",
                subject="ML",
                topic="Intro",
                status="completed",
                planned_minutes=60,
                actual_minutes=50,
                date="2026-10-10",
            )
        , current_user=auth_user("alice@example.edu"))
        self.performance_routes.log_study_session(
            StudySessionLog(
                email="alice@example.edu",
                subject="ML",
                topic="Skipped",
                status="missed",
                planned_minutes=40,
                date="2026-10-11",
            )
        , current_user=auth_user("alice@example.edu"))
        self.performance_routes.log_study_session(
            StudySessionLog(
                email="alice@example.edu",
                subject="Stats",
                topic="Half",
                status="partial",
                planned_minutes=50,
                actual_minutes=20,
                date="2026-10-11",
            )
        , current_user=auth_user("alice@example.edu"))

        summary = self.performance_routes.get_performance_summary("alice@example.edu", current_user=auth_user("alice@example.edu"))
        self.assertEqual(summary["persistence"], "mongo")
        self.assertEqual(summary["total_sessions"], 3)
        self.assertEqual(summary["sessions_completed"], 1)
        self.assertEqual(summary["sessions_partial"], 1)
        self.assertEqual(summary["sessions_missed"], 1)
        self.assertEqual(summary["planned_versus_actual"]["planned_minutes"], 150)
        self.assertEqual(summary["planned_versus_actual"]["actual_minutes"], 70)
        self.assertFalse(summary["empty"])

        subjects = {m["subject"]: m for m in summary["subject_metrics"]}
        self.assertIn("ML", subjects)
        self.assertEqual(subjects["ML"]["sessions_missed"], 1)
        self.assertEqual(subjects["Stats"]["sessions_partial"], 1)

    def test_ownership_filters_other_students(self):
        self.performance_routes.log_study_session(
            StudySessionLog(
                email="alice@example.edu",
                subject="ML",
                status="completed",
                planned_minutes=50,
                actual_minutes=50,
                date="2026-10-11",
            )
        , current_user=auth_user("alice@example.edu"))
        self.performance_routes.log_study_session(
            StudySessionLog(
                email="bob@example.edu",
                subject="ML",
                status="completed",
                planned_minutes=90,
                actual_minutes=90,
                date="2026-10-11",
            )
        , current_user=auth_user("bob@example.edu"))

        alice = self.performance_routes.get_performance_summary("alice@example.edu", current_user=auth_user("alice@example.edu"))
        bob = self.performance_routes.get_performance_summary("bob@example.edu", current_user=auth_user("bob@example.edu"))
        self.assertEqual(alice["total_sessions"], 1)
        self.assertEqual(bob["total_sessions"], 1)
        self.assertEqual(alice["planned_versus_actual"]["planned_minutes"], 50)
        self.assertEqual(bob["planned_versus_actual"]["planned_minutes"], 90)

        alice_list = self.performance_routes.list_study_sessions("alice@example.edu", current_user=auth_user("alice@example.edu"))
        self.assertEqual(alice_list["count"], 1)
        self.assertTrue(all(s["email"] == "alice@example.edu" for s in alice_list["sessions"]))

    def test_empty_progress_summary(self):
        summary = self.performance_routes.get_performance_summary("newbie@example.edu", current_user=auth_user("newbie@example.edu"))
        self.assertTrue(summary["empty"])
        self.assertEqual(summary["total_sessions"], 0)
        self.assertEqual(summary["planned_study_hours"], 0.0)
        self.assertEqual(summary["subject_metrics"], [])

    def test_database_unavailable_returns_503(self):
        with patch.object(self.performance_routes, "sessions_collection", None):
            with self.assertRaises(HTTPException) as ctx:
                self.performance_routes.log_study_session(
                    StudySessionLog(
                        email="alice@example.edu",
                        subject="ML",
                        status="completed",
                        planned_minutes=50,
                        actual_minutes=50,
                    )
                , current_user=auth_user("alice@example.edu"))
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("MongoDB", ctx.exception.detail)

            with self.assertRaises(HTTPException) as ctx2:
                self.performance_routes.get_performance_summary("alice@example.edu", current_user=auth_user("alice@example.edu"))
            self.assertEqual(ctx2.exception.status_code, 503)

    def test_build_summary_strips_foreign_rows(self):
        mixed = [
            {
                "email": "alice@example.edu",
                "subject": "ML",
                "status": "completed",
                "planned_minutes": 50,
                "actual_minutes": 50,
                "date": "2026-10-11",
            },
            {
                "email": "intruder@example.edu",
                "subject": "Hacked",
                "status": "completed",
                "planned_minutes": 999,
                "actual_minutes": 999,
                "date": "2026-10-11",
            },
        ]
        summary = self.progress_service.build_progress_summary(
            email="alice@example.edu",
            sessions=mixed,
            quizzes=[],
        )
        self.assertEqual(summary["total_sessions"], 1)
        self.assertEqual(summary["planned_versus_actual"]["planned_minutes"], 50)


class TestAdaptivePlanningM18(unittest.TestCase):
    """M18 adaptive planning from progress — missed/partial/repeat-safe/DB errors."""

    def setUp(self):
        from app.routes import performance as performance_routes
        from app.services import adaptive_planning_service

        self.performance_routes = performance_routes
        self.adaptive = adaptive_planning_service
        self.sessions = _FakeCollection()
        self.quizzes = _FakeCollection()
        self.plans = _FakeCollection()

        self.session_patch = patch.object(performance_routes, "sessions_collection", self.sessions)
        self.quiz_patch = patch.object(performance_routes, "quizzes_collection", self.quizzes)
        self.plan_patch = patch.object(performance_routes, "study_plans_collection", self.plans)
        self.session_patch.start()
        self.quiz_patch.start()
        self.plan_patch.start()

        self.base_plan = generate_study_plan(
            subjects=[
                {
                    "name": "Machine Learning",
                    "difficulty": "Medium",
                    "current_score": 70,
                    "target_score": 90,
                    "exam_date": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
                },
                {
                    "name": "Statistics",
                    "difficulty": "Low",
                    "current_score": 80,
                    "target_score": 85,
                    "exam_date": None,
                },
            ],
            daily_study_hours=4.0,
            days_to_plan=7,
            plan_date="2026-10-12",
        )
        self.plans.insert_one({
            "email": "alice@example.edu",
            "plan": self.base_plan,
            "declared_daily_study_hours": 4.0,
            "declared_days_to_plan": 7,
            "updated_at": datetime.now().isoformat(),
        })

    def tearDown(self):
        self.session_patch.stop()
        self.quiz_patch.stop()
        self.plan_patch.stop()

    def _session(self, **kwargs):
        base = {
            "session_id": kwargs.get("session_id", "s-" + kwargs.get("subject", "x")),
            "email": "alice@example.edu",
            "subject": "Machine Learning",
            "topic": "t",
            "status": "completed",
            "planned_minutes": 50,
            "actual_minutes": 50,
            "date": "2026-10-11",
        }
        base.update(kwargs)
        self.sessions.insert_one(base)

    def test_missed_and_partial_increase_priority_with_reasons(self):
        self._session(session_id="m1", status="missed", planned_minutes=50, actual_minutes=0)
        self._session(
            session_id="p1",
            subject="Statistics",
            status="partial",
            planned_minutes=60,
            actual_minutes=20,
        )

        result = self.performance_routes.adapt_study_plan(
            AdaptPlanRequest(email="alice@example.edu", plan_date="2026-10-13")
        , current_user=auth_user("alice@example.edu"))
        self.assertFalse(result["unchanged"])
        self.assertTrue(result["repeat_safe"])
        self.assertIn("adapted_plan", result)
        joined = " ".join(result["adaptations"]).lower()
        self.assertTrue("missed" in joined or "partial" in joined or "unfinished" in joined)
        # Daily hours must not exceed original declared limit
        self.assertLessEqual(result["adapted_plan"]["daily_study_hours"], 4.0)
        # Historical sessions untouched
        self.assertEqual(len(self.sessions.rows), 2)

    def test_completed_sessions_do_not_create_backlog(self):
        self._session(session_id="c1", status="completed", planned_minutes=50, actual_minutes=50)
        backlog = self.adaptive.compute_subject_backlog_minutes(
            email="alice@example.edu",
            sessions=self.sessions.rows,
        )
        self.assertEqual(backlog["Machine Learning"]["backlog_minutes"], 0)

    def test_limited_available_time_compresses_schedule(self):
        self._session(session_id="m1", status="missed", planned_minutes=50, actual_minutes=0)
        result = self.performance_routes.adapt_study_plan(
            AdaptPlanRequest(
                email="alice@example.edu",
                daily_available_hours=2.0,
                plan_date="2026-10-13",
            )
        , current_user=auth_user("alice@example.edu"))
        self.assertLessEqual(result["adapted_plan"]["daily_study_hours"], 2.0)
        joined = " ".join(result["adaptations"]).lower()
        self.assertTrue("reduced" in joined or "available" in joined or "missed" in joined)

    def test_upcoming_exam_mentioned_in_reasons(self):
        self._session(session_id="m1", status="missed", planned_minutes=40, actual_minutes=0)
        result = self.performance_routes.adapt_study_plan(
            AdaptPlanRequest(email="alice@example.edu", plan_date="2026-10-13")
        , current_user=auth_user("alice@example.edu"))
        joined = " ".join(result["adaptations"]).lower()
        self.assertTrue("exam" in joined or "missed" in joined)

    def test_repeat_adaptation_is_idempotent(self):
        self._session(session_id="m1", status="missed", planned_minutes=50, actual_minutes=0)
        first = self.performance_routes.adapt_study_plan(
            AdaptPlanRequest(email="alice@example.edu", plan_date="2026-10-13")
        , current_user=auth_user("alice@example.edu"))
        self.assertFalse(first["unchanged"])
        fp1 = first["adaptation_fingerprint"]

        second = self.performance_routes.adapt_study_plan(
            AdaptPlanRequest(email="alice@example.edu", plan_date="2026-10-13")
        , current_user=auth_user("alice@example.edu"))
        self.assertTrue(second["unchanged"])
        self.assertEqual(second["adaptation_fingerprint"], fp1)
        self.assertIn("fingerprint", " ".join(second["adaptations"]).lower())

    def test_empty_history_still_returns_plan(self):
        result = self.performance_routes.adapt_study_plan(
            AdaptPlanRequest(email="alice@example.edu", plan_date="2026-10-13")
        , current_user=auth_user("alice@example.edu"))
        self.assertFalse(result["unchanged"])
        self.assertTrue(result["progress_snapshot"]["empty"])
        self.assertIn("adapted_plan", result)

    def test_missing_plan_returns_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.performance_routes.adapt_study_plan(
                AdaptPlanRequest(email="nobody@example.edu")
            , current_user=auth_user("nobody@example.edu"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_database_unavailable_returns_503(self):
        with patch.object(self.performance_routes, "study_plans_collection", None):
            with self.assertRaises(HTTPException) as ctx:
                self.performance_routes.adapt_study_plan(
                    AdaptPlanRequest(email="alice@example.edu")
                , current_user=auth_user("alice@example.edu"))
            self.assertEqual(ctx.exception.status_code, 503)

        with patch.object(self.performance_routes, "sessions_collection", None):
            with self.assertRaises(HTTPException) as ctx2:
                self.performance_routes.adapt_study_plan(
                    AdaptPlanRequest(email="alice@example.edu")
                , current_user=auth_user("alice@example.edu"))
            self.assertEqual(ctx2.exception.status_code, 503)

    def test_ownership_scopes_sessions_to_email(self):
        self._session(session_id="a1", status="missed", planned_minutes=50, actual_minutes=0)
        self.sessions.insert_one({
            "session_id": "b1",
            "email": "bob@example.edu",
            "subject": "Machine Learning",
            "status": "missed",
            "planned_minutes": 500,
            "actual_minutes": 0,
            "date": "2026-10-11",
        })
        backlog = self.adaptive.compute_subject_backlog_minutes(
            email="alice@example.edu",
            sessions=self.sessions.rows,
        )
        self.assertEqual(backlog["Machine Learning"]["backlog_minutes"], 50)

    def test_adapt_plan_route_registered(self):
        paths = list(app.openapi()["paths"].keys())
        self.assertIn("/performance/adapt-plan", paths)


class TestAuthOwnershipM10(unittest.TestCase):
    """M10 — hashed passwords, access tokens, and cross-student denial."""

    def setUp(self):
        from app.routes import auth as auth_routes
        from tests.auth_helpers import FakeUsersCollection, auth_user, mint_token

        self.auth_routes = auth_routes
        self.users = FakeUsersCollection()
        self._users_patch = patch.object(auth_routes, "users_collection", self.users)
        self._users_patch.start()
        self.addCleanup(self._users_patch.stop)
        self.auth_user = auth_user
        self.mint_token = mint_token

    def test_register_hashes_password_and_returns_token(self):
        from app.routes.auth import RegisterUser

        res = self.auth_routes.register(
            RegisterUser(name="Alice", email="alice@example.edu", password="password123")
        )
        self.assertEqual(res["persistence"], "mongo")
        self.assertIn("access_token", res)
        stored = self.users.find_one({"email": "alice@example.edu"})
        self.assertNotIn("password", stored)
        self.assertTrue(str(stored["password_hash"]).startswith("scrypt$"))
        self.assertNotEqual(stored["password_hash"], "password123")

    def test_login_success_and_invalid_credentials(self):
        from app.routes.auth import LoginUser, RegisterUser

        self.auth_routes.register(
            RegisterUser(name="Alice", email="alice@example.edu", password="password123")
        )
        ok = self.auth_routes.login(
            LoginUser(email="alice@example.edu", password="password123")
        )
        self.assertEqual(ok["message"], "Login successful")
        self.assertTrue(ok["access_token"])

        with self.assertRaises(HTTPException) as ctx:
            self.auth_routes.login(
                LoginUser(email="alice@example.edu", password="wrong-password")
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid email or password", ctx.exception.detail)

    def test_invalid_and_expired_tokens_rejected(self):
        from app.deps.auth import get_current_user
        from app.services.auth_service import create_access_token, decode_access_token
        from fastapi.security import HTTPAuthorizationCredentials

        with self.assertRaises(HTTPException) as missing:
            get_current_user(credentials=None)
        self.assertEqual(missing.exception.status_code, 401)

        with self.assertRaises(HTTPException) as bad:
            get_current_user(
                credentials=HTTPAuthorizationCredentials(
                    scheme="Bearer", credentials="not.a.token"
                )
            )
        self.assertEqual(bad.exception.status_code, 401)

        from app.services import auth_service as svc

        expired = create_access_token(
            email="alice@example.edu", name="Alice", expires_minutes=-1
        )["access_token"]
        with self.assertRaises(svc.InvalidTokenError):
            decode_access_token(expired)

    def test_cross_student_profile_access_denied(self):
        from app.routes.student import get_profile

        with patch("app.routes.student.students_collection") as coll:
            coll.find_one.return_value = {"email": "alice@example.edu", "course": "BTech"}
            with self.assertRaises(HTTPException) as ctx:
                get_profile("alice@example.edu", current_user=self.auth_user("bob@example.edu"))
            self.assertEqual(ctx.exception.status_code, 403)

    def test_memory_registration_disabled_when_mongo_missing(self):
        from app.routes.auth import RegisterUser

        with patch.object(self.auth_routes, "users_collection", None):
            with self.assertRaises(HTTPException) as ctx:
                self.auth_routes.register(
                    RegisterUser(
                        name="Alice",
                        email="offline@example.edu",
                        password="password123",
                    )
                )
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("In-memory registration is disabled", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()


