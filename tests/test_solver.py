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
