from ortools.sat.python import cp_model


def get_default_block_availability():
    """Default availability by level for a six-day week."""
    return [
        [1, 0, 1, 0, 0, 1],
        [0, 1, 1, 1, 0, 1],
        [0, 1, 0, 1, 1, 1],
    ]


def get_default_labs_arrangement(no_of_blocks, no_of_labs, no_of_days):
    """Default lab layout with support for up to 7 days."""
    days_arrangement = [
        [[0, 1], [0, 0]],
        [[1, 1], [1, 1]],
        [[1, 1], [1, 1]],
        [[0, 0], [1, 0]],
        [[1, 1], [1, 1]],
        [[1, 1], [1, 1]],
        [[1, 1], [1, 1]],
    ]

    adapted_arrangement = []
    for day_idx in range(no_of_days):
        day = days_arrangement[day_idx] if day_idx < len(days_arrangement) else days_arrangement[-1]
        day_blocks = []
        for block_idx in range(no_of_blocks):
            if block_idx < len(day):
                block_labs = day[block_idx][:no_of_labs] + [0] * (no_of_labs - len(day[block_idx]))
            else:
                block_labs = [1] * no_of_labs
            day_blocks.append(block_labs)
        adapted_arrangement.append(day_blocks)
    return adapted_arrangement


def _normalize_bool(value):
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"1", "true", "yes", "y", "on"}
    if isinstance(value, (int, float)):
        return bool(int(value))
    return bool(value)


def _sort_key(value):
    text = str(value).strip()
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return (0, int(text))
    return (1, text.lower())


def _normalize_level_name(level_name):
    text = str(level_name or "").strip()
    aliases = {
        "senior": "Senior",
        "junior": "Junior",
        "accelerated": "Accelerated",
        "sr": "Senior",
        "jr": "Junior",
        "acc": "Accelerated",
    }
    key = text.lower()
    return aliases.get(key, text)


def _build_roster_from_csv(params):
    course_data = params.get("course_data") or []
    course_columns = params.get("course_columns") or []
    if not course_data or not course_columns:
        return None

    course_sessions = params.get("course_sessions") or [1] * len(course_columns)
    course_sessions = list(course_sessions[: len(course_columns)]) + [1] * max(0, len(course_columns) - len(course_sessions))

    level_sets = {}
    for row in course_data:
        level_value = None
        for candidate in ["Student_Level", "Level", "student_level", "level"]:
            if candidate in row and row[candidate] not in (None, ""):
                level_value = _normalize_level_name(row[candidate])
                break
        if level_value is None:
            level_value = "0"

        group_value = None
        for candidate in ["Group_Index", "Group", "group_index", "group"]:
            if candidate in row and row[candidate] not in (None, ""):
                group_value = str(row[candidate]).strip()
                break
        if group_value is None:
            group_value = "1"

        level_sets.setdefault(level_value, set()).add(group_value)

    level_priority = {"Senior": 0, "Junior": 1, "Accelerated": 2}
    ordered_levels = [
        level_name for level_name in ["Senior", "Junior", "Accelerated"] if level_name in level_sets
    ]
    remaining_levels = [
        level_name for level_name in sorted(level_sets.keys(), key=_sort_key)
        if level_name not in ordered_levels
    ]
    level_text = ordered_levels + remaining_levels
    group_counts = []
    student_data = []
    for level_name in level_text:
        groups = sorted(level_sets[level_name], key=_sort_key)
        group_counts.append(len(groups))
        level_rows = []
        for group_name in groups:
            enrolled = [0] * len(course_columns)
            for row in course_data:
                row_level = None
                for candidate in ["Student_Level", "Level", "student_level", "level"]:
                    if candidate in row and row[candidate] not in (None, ""):
                        row_level = _normalize_level_name(row[candidate])
                        break
                if row_level is None:
                    row_level = "0"

                row_group = None
                for candidate in ["Group_Index", "Group", "group_index", "group"]:
                    if candidate in row and row[candidate] not in (None, ""):
                        row_group = str(row[candidate]).strip()
                        break
                if row_group is None:
                    row_group = "1"

                if row_level != level_name or row_group != group_name:
                    continue

                for idx, course in enumerate(course_columns):
                    if course in row and _normalize_bool(row[course]):
                        enrolled[idx] = 1
            level_rows.append(enrolled)
        student_data.append(level_rows)

    return {
        "courses": course_columns,
        "course_sessions": [int(v) for v in course_sessions],
        "level_text": level_text,
        "no_of_groups_levelwise": group_counts,
        "student_data": student_data,
    }


