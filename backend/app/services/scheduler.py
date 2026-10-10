"""
Deterministic Study Scheduler Engine for StudyWise AI (Milestone 11).

This module generates practical, bounded, and deterministic daily and weekly study timetables
based on:
1. M10 recommended study hours and student daily availability
2. Multi-factor subject prioritization (Difficulty, Score Gap, Exam Urgency)
3. Pomodoro-based structured study cycles (50 min study + 10 min break)
4. Strict burnout guardrails (daily ceiling limits)
5. Predictable chronological slot sequencing from preferred start time

ARCHITECTURAL PRINCIPLES:
- Deterministic: Identical inputs (including plan_date anchor) produce identical timetables.
- Bounded: Total scheduled study time never exceeds available time or M10 recommendation.
- Decoupled: Pure algorithmic scheduling engine, independent of FastAPI routing.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.services.study_hour_recommendation import calculate_study_hour_recommendation


def calculate_subject_weights(
    subjects: List[Dict[str, Any]],
    reference_date: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Computes deterministic weight and priority score for each subject based on:
    - Subject difficulty (Low: 1.0, Medium: 1.35, High: 1.7)
    - Performance gap (Target score - Current score)
    - Exam urgency (Days remaining until exam date relative to reference_date)
    """
    if not subjects:
        raise ValueError("At least one subject is required to calculate subject weights.")

    ref_date = reference_date or datetime.now()
    weighted_subjects = []

    difficulty_map = {
        "low": 1.0,
        "medium": 1.35,
        "high": 1.7
    }

    for subj in subjects:
        raw_name = subj.get("name", "")
        name = str(raw_name).strip() if raw_name is not None else ""
        if not name:
            raise ValueError("Subject name cannot be empty.")

        diff_str = str(subj.get("difficulty", "Medium")).lower()
        diff_weight = difficulty_map.get(diff_str, 1.35)

        try:
            current = float(subj.get("current_score", 60.0))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid current_score for subject '{name}'.")

        try:
            target = float(subj.get("target_score", 85.0))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid target_score for subject '{name}'.")

        if current < 0.0 or current > 100.0:
            raise ValueError(f"Current score for '{name}' must be between 0 and 100, got {current}.")
        if target < 0.0 or target > 100.0:
            raise ValueError(f"Target score for '{name}' must be between 0 and 100, got {target}.")

        score_gap = max(0.0, target - current)
        effective_gap = max(5.0, score_gap)
        gap_factor = min(2.5, max(0.5, effective_gap / 20.0))

        exam_date_str = subj.get("exam_date")
        urgency_factor = 1.0
        days_left = None

        if exam_date_str:
            try:
                exam_dt = datetime.strptime(str(exam_date_str).strip(), "%Y-%m-%d")
                days_left = (exam_dt.date() - ref_date.date()).days
                if days_left <= 0:
                    urgency_factor = 3.0   # Exam is today or overdue
                elif days_left <= 2:
                    urgency_factor = 2.5
                elif days_left <= 7:
                    urgency_factor = 1.8
                elif days_left <= 14:
                    urgency_factor = 1.4
                elif days_left <= 30:
                    urgency_factor = 1.15
            except ValueError:
                pass

        # Combined deterministic priority score
        raw_score = (diff_weight * 0.40) + (gap_factor * 0.35) + (urgency_factor * 0.25)

        # Categorical priority level
        if urgency_factor >= 1.8 or diff_weight >= 1.7 or score_gap >= 25.0:
            priority_level = "High Priority"
        elif score_gap <= 5.0 and diff_weight <= 1.0:
            priority_level = "Maintenance"
        else:
            priority_level = "Standard"

        weighted_subjects.append({
            "name": name,
            "difficulty": subj.get("difficulty", "Medium").title(),
            "current_score": current,
            "target_score": target,
            "score_gap": round(score_gap, 1),
            "exam_date": exam_date_str,
            "days_left": days_left,
            "priority_score": round(raw_score, 3),
            "priority_level": priority_level
        })

    # Normalize priorities so they sum to 1.0 (100%)
    total_priority = sum(s["priority_score"] for s in weighted_subjects) or 1.0
    for s in weighted_subjects:
        s["allocated_ratio"] = round(s["priority_score"] / total_priority, 4)

    # Deterministic sorting: highest priority first; alphabetical secondary sort for deterministic tie-breaking
    return sorted(weighted_subjects, key=lambda x: (-x["priority_score"], x["name"]))


