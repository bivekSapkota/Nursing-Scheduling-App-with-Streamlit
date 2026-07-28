from ortools.sat.python import cp_model

# ============================================================
# Default Patterns for Block Availability and Labs Arrangement
# ============================================================
def get_default_block_availability():
    """
    Default block availability pattern for each level across days.
    Days: Mon, Tue, Wed, Thu, Fri, Sat
    """
    return [
        [1, 0, 1, 0, 0, 1],  # Senior availability
        [0, 1, 1, 1, 0, 1],  # Junior availability
        [0, 1, 0, 1, 1, 1]   # Accelerated availability
    ]

def get_default_labs_arrangement(no_of_blocks, no_of_labs, no_of_days):
    """
    Default lab arrangement pattern for each day and block.
    Returns: List of days, each containing list of blocks, each containing list of labs.
    """
    days_arrangement = [
        [[0, 1], [0, 0]],  # Monday
        [[1, 1], [1, 1]],  # Tuesday
        [[1, 1], [1, 1]],  # Wednesday
        [[0, 0], [1, 0]],  # Thursday
        [[1, 1], [1, 1]],  # Friday
        [[1, 1], [1, 1]],  # Saturday
        [[1, 1], [1, 1]]   # Sunday
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

def run_ortools_solver(params):

  
    # parameters
    no_of_weeks = params["no_of_weeks"]
    no_of_days = params["no_of_days"]
    no_of_blocks = params["no_of_blocks"]
    no_of_labs = params["no_of_labs"]

    no_of_groups_levelwise = [
        params["senior_groups"],
        params["junior_groups"],
        params["accelerated_groups"]
    ]

    no_of_lab_sessions_levelwise = [
        params["senior_sessions"],
        params["junior_sessions"],
        params["accelerated_sessions"]
    ]

    level_text = ["Senior", "Junior", "Accelerated"]
    no_of_level = len(no_of_groups_levelwise)

    daily_header_data = [[
        [
            f"Block{block+1}-Lab{lab+1}"
            for block in range(no_of_blocks)
            for lab in range(no_of_labs)
        ]
    ]]

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    # ------------------------------------------------------------
    # Fixed arrays (actual data from nursing school)- commented out for now, replaced with user input
    # ------------------------------------------------------------
    # block_availability = [
    #     [1, 0, 1, 0, 0, 1],  # senior
    #     [0, 1, 1, 1, 0, 1],  # junior
    #     [0, 1, 0, 1, 1, 1]   # accelerated
    # ]

    # labs_arrangement = [
    #     [[0, 1], [0, 0]],  # Monday
    #     [[1, 1], [1, 1]],  # Tuesday
    #     [[1, 1], [1, 1]],  # Wednesday
    #     [[0, 0], [1, 0]],  # Thursday
    #     [[1, 1], [1, 1]],  # Friday
    #     [[1, 1], [1, 1]]   # Saturday
    # ]

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

    # ------------------------------------------------------------
    # Build Model
    # ------------------------------------------------------------
    model = cp_model.CpModel()

    assign = {}

    for level in range(no_of_level):
        for group in range(no_of_groups_levelwise[level]):
            for week in range(no_of_weeks):
                for day in range(no_of_days):
                    for block in range(no_of_blocks):
                        for lab in range(no_of_labs):
                            assign[(level, group, week, day, block, lab)] = \
                                model.NewBoolVar(f"L{level}_G{group}_W{week}_D{day}_B{block}_L{lab}")

    # ------------------------------------------------------------
    # Constraint 1 & 2: Required sessions + allowed days
    # ------------------------------------------------------------
    for level in range(no_of_level):
        for group in range(no_of_groups_levelwise[level]):
            total_sessions = []
            forbidden_sessions = []

            for week in range(no_of_weeks):
                for day in range(no_of_days):
                    for block in range(no_of_blocks):
                        for lab in range(no_of_labs):
                            var = assign[(level, group, week, day, block, lab)]
                            total_sessions.append(var)
                            forbidden_sessions.append(var * (not block_availability[level][day]))

            model.Add(sum(total_sessions) == no_of_lab_sessions_levelwise[level])
            model.Add(sum(forbidden_sessions) == 0)

    # ------------------------------------------------------------
    # Constraint 3: At most one lab per day per group
    # ------------------------------------------------------------
    for level in range(no_of_level):
        for group in range(no_of_groups_levelwise[level]):
            for week in range(no_of_weeks):
                for day in range(no_of_days):
                    daily_vars = [
                        assign[(level, group, week, day, block, lab)]
                        for block in range(no_of_blocks)
                        for lab in range(no_of_labs)
                    ]
                    model.Add(sum(daily_vars) <= 1)

    # ------------------------------------------------------------
    # Constraint 4: Lab schedule availability
    # ------------------------------------------------------------
    for week in range(no_of_weeks):
        for day in range(no_of_days):
            forbidden = []
            for level in range(no_of_level):
                for group in range(no_of_groups_levelwise[level]):
                    for block in range(no_of_blocks):
                        for lab in range(no_of_labs):
                            forbidden.append(
                                assign[(level, group, week, day, block, lab)]
                                * (not labs_arrangement[day][block][lab])
                            )
            model.Add(sum(forbidden) == 0)

    # ------------------------------------------------------------
    # Constraint 5: Only one group per lab per block
    # ------------------------------------------------------------
    for week in range(no_of_weeks):
        for day in range(no_of_days):
            for block in range(no_of_blocks):
                for lab in range(no_of_labs):
                    occupancy = [
                        assign[(level, group, week, day, block, lab)]
                        for level in range(no_of_level)
                        for group in range(no_of_groups_levelwise[level])
                    ]
                    model.Add(sum(occupancy) <= 1)

    # ------------------------------------------------------------
    # Objective
    # ------------------------------------------------------------
    z_min = []
    for level in range(no_of_level):
        for group in range(no_of_groups_levelwise[level]):
            for week in range(no_of_weeks):
                for day in range(no_of_days):
                    for block in range(no_of_blocks):
                        for lab in range(no_of_labs):
                            var = assign[(level, group, week, day, block, lab)]
                            if objective_choice == "Preference Weighted Scheduling":
                                z_min.append(var * preference_list[week])
                            else:
                                z_min.append(var * block)

    model.Minimize(sum(z_min))

    # ------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------
    solver = cp_model.CpSolver()
    status = solver.solve(model)

    # ------------------------------------------------------------
    # Build Markdown and structured schedule output
    # ------------------------------------------------------------
    markdown_output = ""
    weekly_schedule = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):

        for week in range(no_of_weeks):

            markdown_output += f"\n### Week: {week+1}\n"

            header_cells = ["Days"] + daily_header_data[0][0]
            markdown_output += "| " + " | ".join(f"{cell:<21}" for cell in header_cells) + " |\n"
            separator_cells = ["-" * 23] + ["-" * 21] * (len(header_cells) - 1)
            markdown_output += "|" + "|".join(separator_cells) + "|\n"

            week_rows = []
            for day in range(no_of_days):

                row = [days[day]]
                markdown_row = f"| {days[day]:<21} |"

                for block in range(no_of_blocks):
                    for lab in range(no_of_labs):

                        assigned_text = ""

                        for level in range(no_of_level):
                            for group in range(no_of_groups_levelwise[level]):
                                if solver.value(assign[(level, group, week, day, block, lab)]) == 1:
                                    assigned_text = f"{level_text[level]}-Group{group+1}"

                        row.append(assigned_text)
                        markdown_row += f"{assigned_text:<21} |"

                week_rows.append(row)
                markdown_output += markdown_row + "\n"

            weekly_schedule.append({
                "week": week + 1,
                "header": header_cells,
                "rows": week_rows
            })

    else:
        markdown_output = "No Solution Found"

    # ------------------------------------------------------------
    # Return results
    # ------------------------------------------------------------
    return {
        "status": solver.status_name(status),
        "objective_value": solver.objective_value if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "markdown_output": markdown_output,
        "weekly_schedule": weekly_schedule,
        "daily_header_data": daily_header_data
    }