def _solve_course_aware_model(params):
    roster = _build_roster_from_csv(params)
    if roster is None:
        raise ValueError("Course roster data is missing or incomplete.")

    no_of_weeks = params["no_of_weeks"]
    no_of_days = params["no_of_days"]
    no_of_blocks = params["no_of_blocks"]
    no_of_labs = params["no_of_labs"]

    block_availability = params["block_availability"]
    labs_arrangement = params["labs_arrangement"]
    objective_choice = params.get("objective", "Balanced Schedule Distribution")
    user_preference_weights = params.get("preference_weights")

    if objective_choice == "Preference Weighted Scheduling" and user_preference_weights:
        preference_list = list(user_preference_weights)
        if len(preference_list) < no_of_weeks:
            preference_list += [preference_list[-1]] * (no_of_weeks - len(preference_list))
    else:
        preference_list = [1] * no_of_weeks

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][:no_of_days]
    courses = roster["courses"]
    course_sessions = roster["course_sessions"]
    level_text = roster["level_text"]
    no_of_level = len(level_text)
    student_data = roster["student_data"]
    no_of_groups_levelwise = roster["no_of_groups_levelwise"]

    canonical_level_names = ["Senior", "Junior", "Accelerated"]
    available_days_by_name = {}
    for level_name in canonical_level_names:
        level_index = canonical_level_names.index(level_name)
        raw_days = block_availability[level_index] if level_index < len(block_availability) else [1] * no_of_days
        available_days_by_name[level_name] = list(raw_days[:no_of_days])

    for level_name in list(level_text):
        canonical_name = _normalize_level_name(level_name)
        if canonical_name in available_days_by_name:
            available_days_by_name[canonical_name] = available_days_by_name[canonical_name]

    allowed_days_by_level = {}
    for level_name in level_text:
        raw_days = available_days_by_name.get(level_name, [1] * no_of_days)
        allowed_days = {
            day_index for day_index, is_allowed in enumerate(raw_days[:no_of_days])
            if _normalize_bool(is_allowed)
        }
        allowed_days_by_level[level_name] = allowed_days

    model = cp_model.CpModel()
    assign = {}

    for level in range(no_of_level):
        for group in range(no_of_groups_levelwise[level]):
            for course in range(len(courses)):
                if student_data[level][group][course] != 1:
                    continue
                for week in range(no_of_weeks):
                    for day in range(no_of_days):
                        for block in range(no_of_blocks):
                            for lab in range(no_of_labs):
                                key = (level, group, course, week, day, block, lab)
                                assign[key] = model.NewBoolVar(
                                    f"X_L{level}_G{group}_C{course}_W{week}_D{day}_B{block}_Lab{lab}"
                                )

    for level in range(no_of_level):
        for group in range(no_of_groups_levelwise[level]):
            for course in range(len(courses)):
                if student_data[level][group][course] != 1:
                    continue
                session_vars = []
                for week in range(no_of_weeks):
                    for day in range(no_of_days):
                        for block in range(no_of_blocks):
                            for lab in range(no_of_labs):
                                key = (level, group, course, week, day, block, lab)
                                if key in assign:
                                    session_vars.append(assign[key])
                model.Add(sum(session_vars) == course_sessions[course])

    for level in range(no_of_level):
        for group in range(no_of_groups_levelwise[level]):
            for week in range(no_of_weeks):
                for day in range(no_of_days):
                    daily_vars = []
                    for course in range(len(courses)):
                        for block in range(no_of_blocks):
                            for lab in range(no_of_labs):
                                key = (level, group, course, week, day, block, lab)
                                if key in assign:
                                    daily_vars.append(assign[key])
                    if daily_vars:
                        model.Add(sum(daily_vars) <= 1)

    for level in range(no_of_level):
        level_name = level_text[level]
        allowed_days = allowed_days_by_level.get(level_name, set(range(no_of_days)))
        for group in range(no_of_groups_levelwise[level]):
            for course in range(len(courses)):
                if student_data[level][group][course] != 1:
                    continue

                forbidden_day_vars = []
                forbidden_lab_vars = []
                for week in range(no_of_weeks):
                    for day in range(no_of_days):
                        for block in range(no_of_blocks):
                            for lab in range(no_of_labs):
                                key = (level, group, course, week, day, block, lab)
                                if key in assign:
                                    x = assign[key]
                                    forbidden_day_vars.append(x * (1 - int(day in allowed_days)))
                                    forbidden_lab_vars.append(x * (1 - int(labs_arrangement[day][block][lab])))

                if forbidden_day_vars:
                    model.Add(sum(forbidden_day_vars) == 0)
                if forbidden_lab_vars:
                    model.Add(sum(forbidden_lab_vars) == 0)

    for week in range(no_of_weeks):
        for day in range(no_of_days):
            for block in range(no_of_blocks):
                for lab in range(no_of_labs):
                    course_slot_vars = []
                    for level in range(no_of_level):
                        for group in range(no_of_groups_levelwise[level]):
                            for course in range(len(courses)):
                                key = (level, group, course, week, day, block, lab)
                                if key in assign:
                                    course_slot_vars.append(assign[key])
                    if course_slot_vars:
                        model.Add(sum(course_slot_vars) <= 1)

    for level in range(no_of_level):
        for group in range(no_of_groups_levelwise[level]):
            for week in range(no_of_weeks):
                for day in range(no_of_days):
                    for block in range(no_of_blocks):
                        for lab in range(no_of_labs):
                            group_slot_vars = []
                            for course in range(len(courses)):
                                key = (level, group, course, week, day, block, lab)
                                if key in assign:
                                    group_slot_vars.append(assign[key])
                            if group_slot_vars:
                                model.Add(sum(group_slot_vars) <= 1)

    objective_terms = []
    for level in range(no_of_level):
        for group in range(no_of_groups_levelwise[level]):
            for course in range(len(courses)):
                if student_data[level][group][course] != 1:
                    continue
                for week in range(no_of_weeks):
                    for day in range(no_of_days):
                        for block in range(no_of_blocks):
                            for lab in range(no_of_labs):
                                key = (level, group, course, week, day, block, lab)
                                if key in assign:
                                    if objective_choice == "Preference Weighted Scheduling":
                                        # use the weekly preference weight as the objective coefficient
                                        weight = preference_list[week]
                                    else:
                                        # notebook logic for balanced distribution
                                        weight = block
                                    objective_terms.append(assign[key] * weight)

    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    markdown_output = ""
    weekly_schedule = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for week in range(no_of_weeks):
            header_cells = ["Days"] + [f"Block{block + 1}-Lab{lab + 1}" for block in range(no_of_blocks) for lab in range(no_of_labs)]
            markdown_output += f"\n### Week: {week + 1}\n"
            markdown_output += "| " + " | ".join(f"{cell:<22}" for cell in header_cells) + " |\n"
            markdown_output += "|" + "|".join(["-" * 24] + ["-" * 22] * (len(header_cells) - 1)) + "|\n"

            week_rows = []
            for day in range(no_of_days):
                row = [days[day]]
                for block in range(no_of_blocks):
                    for lab in range(no_of_labs):
                        assigned_text = ""
                        for level in range(no_of_level):
                            for group in range(no_of_groups_levelwise[level]):
                                for course in range(len(courses)):
                                    key = (level, group, course, week, day, block, lab)
                                    if key in assign and solver.Value(assign[key]) == 1:
                                        assigned_text = f"{courses[course]}-{level_text[level]}-Group{group + 1}"
                                        break
                                if assigned_text:
                                    break
                            if assigned_text:
                                break
                        row.append(assigned_text)
                week_rows.append(row)
                markdown_output += "| " + " | ".join(f"{cell:<22}" for cell in row) + " |\n"

            weekly_schedule.append({
                "week": week + 1,
                "header": header_cells,
                "rows": week_rows,
            })
    else:
        markdown_output = "No Solution Found"

    return {
        "status": solver.StatusName(status),
        "objective_value": solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "markdown_output": markdown_output,
        "weekly_schedule": weekly_schedule,
        "daily_header_data": [header_cells],
    }


def run_ortools_solver(params):
    if not params.get("course_data") or not params.get("course_columns"):
        raise ValueError("CSV roster data is required. Upload a roster CSV containing level, group, course, and student enrollment information.")

    return _solve_course_aware_model(params)
