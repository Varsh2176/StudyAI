"""
Risk Classification Service for StudyWise AI.

This module provides a transparent, configurable, rule-based academic risk indicator.
Because the Kaggle StudentPerformanceFactors dataset contains continuous exam outcomes
rather than pre-existing risk labels, supervised risk classification would require
artificial label fabrication. This service avoids outcome data leakage by evaluating
only pre-exam observable academic indicators and predicted trajectory.

DISCLAIMER & LIMITATIONS:
This risk classification is an explainable heuristic tool to assist in study planning.
It is NOT a clinically or scientifically validated risk diagnosis.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class RiskThresholds:
    """Configurable thresholds for academic risk indicator calculations."""
    attendance_critical: float = 65.0      # Below 65% is critical attendance
    attendance_borderline: float = 75.0    # 65% to < 75% is marginal attendance
    study_hours_critical: float = 10.0     # Below 10 hrs/week is critical study deficit
    study_hours_borderline: float = 16.0   # 10 to < 16 hrs/week is moderate study effort
    previous_scores_critical: float = 55.0 # Below 55% prior score is critical academic deficit
    previous_scores_borderline: float = 70.0 # 55% to < 70% prior score is borderline
    predicted_score_critical: float = 60.0 # Below 60% predicted score is below passing standard
    predicted_score_borderline: float = 70.0 # 60% to < 70% predicted score is marginal pass
    high_risk_cutoff: int = 4             # >= 4 risk points -> High Risk
    moderate_risk_cutoff: int = 2         # >= 2 risk points -> Moderate Risk


DEFAULT_THRESHOLDS = RiskThresholds()


def evaluate_academic_risk(
    attendance: float,
    hours_studied: float,
    previous_scores: float,
    predicted_score: float,
    access_to_resources: str = "Medium",
    learning_disabilities: str = "No",
    tutoring_sessions: int = 0,
    thresholds: Optional[RiskThresholds] = None
) -> Dict[str, Any]:
    """
    Evaluates multi-factor academic risk using transparent heuristics.
    
    Returns:
    - risk_category: "Low Risk" | "Moderate Risk" | "High Risk"
    - risk_score: total accumulated risk points
    - relevant_indicators: list of specific indicator findings
    - concise_explanation: student-facing summary
    - recommended_interventions: actionable recommendations
    - disclaimer: explicit methodological boundary notice
    """
    cfg = thresholds or DEFAULT_THRESHOLDS

    # Validate numeric inputs
    if attendance < 0.0 or attendance > 100.0:
        raise ValueError(f"Attendance must be between 0 and 100, got {attendance}")
    if hours_studied < 0.0:
        raise ValueError(f"Hours_Studied cannot be negative, got {hours_studied}")
    if previous_scores < 0.0 or previous_scores > 100.0:
        raise ValueError(f"Previous_Scores must be between 0 and 100, got {previous_scores}")

    points = 0
    indicators: List[Dict[str, Any]] = []
    interventions: List[str] = []

    # 1. Attendance Check
    if attendance < cfg.attendance_critical:
        points += 3
        indicators.append({
            "indicator": "Attendance",
            "value": f"{attendance:.1f}%",
            "severity": "Critical",
            "message": f"Attendance ({attendance:.1f}%) is critically low (< {cfg.attendance_critical}%)."
        })
        interventions.append("Attend mandatory remedial lectures and consult academic advisors to rectify attendance deficit.")
    elif attendance < cfg.attendance_borderline:
        points += 1
        indicators.append({
            "indicator": "Attendance",
            "value": f"{attendance:.1f}%",
            "severity": "Borderline",
            "message": f"Attendance ({attendance:.1f}%) is below optimal threshold ({cfg.attendance_borderline}%)."
        })
        interventions.append("Prioritize attending all remaining classes to avoid falling below attendance prerequisites.")

    # 2. Study Hours Check
    if hours_studied < cfg.study_hours_critical:
        points += 2
        indicators.append({
            "indicator": "Hours_Studied",
            "value": f"{hours_studied:.1f} hrs/week",
            "severity": "Critical",
            "message": f"Weekly study time ({hours_studied:.1f} hrs) is significantly below recommended minimum ({cfg.study_hours_critical} hrs)."
        })
        interventions.append(f"Increase dedicated study allocation by at least {int(cfg.study_hours_critical - hours_studied + 4)} hours per week.")
    elif hours_studied < cfg.study_hours_borderline:
        points += 1
        indicators.append({
            "indicator": "Hours_Studied",
            "value": f"{hours_studied:.1f} hrs/week",
            "severity": "Borderline",
            "message": f"Weekly study time ({hours_studied:.1f} hrs) is moderate; target is {cfg.study_hours_borderline} hrs."
        })
        interventions.append("Schedule 2 to 3 additional hours of structured revision during peak concentration periods.")

    # 3. Prior Academic Scores Check
    if previous_scores < cfg.previous_scores_critical:
        points += 3
        indicators.append({
            "indicator": "Previous_Scores",
            "value": f"{previous_scores:.1f}%",
            "severity": "Critical",
            "message": f"Previous exam performance ({previous_scores:.1f}%) indicates foundational concept gaps (< {cfg.previous_scores_critical}%)."
        })
        interventions.append("Schedule one-on-one peer tutoring and review previous examination problem sets.")
    elif previous_scores < cfg.previous_scores_borderline:
        points += 1
        indicators.append({
            "indicator": "Previous_Scores",
            "value": f"{previous_scores:.1f}%",
            "severity": "Borderline",
            "message": f"Previous exam performance ({previous_scores:.1f}%) is in borderline range (< {cfg.previous_scores_borderline}%)."
        })
        interventions.append("Focus on high-weight core concepts to strengthen foundational comprehension.")

    # 4. Model Projected Score Check
    if predicted_score < cfg.predicted_score_critical:
        points += 2
        indicators.append({
            "indicator": "Predicted_Score",
            "value": f"{predicted_score:.1f}",
            "severity": "Critical",
            "message": f"Projected score ({predicted_score:.1f}) is currently below the passing benchmark ({cfg.predicted_score_critical:.0f})."
        })
        interventions.append("Adopt an intensive study timetable prioritizing highest-weight examination topics.")
    elif predicted_score < cfg.predicted_score_borderline:
        points += 1
        indicators.append({
            "indicator": "Predicted_Score",
            "value": f"{predicted_score:.1f}",
            "severity": "Borderline",
            "message": f"Projected score ({predicted_score:.1f}) is marginal; target is > {cfg.predicted_score_borderline:.0f}."
        })

    # 5. Resource and Support Context
    if str(access_to_resources).lower() == "low":
        points += 1
        indicators.append({
            "indicator": "Access_to_Resources",
            "value": "Low",
            "severity": "Notice",
            "message": "Limited study resource access reported."
        })
        interventions.append("Utilize open digital textbook repositories and university library study notes.")

    if str(learning_disabilities).lower() == "yes" and tutoring_sessions == 0:
        points += 1
        indicators.append({
            "indicator": "Support_Services",
            "value": "No tutoring",
            "severity": "Notice",
            "message": "Learning accommodations needed without active tutoring support."
        })
        interventions.append("Engage campus academic accessibility center and enroll in regular tutoring sessions.")

    # Determine Category
    if points >= cfg.high_risk_cutoff:
        category = "High Risk"
        explanation = (
            f"High Risk (Risk Score: {points}): Substantial academic risk detected across "
            f"{len(indicators)} leading indicator(s). Immediate structured academic intervention recommended."
        )
    elif points >= cfg.moderate_risk_cutoff:
        category = "Moderate Risk"
        explanation = (
            f"Moderate Risk (Risk Score: {points}): Moderate vulnerability detected with "
            f"{len(indicators)} borderline indicator(s). Targeted revision and consistent routine advised."
        )
    else:
        category = "Low Risk"
        explanation = (
            f"Low Risk (Risk Score: {points}): Academic performance indicators and projected trajectory "
            "are currently on track. Maintain ongoing study habits and active recall."
        )
        if not interventions:
            interventions.append("Maintain current study schedule and incorporate weekly self-assessment quizzes.")

    # Format output with backward-compatibility for risk_level and risk_factors
    return {
        "risk_category": category,
        "risk_level": category,  # Backward compatible alias
        "risk_score": points,
        "relevant_indicators": indicators,
        "risk_factors": [ind["message"] for ind in indicators],  # Backward compatible alias
        "concise_explanation": explanation,
        "recommendation": explanation,  # Backward compatible alias
        "recommended_interventions": interventions,
        "configurable_thresholds_applied": {
            "attendance_critical": cfg.attendance_critical,
            "attendance_borderline": cfg.attendance_borderline,
            "study_hours_critical": cfg.study_hours_critical,
            "study_hours_borderline": cfg.study_hours_borderline,
            "previous_scores_critical": cfg.previous_scores_critical,
            "previous_scores_borderline": cfg.previous_scores_borderline,
            "predicted_score_critical": cfg.predicted_score_critical,
            "predicted_score_borderline": cfg.predicted_score_borderline,
            "high_risk_cutoff": cfg.high_risk_cutoff,
            "moderate_risk_cutoff": cfg.moderate_risk_cutoff
        },
        "disclaimer": (
            "Rule-based academic heuristic derived from observable engagement indicators. "
            "This is not a clinically or scientifically validated diagnostic prediction."
        )
    }

