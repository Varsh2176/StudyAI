from datetime import datetime, timedelta
from typing import List, Dict, Any


def calculate_subject_weights(subjects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Computes deterministic weight and priority score for each subject based on:
    - Subject difficulty (Low: 1.0, Medium: 1.35, High: 1.7)
    - Performance gap (Target score - Current score)
    - Exam urgency (Days remaining until exam date)
    """
    now = datetime.now()
    weighted_subjects = []

    difficulty_map = {
        "low": 1.0,
        "medium": 1.35,
        "high": 1.7
    }

    for subj in subjects:
        name = subj.get("name", "Subject")
        diff_str = str(subj.get("difficulty", "Medium")).lower()
        diff_weight = difficulty_map.get(diff_str, 1.35)

        current = float(subj.get("current_score", 60.0))
        target = float(subj.get("target_score", 85.0))
        score_gap = max(5.0, target - current)
        gap_factor = min(2.5, max(0.5, score_gap / 20.0))

        exam_date_str = subj.get("exam_date")
        urgency_factor = 1.0
        days_left = None

        if exam_date_str:
            try:
                exam_dt = datetime.strptime(exam_date_str, "%Y-%m-%d")
                days_left = (exam_dt.date() - now.date()).days
                if days_left <= 2:
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

        weighted_subjects.append({
            "name": name,
            "difficulty": subj.get("difficulty", "Medium"),
            "current_score": current,
            "target_score": target,
            "exam_date": exam_date_str,
            "days_left": days_left,
            "priority_score": round(raw_score, 3)
        })

    # Normalize priorities so they sum to 100%
    total_priority = sum(s["priority_score"] for s in weighted_subjects) or 1.0
    for s in weighted_subjects:
        s["allocated_ratio"] = round(s["priority_score"] / total_priority, 4)

    return sorted(weighted_subjects, key=lambda x: x["priority_score"], reverse=True)


def generate_study_plan(
    subjects: List[Dict[str, Any]],
    daily_study_hours: float = 4.0,
    preferred_start_time: str = "09:00",
    days_to_plan: int = 7
) -> Dict[str, Any]:
    """
    Generates deterministic daily and weekly study schedules with structured
    study blocks (50m study + 10m break), subject allocation, and daily limits.
    """
    # Enforce safe bounds on study hours (max 10 hrs/day to prevent burnout)
    safe_daily_hours = min(10.0, max(1.0, float(daily_study_hours)))
    weighted_subjects = calculate_subject_weights(subjects)

    if not weighted_subjects:
        return {
            "summary": "No subjects provided.",
            "daily_plan": [],
            "weekly_plan": {}
        }

    # Number of 1-hour slots (50 min study + 10 min break) per day
    num_slots_per_day = int(round(safe_daily_hours))
    if num_slots_per_day < 1:
        num_slots_per_day = 1

    try:
        start_hour, start_minute = map(int, preferred_start_time.split(":"))
    except Exception:
        start_hour, start_minute = 9, 0

    study_activities = [
        "Core Theory & Fundamentals",
        "Problem Solving & Practical Exercises",
        "Active Recall & Flashcards",
        "Formula Memorization & Mind-mapping",
        "Exam-Style Practice Questions",
        "Review & Weak-Spot Consolidation"
    ]

    weekly_plan = {}
    current_date = datetime.now()

    # Pre-calculate slot shares for subjects across the week
    total_slots_week = num_slots_per_day * days_to_plan
    subject_slot_queue = []

    for s in weighted_subjects:
        count = max(1, int(round(s["allocated_ratio"] * total_slots_week)))
        subject_slot_queue.extend([s["name"]] * count)

    # Pad or trim queue to fit total slots
    while len(subject_slot_queue) < total_slots_week:
        subject_slot_queue.append(weighted_subjects[0]["name"])
    subject_slot_queue = subject_slot_queue[:total_slots_week]

    # Distribute subjects smoothly across days
    slot_idx = 0
    for day_offset in range(days_to_plan):
        plan_day = current_date + timedelta(days=day_offset)
        day_key = plan_day.strftime("%A (%Y-%m-%d)")
        
        day_slots = []
        slot_time = datetime(
            plan_day.year, plan_day.month, plan_day.day,
            start_hour, start_minute
        )

        for s_idx in range(num_slots_per_day):
            subject_name = subject_slot_queue[slot_idx % len(subject_slot_queue)]
            slot_idx += 1

            study_start = slot_time.strftime("%H:%M")
            study_end = (slot_time + timedelta(minutes=50)).strftime("%H:%M")
            break_end = (slot_time + timedelta(minutes=60)).strftime("%H:%M")

            activity = study_activities[(day_offset + s_idx) % len(study_activities)]

            day_slots.append({
                "slot_id": f"day_{day_offset + 1}_slot_{s_idx + 1}",
                "start_time": study_start,
                "end_time": study_end,
                "break_time": f"{study_end} - {break_end} (10 min rest)",
                "subject": subject_name,
                "recommended_focus": activity,
                "completed": False
            })

            slot_time += timedelta(minutes=60)

        weekly_plan[day_key] = day_slots

    first_day_key = list(weekly_plan.keys())[0] if weekly_plan else "Today"
    daily_schedule = weekly_plan.get(first_day_key, [])

    return {
        "daily_study_hours": safe_daily_hours,
        "days_planned": days_to_plan,
        "subjects_weighted": weighted_subjects,
        "daily_schedule": daily_schedule,
        "weekly_schedule": weekly_plan,
        "notes": "Plan generated using deterministic difficulty-gap-urgency weighting and Pomodoro intervals (50m study / 10m break)."
    }