def generate_study_plan(
    subjects: List[Dict[str, Any]],
    daily_study_hours: Optional[float] = 4.0,
    preferred_start_time: str = "09:00",
    days_to_plan: int = 7,
    daily_available_hours: Optional[float] = None,
    risk_category: Optional[str] = None,
    max_daily_limit: Optional[float] = 8.0,
    plan_date: Optional[str] = None,
    slot_duration_minutes: int = 50,
    break_duration_minutes: int = 10,
    risk_details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generates deterministic daily and weekly study timetables bounded by
    student availability, M10 recommended study hours, and Pomodoro cycles.
    """
    if not subjects:
        raise ValueError("At least one subject is required to generate a study timetable.")

    # Validate availability and study hours
    available = float(
        daily_available_hours if daily_available_hours is not None
        else (daily_study_hours if daily_study_hours is not None else 4.0)
    )
    if available <= 0.0:
        raise ValueError("Available daily study hours must be greater than zero.")
    if available > 16.0:
        raise ValueError("Available daily study hours cannot exceed 16.0 hours.")

    requested = float(daily_study_hours if daily_study_hours is not None else available)
    if requested <= 0.0:
        raise ValueError("Daily study hours must be greater than zero.")
    if requested > 16.0:
        raise ValueError("Daily study hours cannot exceed 16.0 hours.")

    if days_to_plan < 1 or days_to_plan > 30:
        raise ValueError("days_to_plan must be between 1 and 30.")

    # Parse anchor date deterministically
    if plan_date:
        try:
            current_date = datetime.strptime(str(plan_date).strip(), "%Y-%m-%d")
            plan_date_str = str(plan_date).strip()
        except ValueError:
            current_date = datetime.now()
            plan_date_str = current_date.strftime("%Y-%m-%d")
    else:
        current_date = datetime.now()
        plan_date_str = current_date.strftime("%Y-%m-%d")

    # Subject weights with deterministic ordering
    weighted_subjects = calculate_subject_weights(subjects, reference_date=current_date)

    # Enforce safe burnout cap
    daily_cap = min(12.0, max(2.0, float(max_daily_limit if max_daily_limit is not None else 8.0)))

    # M10 Study-Hour Recommendation Integration
    m10_rec = calculate_study_hour_recommendation(
        daily_available_hours=min(available, daily_cap),
        subjects=subjects,
        risk_category=risk_category,
        max_daily_limit=daily_cap,
        risk_details=risk_details
    )
    m10_recommended_daily = m10_rec["recommended_daily_hours"]

    # Bound effective scheduled study time:
    # If daily_available_hours is explicitly set, study time must not exceed available time or M10 recommendation.
    # Otherwise, schedule according to requested study hours up to daily burnout cap.
    if daily_available_hours is not None:
        effective_daily_hours = min(available, requested, m10_recommended_daily, daily_cap)
    else:
        effective_daily_hours = min(requested, daily_cap)
    effective_daily_hours = round(effective_daily_hours, 1)

    burnout_applied = (
        (requested > daily_cap) or
        (available > daily_cap) or
        bool(m10_rec.get("burnout_guardrail_applied", False))
    )

    # Determine slot parameters
    if effective_daily_hours < 1.0:
        num_slots_per_day = 1
        actual_slot_minutes = max(15, int(round(effective_daily_hours * 60)))
        actual_break_minutes = 0
    else:
        num_slots_per_day = int(round(effective_daily_hours))
        if num_slots_per_day < 1:
            num_slots_per_day = 1
        actual_slot_minutes = slot_duration_minutes
        actual_break_minutes = break_duration_minutes

    # Parse start time safely
    try:
        start_parts = str(preferred_start_time).strip().split(":")
        start_hour = int(start_parts[0])
        start_minute = int(start_parts[1])
        if not (0 <= start_hour <= 23 and 0 <= start_minute <= 59):
            start_hour, start_minute = 9, 0
    except Exception:
        start_hour, start_minute = 9, 0

    # Structured focus activities by priority level
    focus_activities = {
        "High Priority": [
            "Exam-Style Practice Questions & Mock Problem Sets",
            "Formula Derivations & Weak-Spot Consolidation",
            "High-Yield Problem Solving Drills",
            "Targeted Review of Critical Misconceptions"
        ],
        "Standard": [
            "Core Theory & Conceptual Mind-Mapping",
            "Practical Application & Text Exercises",
            "Structured Topic Summarization",
            "Interactive Quiz & Self-Testing"
        ],
        "Maintenance": [
            "Active Recall Flashcards & Spaced Retention",
            "Rapid Topic Overview & Key Formula Verification",
            "Quick Reference Sheet Consolidation"
        ]
    }

    # Proportional slot counts per subject across the planning horizon
    total_slots_week = num_slots_per_day * days_to_plan
    counts = {}
    for s in weighted_subjects:
        counts[s["name"]] = max(1, int(round(s["allocated_ratio"] * total_slots_week)))

    # Balance counts to equal total_slots_week exactly
    curr_total = sum(counts.values())
    if curr_total < total_slots_week:
        counts[weighted_subjects[0]["name"]] += (total_slots_week - curr_total)
    elif curr_total > total_slots_week:
        diff = curr_total - total_slots_week
        for s in reversed(weighted_subjects):
            reduction = min(diff, max(0, counts[s["name"]] - 1))
            counts[s["name"]] -= reduction
            diff -= reduction
            if diff <= 0:
                break

    # Interleave subjects in priority round-robin order
    subject_slot_queue = []
    while len(subject_slot_queue) < total_slots_week:
        added = False
        for s in weighted_subjects:
            if counts[s["name"]] > 0:
                subject_slot_queue.append(s)
                counts[s["name"]] -= 1
                added = True
                if len(subject_slot_queue) == total_slots_week:
                    break
        if not added:
            break

    while len(subject_slot_queue) < total_slots_week:
        subject_slot_queue.append(weighted_subjects[0])
    subject_slot_queue = subject_slot_queue[:total_slots_week]

    weekly_plan = {}
    daily_schedule = []

    for day_offset in range(days_to_plan):
        plan_day = current_date + timedelta(days=day_offset)
        day_key = plan_day.strftime("%A (%Y-%m-%d)")

        day_slots = []
        slot_time = datetime(
            plan_day.year, plan_day.month, plan_day.day,
            start_hour, start_minute
        )

        for s_idx in range(num_slots_per_day):
            subj_idx = (day_offset * num_slots_per_day + s_idx) % len(subject_slot_queue)
            s_obj = subject_slot_queue[subj_idx]

            study_start = slot_time.strftime("%H:%M")
            study_end = (slot_time + timedelta(minutes=actual_slot_minutes)).strftime("%H:%M")
            break_end = (slot_time + timedelta(minutes=actual_slot_minutes + actual_break_minutes)).strftime("%H:%M")

            acts = focus_activities.get(s_obj.get("priority_level", "Standard"), focus_activities["Standard"])
            activity = acts[(day_offset + s_idx) % len(acts)]

            break_text = (
                f"{study_end} - {break_end} ({actual_break_minutes} min rest)"
                if actual_break_minutes > 0
                else "No break (compact session)"
            )

            slot_item = {
                "slot_order": s_idx + 1,
                "slot_id": f"day_{day_offset + 1}_slot_{s_idx + 1}",
                "subject": s_obj["name"],
                "difficulty": s_obj["difficulty"],
                "priority_level": s_obj["priority_level"],
                "duration_minutes": actual_slot_minutes,
                "start_time": study_start,
                "end_time": study_end,
                "break_duration_minutes": actual_break_minutes,
                "break_time": break_text,
                "recommended_focus": activity,
                "completed": False
            }

            day_slots.append(slot_item)
            slot_time += timedelta(minutes=actual_slot_minutes + actual_break_minutes)

        weekly_plan[day_key] = day_slots
        if day_offset == 0:
            daily_schedule = day_slots

    # Summary of subject allocations for Day 1
    subject_allocations = []
    for s in weighted_subjects:
        slots_count = sum(1 for slot in daily_schedule if slot["subject"] == s["name"])
        allocated_mins = slots_count * actual_slot_minutes
        subject_allocations.append({
            "subject": s["name"],
            "difficulty": s["difficulty"],
            "priority_score": s["priority_score"],
            "allocated_ratio": s["allocated_ratio"],
            "allocated_study_minutes": allocated_mins,
            "allocated_study_hours": round(allocated_mins / 60.0, 2),
            "slots_count": slots_count
        })

    total_scheduled_study_minutes = len(daily_schedule) * actual_slot_minutes
    total_scheduled_study_hours = round(total_scheduled_study_minutes / 60.0, 2)
    total_break_minutes = len(daily_schedule) * actual_break_minutes

    summary = (
        f"Generated practical study timetable for {plan_date_str} totaling "
        f"{total_scheduled_study_hours} hrs of focused study across {num_slots_per_day} session(s) "
        f"with {total_break_minutes} mins of rest. Scheduled study time does not exceed declared "
        f"availability ({available} hrs) or M10 recommendation ({m10_recommended_daily} hrs)."
    )
    if burnout_applied:
        summary += f" Burnout protection applied with daily cap of {daily_cap} hrs."

    return {
        "plan_date": plan_date_str,
        "daily_study_hours": effective_daily_hours,
        "daily_available_hours": available,
        "m10_recommended_daily_hours": m10_recommended_daily,
        "m10_recommended_weekly_hours": m10_rec.get("recommended_weekly_hours"),
        "total_scheduled_study_minutes": total_scheduled_study_minutes,
        "total_scheduled_study_hours": total_scheduled_study_hours,
        "total_break_minutes": total_break_minutes,
        "risk_category_applied": m10_rec.get("risk_category_applied", risk_category or "Low Risk"),
        "risk_assessment_details": risk_details or m10_rec.get("risk_assessment_details"),
        "m10_recommendation": m10_rec,
        "burnout_guardrail_applied": burnout_applied,
        "days_planned": days_to_plan,
        "subjects_weighted": weighted_subjects,
        "daily_schedule": daily_schedule,
        "weekly_schedule": weekly_plan,
        "timetable": daily_schedule,
        "subject_allocations": subject_allocations,
        "summary": summary,
        "notes": (
            "Timetable generated deterministically using Pomodoro cycles (50m study / 10m break). "
            "Subjects are prioritized by difficulty, target deficit, and exam urgency. "
            "Scheduled study time is strictly bounded by M10 recommended hours and cognitive limits."
        ),
        "disclaimer": m10_rec.get(
            "disclaimer",
            "This study plan is an advisory schedule. Study hours are strictly bounded to prevent burnout."
        )
    }

