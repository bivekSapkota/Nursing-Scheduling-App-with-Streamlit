from solver import run_ortools_solver


def test_solver_uses_csv_roster_data_for_course_aware_schedule():
    params = {
        "no_of_weeks": 1,
        "no_of_days": 7,
        "no_of_blocks": 2,
        "no_of_labs": 2,
        "objective": "Balanced Schedule Distribution",
        "preference_weights": [1],
        "block_availability": [
            [1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1],
        ],
        "labs_arrangement": [
            [[1, 1], [1, 1]],
            [[1, 1], [1, 1]],
            [[1, 1], [1, 1]],
            [[1, 1], [1, 1]],
            [[1, 1], [1, 1]],
            [[1, 1], [1, 1]],
            [[1, 1], [1, 1]],
        ],
        "course_data": [
            {"Student_Level": "Senior", "Group": "Group1", "CourseA": True, "CourseB": False},
            {"Student_Level": "Senior", "Group": "Group1", "CourseA": False, "CourseB": True},
            {"Student_Level": "Junior", "Group": "Group2", "CourseA": True, "CourseB": False},
        ],
        "course_columns": ["CourseA", "CourseB"],
        "course_sessions": [1, 1],
    }

    result = run_ortools_solver(params)

    assert result["status"] in {"OPTIMAL", "FEASIBLE"}
    assert len(result["weekly_schedule"]) == 1
    assert len(result["weekly_schedule"][0]["rows"]) == 7
    assert any("CourseA" in cell for row in result["weekly_schedule"][0]["rows"] for cell in row)


def test_solver_enforces_level_specific_allowed_days():
    params = {
        "no_of_weeks": 1,
        "no_of_days": 6,
        "no_of_blocks": 1,
        "no_of_labs": 1,
        "objective": "Balanced Schedule Distribution",
        "preference_weights": [1],
        "block_availability": [
            [1, 0, 1, 0, 0, 1],
            [0, 1, 1, 1, 0, 1],
            [0, 1, 0, 1, 1, 1],
        ],
        "labs_arrangement": [
            [[1]], [[1]], [[1]], [[1]], [[1]], [[1]],
        ],
        "course_data": [
            {"Student_Level": "Accelerated", "Group": "Group1", "CourseA": True},
            {"Student_Level": "Junior", "Group": "Group1", "CourseA": True},
            {"Student_Level": "Senior", "Group": "Group1", "CourseA": True},
        ],
        "course_columns": ["CourseA"],
        "course_sessions": [1],
    }

    result = run_ortools_solver(params)

    assert result["status"] in {"OPTIMAL", "FEASIBLE"}
    assignments_by_level = {"Senior": set(), "Junior": set(), "Accelerated": set()}

    for week in result["weekly_schedule"]:
        for row in week["rows"]:
            day_name = row[0]
            cell_value = row[1] if len(row) > 1 else ""
            if not cell_value:
                continue
            level_name = cell_value.split("-")[1]
            assignments_by_level.setdefault(level_name, set()).add(day_name)

    assert assignments_by_level["Senior"].issubset({"Monday", "Wednesday", "Saturday"})
    assert assignments_by_level["Junior"].issubset({"Tuesday", "Wednesday", "Thursday", "Saturday"})
    assert assignments_by_level["Accelerated"].issubset({"Tuesday", "Thursday", "Friday", "Saturday"})


def test_solver_maps_allowed_days_by_level_name_not_index_order():
    params = {
        "no_of_weeks": 1,
        "no_of_days": 6,
        "no_of_blocks": 1,
        "no_of_labs": 1,
        "objective": "Balanced Schedule Distribution",
        "preference_weights": [1],
        "block_availability": [
            [1, 0, 1, 0, 0, 1],
            [0, 1, 1, 1, 0, 1],
            [0, 1, 0, 1, 1, 1],
        ],
        "labs_arrangement": [
            [[1]], [[1]], [[1]], [[1]], [[1]], [[1]],
        ],
        "course_data": [
            {"Student_Level": "Accelerated", "Group": "Group1", "CourseA": True},
            {"Student_Level": "Junior", "Group": "Group1", "CourseA": True},
            {"Student_Level": "Senior", "Group": "Group1", "CourseA": True},
        ],
        "course_columns": ["CourseA"],
        "course_sessions": [1],
    }

    result = run_ortools_solver(params)

    assert result["status"] in {"OPTIMAL", "FEASIBLE"}
    assignments_by_level = {"Senior": set(), "Junior": set(), "Accelerated": set()}

    for week in result["weekly_schedule"]:
        for row in week["rows"]:
            day_name = row[0]
            cell_value = row[1] if len(row) > 1 else ""
            if not cell_value:
                continue
            level_name = cell_value.split("-")[1]
            if level_name in assignments_by_level:
                assignments_by_level[level_name].add(day_name)

    assert assignments_by_level["Senior"].issubset({"Monday", "Wednesday", "Saturday"})
    assert assignments_by_level["Junior"].issubset({"Tuesday", "Wednesday", "Thursday", "Saturday"})
    assert assignments_by_level["Accelerated"].issubset({"Tuesday", "Thursday", "Friday", "Saturday"})
