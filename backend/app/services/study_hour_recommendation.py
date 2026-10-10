"""
Study-Hour Recommendation Service for StudyWise AI (Milestone 10).

This module computes deterministic, explainable, and bounded study-hour recommendations
based on:
1. Student's available study time
2. Subject-wise difficulty weights
3. Performance gaps (Target Score vs. Current Score)
4. Upcoming exam deadlines (urgency)
5. Academic risk classification (Low / Moderate / High Risk)
6. Strict burnout guardrails and reasonable daily limits (default max 8 hrs/day)

IMPORTANT ARCHITECTURAL DISTINCTION:
- The ML model (Ridge Regression) predicts expected Exam_Score from student features.
- The Study-Hour Recommendation service is a prescriptive heuristic engine.
- The dataset does NOT directly predict optimal study hours.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class RecommendationConfig:
    """Configurable parameters for the study-hour recommendation algorithm."""
    base_hours_per_subject_weekly: float = 2.5   # Base maintenance hours per subject per week
    hours_per_score_gap_point: float = 0.15       # Extra weekly hours per point of target-current deficit
    diff_multiplier_low: float = 0.85
    diff_multiplier_medium: float = 1.00
    diff_multiplier_high: float = 1.35
    risk_multiplier_low: float = 1.00             # On-track pacing
    risk_multiplier_moderate: float = 1.15        # +15% study intensity
    risk_multiplier_high: float = 1.30            # +30% intensive remedial allocation
    default_max_daily_limit: float = 8.0          # Hard daily cap to prevent burnout
    min_daily_limit: float = 1.0                  # Minimum viable daily study time


DEFAULT_CONFIG = RecommendationConfig()


def calculate_study_hour_recommendation(
    daily_available_hours: float,
    subjects: List[Dict[str, Any]],
    risk_category: Optional[str] = None,
    max_daily_limit: Optional[float] = None,
    config: Optional[RecommendationConfig] = None
) -> Dict[str, Any]:
    """
    Computes personalized daily and weekly study hours for the student and per subject.
    """
    cfg = config or DEFAULT_CONFIG
    daily_cap = min(12.0, max(2.0, float(max_daily_limit if max_daily_limit is not None else cfg.default_max_daily_limit)))
    
    # Validate available hours
    if daily_available_hours <= 0:
        raise ValueError("Available daily study hours must be greater than zero.")
    if daily_available_hours > 24:
        raise ValueError("Available daily study hours cannot exceed 24 hours.")

    if not subjects:
        raise ValueError("At least one subject must be provided for study hour recommendation.")

    now = datetime.now()
    normalized_risk = (risk_category or "Low Risk").strip().title()
    if "Moderate" in normalized_risk or "Medium" in normalized_risk:
        risk_mult = cfg.risk_multiplier_moderate
        risk_label = "Moderate Risk"
    elif "High" in normalized_risk:
        risk_mult = cfg.risk_multiplier_high
        risk_label = "High Risk"
    else:
        risk_mult = cfg.risk_multiplier_low
        risk_label = "Low Risk"

    diff_map = {
        "low": cfg.diff_multiplier_low,
        "medium": cfg.diff_multiplier_medium,
        "high": cfg.diff_multiplier_high
    }

    subject_demands = []
    total_raw_demand = 0.0

    for s in subjects:
        name = s.get("name", "Subject").strip()
        if not name:
            name = "Unnamed Subject"

        diff_str = str(s.get("difficulty", "Medium")).lower()
        diff_weight = diff_map.get(diff_str, cfg.diff_multiplier_medium)

        current = float(s.get("current_score", 60.0))
        target = float(s.get("target_score", 85.0))
        if current < 0 or current > 100:
            raise ValueError(f"Current score for {name} must be between 0 and 100, got {current}")
        if target < 0 or target > 100:
            raise ValueError(f"Target score for {name} must be between 0 and 100, got {target}")

        score_gap = max(0.0, target - current)
        # Maintenance gap for already mastered subjects
        effective_gap = max(4.0, score_gap)

        # Urgency multiplier if exam date is set
        urgency_mult = 1.0
        exam_date_str = s.get("exam_date")
        if exam_date_str:
            try:
                exam_dt = datetime.strptime(str(exam_date_str), "%Y-%m-%d")
                days_left = (exam_dt.date() - now.date()).days
                if days_left <= 3:
                    urgency_mult = 1.35
                elif days_left <= 7:
                    urgency_mult = 1.20
                elif days_left <= 14:
                    urgency_mult = 1.10
            except ValueError:
                pass

        # Raw hours demand for this subject
        raw_hours = (cfg.base_hours_per_subject_weekly + (effective_gap * cfg.hours_per_score_gap_point)) * diff_weight * urgency_mult
        raw_hours = round(raw_hours * risk_mult, 2)

        subject_demands.append({
            "name": name,
            "difficulty": s.get("difficulty", "Medium").title(),
            "current_score": current,
            "target_score": target,
            "score_gap": round(score_gap, 1),
            "raw_hours": raw_hours
        })
        total_raw_demand += raw_hours

    # Available total hours per week
    available_weekly = daily_available_hours * 7.0
    cap_weekly = daily_cap * 7.0

    # Determine recommended weekly hours
    # Student cannot study more than their available time or the burnout cap
    burnout_applied = False
    time_constrained = False

    if total_raw_demand > cap_weekly:
        recommended_weekly = cap_weekly
        burnout_applied = True
    elif total_raw_demand > available_weekly:
        recommended_weekly = available_weekly
        time_constrained = True
    else:
        # Minimum baseline is either the raw demand or at least 1 hr/day if available
        recommended_weekly = max(cfg.min_daily_limit * 7.0, total_raw_demand)
        recommended_weekly = min(recommended_weekly, available_weekly, cap_weekly)

    recommended_weekly = round(recommended_weekly, 1)
    recommended_daily = round(recommended_weekly / 7.0, 1)

    # Subject-wise breakdown proportional to raw demand
    breakdown = []
    for sd in subject_demands:
        ratio = (sd["raw_hours"] / total_raw_demand) if total_raw_demand > 0 else (1.0 / len(subject_demands))
        subj_weekly = round(recommended_weekly * ratio, 1)
        subj_daily = round(subj_weekly / 7.0, 1)

        priority = "Standard"
        if sd["score_gap"] >= 20 or sd["difficulty"] == "High":
            priority = "High Priority"
        elif sd["score_gap"] <= 5 and sd["difficulty"] == "Low":
            priority = "Maintenance"

        breakdown.append({
            "subject": sd["name"],
            "difficulty": sd["difficulty"],
            "score_gap": sd["score_gap"],
            "weekly_hours": subj_weekly,
            "daily_hours": subj_daily,
            "percentage_share": round(ratio * 100, 1),
            "focus_priority": priority
        })

    # Explanation construction
    explanation_parts = [
        f"Recommended study commitment is {recommended_daily} hrs/day ({recommended_weekly} hrs/week) across {len(subjects)} subject(s)."
    ]
    if risk_label != "Low Risk":
        explanation_parts.append(
            f"An intensity factor of {int((risk_mult - 1.0) * 100)}% was incorporated based on your '{risk_label}' standing to remediate foundational deficits."
        )
    if burnout_applied:
        explanation_parts.append(
            f"Daily study ceiling guardrail ({daily_cap} hrs/day) applied to prevent cognitive fatigue and burnout."
        )
    elif time_constrained:
        explanation_parts.append(
            f"Recommendation fits within your declared availability ({daily_available_hours} hrs/day), prioritizing high-deficit subjects."
        )
    else:
        explanation_parts.append(
            "Pacing provides sufficient coverage to bridge your academic target gaps comfortably."
        )

    concise_explanation = " ".join(explanation_parts)

    return {
        "recommended_weekly_hours": recommended_weekly,
        "recommended_daily_hours": recommended_daily,
        "available_daily_hours": daily_available_hours,
        "max_daily_limit": daily_cap,
        "risk_category_applied": risk_label,
        "burnout_guardrail_applied": burnout_applied,
        "subject_breakdown": breakdown,
        "concise_explanation": concise_explanation,
        "methodology_notes": (
            "Study hours are determined via a deterministic optimization model combining subject difficulty, "
            "score deficit (Target - Current), urgency, and risk multiplier, strictly bounded by declared availability "
            f"and a maximum burnout guardrail of {daily_cap} hrs/day."
        ),
        "disclaimer": (
            "This study-hour allocation is an advisory planning recommendation. The ML model predicts exam scores, "
            "not study-hour targets. Study hours should be balanced with adequate sleep and personal well-being."
        )
    }

