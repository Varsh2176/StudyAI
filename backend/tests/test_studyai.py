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
    StudyPlanResponse
)
from app.routes.prediction import predict_score_endpoint
from app.routes.study_plan import (
    recommend_study_hours_endpoint,
    generate_plan_endpoint,
    generate_timetable_endpoint
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
from app.main import app, health


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
        res = predict_score_endpoint(req)

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
        res = predict_score_endpoint(req)

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
        res = predict_score_endpoint(req)

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
                predict_score_endpoint(req)
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
        res = recommend_study_hours_endpoint(req)
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
        res = recommend_study_hours_endpoint(req)
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
        res = recommend_study_hours_endpoint(req)
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
        res = recommend_study_hours_endpoint(req)
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
        res = recommend_study_hours_endpoint(req)
        self.assertTrue(res["burnout_guardrail_applied"])
        self.assertLessEqual(res["recommended_daily_hours"], 4.0)
        self.assertLessEqual(res["recommended_weekly_hours"], 28.0)


class TestPreservedBackendRoutes(unittest.TestCase):
    def test_registered_route_paths(self):
        paths = list(app.openapi()["paths"].keys())
        self.assertIn("/auth/register", paths)
        self.assertIn("/student/profile", paths)
        self.assertIn("/student/{email}", paths)
        self.assertIn("/predict/exam-score", paths)
        self.assertIn("/predict/model-status", paths)
        self.assertIn("/study-plan/generate", paths)
        self.assertIn("/study-plan/timetable", paths)
        self.assertIn("/study-plan/recommend-hours", paths)
        self.assertIn("/health", paths)

    def test_health_check(self):
        res = health()
        self.assertEqual(res["status"], "healthy")
        self.assertIn("ml_model", res)
        self.assertTrue(res["ml_model"]["loaded"])
        self.assertEqual(res["ml_model"]["algorithm"], "RidgeRegression")


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
        res_gen = generate_plan_endpoint(req)
        self.assertIn("timetable", res_gen)
        self.assertIn("subject_allocations", res_gen)
        self.assertIn("daily_schedule", res_gen)
        self.assertIn("weekly_schedule", res_gen)
        self.assertIn("summary", res_gen)
        self.assertEqual(len(res_gen["timetable"]), 3)
        self.assertEqual(res_gen["timetable"][0]["start_time"], "08:30")

        # 2. Test POST /study-plan/timetable
        res_tt = generate_timetable_endpoint(req)
        self.assertEqual(res_tt["timetable"], res_gen["timetable"])
        self.assertEqual(res_tt["total_scheduled_study_hours"], res_gen["total_scheduled_study_hours"])


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


if __name__ == "__main__":
    unittest.main()
