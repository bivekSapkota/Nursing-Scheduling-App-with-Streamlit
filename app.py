import streamlit as st
import pandas as pd
import openpyxl
from io import BytesIO
from solver import run_ortools_solver, get_default_block_availability, get_default_labs_arrangement

# Initialize session state
if "results" not in st.session_state:
    st.session_state.results = None
if "previous_params" not in st.session_state:
    st.session_state.previous_params = None
if "params_changed" not in st.session_state:
    st.session_state.params_changed = False

# 2. Streamlit App UI

st.set_page_config(page_title="Nursing Simulation Lab Scheduling Optimization", layout="wide")
st.title(" Nursing Simulation Lab Scheduling Optimization")

st.markdown("Copyright © 2023 Nursing Simulation Lab Scheduling Optimization App. All rights reserved.")
st.markdown("Contributors: Dr. Leonardo Bedoya- Valencia, Dr. Ebisa Wollega, Aminoritse Bajah-Onyejekwe, Bivek Sapkota")

# Sidebar Inputs
st.sidebar.header("Model Parameters")

no_of_weeks = st.sidebar.number_input("Number of Weeks", min_value=1, max_value=52, value=16)
no_of_days = st.sidebar.number_input("Number of Days per Week", min_value=1, max_value=7, value=6)
no_of_blocks = st.sidebar.slider("Blocks per Day", min_value=1, max_value=5, value=2)
no_of_labs = st.sidebar.slider("Labs per Block", min_value=1, max_value=5, value=2)

st.sidebar.markdown("<hr style='border-top:3px solid green;margin:10px 0;'>", unsafe_allow_html=True)

st.sidebar.subheader("Level Settings")

senior_groups = st.sidebar.number_input("No. of Senior Groups", min_value=1, max_value=50, value=15)
junior_groups = st.sidebar.number_input("No. of Junior Groups", min_value=1, max_value=50, value=12)
accelerated_groups = st.sidebar.number_input("No. of Accelerated Groups", min_value=1, max_value=50, value=15)

st.sidebar.markdown("<hr style='border-top:3px solid green;margin:10px 0;'>", unsafe_allow_html=True)
st.sidebar.subheader("Session Settings")

senior_sessions = st.sidebar.number_input("No. of Senior Lab Sessions", min_value=1, max_value=20, value=4)
junior_sessions = st.sidebar.number_input("No. of Junior Lab Sessions", min_value=1, max_value=20, value=4)
accelerated_sessions = st.sidebar.number_input("No. of Accelerated Lab Sessions", min_value=1, max_value=20, value=7)

st.sidebar.markdown("<hr style='border-top:3px solid green;margin:10px 0;'>", unsafe_allow_html=True)

st.sidebar.markdown("### Block Availability (Allowed Days)")

days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
active_days = days_of_week[:no_of_days]
levels_list = ["Senior", "Junior", "Accelerated"]

# Get default block availability pattern and adapt to the selected number of days
raw_block_availability = get_default_block_availability()
if no_of_days <= len(raw_block_availability[0]):
    default_block_availability = [level[:no_of_days] for level in raw_block_availability]
else:
    default_block_availability = [level + [1] * (no_of_days - len(level)) for level in raw_block_availability]

block_availability = []

for lvl_idx, lvl in enumerate(levels_list):
    st.sidebar.markdown(f"**{lvl}**")
    row = []
    cols = st.sidebar.columns(len(active_days))
    for i, d in enumerate(active_days):
        default_value = default_block_availability[lvl_idx][i]
        row.append(cols[i].checkbox(d, value=bool(default_value), key=f"{lvl}_{d}"))
    block_availability.append(row)
    st.sidebar.markdown("---")


st.sidebar.markdown("<hr style='border-top:3px solid green;margin:10px 0;'>", unsafe_allow_html=True)
st.sidebar.markdown("### Labs Arrangement (Which Labs Run)")

# Get default labs arrangement pattern and adapt it to the selected number of days
default_labs_arrangement = get_default_labs_arrangement(no_of_blocks, no_of_labs, no_of_days)

labs_arrangement = []

for day_idx, day in enumerate(active_days):
    st.sidebar.markdown(f"**{day}**")
    day_blocks = []

    for block in range(no_of_blocks):
        st.sidebar.markdown(f"Block {block+1}:")
        cols = st.sidebar.columns(no_of_labs)

        block_labs = []
        for lab in range(no_of_labs):
            default_value = default_labs_arrangement[day_idx][block][lab]
            block_labs.append(
                cols[lab].checkbox(
                    f"Lab {lab+1}",
                    value=bool(default_value),
                    key=f"{day}_B{block}_L{lab}"
                )
            )

        day_blocks.append(block_labs)
    
    st.sidebar.markdown("---")
    labs_arrangement.append(day_blocks)



# 3. Main Controls
# Objective selection on main screen
st.subheader("Objective Selection")
objective_choice = st.radio(
    "Solver Objective",
    options=[
        "Balanced Schedule Distribution",
        "Preference Weighted Scheduling"
    ],
    index=0,
    help="Choose which objective the solver should minimize."
)

preference_weights = None
if objective_choice == "Preference Weighted Scheduling":
    st.markdown("### Weekly Preference Weights")
    st.caption("Lower values mean higher scheduling preference for that week.")

    default_preference = [1] * no_of_weeks
    weight_cols = st.columns(min(no_of_weeks, 6))
    preference_weights = []
    for week in range(no_of_weeks):
        with weight_cols[week % len(weight_cols)]:
            preference_weights.append(
                st.number_input(
                    f"Week {week + 1}",
                    min_value=1,
                    max_value=20,
                    value=default_preference[week],
                    key=f"preference_week_{week + 1}"
                )
            )

# Collect parameters
params = {
    "no_of_weeks": no_of_weeks,
    "no_of_days": no_of_days,
    "no_of_blocks": no_of_blocks,
    "no_of_labs": no_of_labs,
    "senior_groups": senior_groups,
    "junior_groups": junior_groups,
    "accelerated_groups": accelerated_groups,
    "senior_sessions": senior_sessions,
    "junior_sessions": junior_sessions,
    "accelerated_sessions": accelerated_sessions,
    "objective": objective_choice,
    "preference_weights": preference_weights,
    "block_availability": block_availability,
    "labs_arrangement": labs_arrangement
}

# Detect if params have changed
import json
def params_equal(p1, p2):
    if p1 is None or p2 is None:
        return p1 == p2
    try:
        return json.dumps(p1, sort_keys=True, default=str) == json.dumps(p2, sort_keys=True, default=str)
    except:
        return p1 == p2

if not params_equal(params, st.session_state.previous_params):
    st.session_state.params_changed = True
    st.session_state.previous_params = params
else:
    st.session_state.params_changed = False

# Display warning if params changed
if st.session_state.params_changed and st.session_state.results is not None:
    st.warning("⚠️ Input Parameters have changed. Please run the solver again to update the schedule.")

# CSS for orange, bold Run Solver button
st.markdown("""
    <style>
        div.stButton > button:first-child {
            background-color: #ff8c00;   /* Orange fill */
            color: white;                /* Text color */
            font-weight: bold;           /* Bold text */
            padding: 0.6em 1.2em;        /* Slightly larger button */
            border-radius: 8px;          /* Rounded corners */
        }
        div.stButton > button:first-child:hover {
            background-color: #e67e00;   /* Darker orange on hover */
        }
        div.stDownloadButton > button:first-child {
            background-color: #28a745;   /* Green fill */
            color: white;                /* Text color */
            font-weight: bold;           /* Bold text */
            padding: 0.6em 1.2em;        /* Slightly larger button */
            border-radius: 8px;          /* Rounded corners */
        }
        div.stDownloadButton > button:first-child:hover {
            background-color: #218838;   /* Darker green on hover */
        }
        div[data-testid="stMarkdownContainer"] table,
        div[data-testid="stMarkdownContainer"] th,
        div[data-testid="stMarkdownContainer"] td {
            border: 1px solid green;
            border-collapse: collapse;
        }
        div[data-testid="stMarkdownContainer"] th,
        div[data-testid="stMarkdownContainer"] td {
            padding: 8px;
        }
    </style>
""", unsafe_allow_html=True)

st.header(" Run Optimization Solver")

if st.button("Run Solver"):
    with st.spinner("Running OR-Tools solver..."):
        results = run_ortools_solver(params)
        st.session_state.results = results
        st.session_state.params_changed = False  # Clear the changed flag after solver runs

# Display results if they exist in session state
if st.session_state.results is not None:
    results = st.session_state.results
    
    # ------------------------------------------------------------
    # 4. Display Results
    # ------------------------------------------------------------
    st.success("Solver completed!")

    st.markdown(f"**Solver Status:** {results.get('status', 'Unknown')}")
    st.markdown(f"**Objective Value:** {results.get('objective_value', 'N/A')}")

    markdown_text = results.get("markdown_output", "No schedule returned.")
    
    schedule_data = results.get("weekly_schedule", [])
    group_labels = []
    for week in schedule_data:
        for row in week["rows"]:
            for cell in row[1:]:
                if cell and cell not in group_labels:
                    group_labels.append(cell)

    level_options = ["Senior", "Junior", "Accelerated"]
    selected_levels = st.multiselect("Filter by level", options=level_options, default=level_options)
    filtered_group_labels = sorted([label for label in group_labels if any(label.startswith(level) for level in selected_levels)])
    selected_groups = st.multiselect("Filter by group", options=filtered_group_labels, default=filtered_group_labels)

    def apply_group_filter(schedule, allowed_groups):
        if not allowed_groups:
            return [{"week": week["week"], "header": week["header"], "rows": [[row[0]] + ["" for _ in row[1:]] for row in week["rows"]]} for week in schedule]
        filtered = []
        allowed_set = set(allowed_groups)
        for week in schedule:
            filtered_rows = []
            for row in week["rows"]:
                filtered_cells = [row[0]] + [cell if cell in allowed_set else "" for cell in row[1:]]
                filtered_rows.append(filtered_cells)
            filtered.append({"week": week["week"], "header": week["header"], "rows": filtered_rows})
        return filtered

    filtered_schedule_data = apply_group_filter(schedule_data, selected_groups)

    def format_filtered_markdown(schedule):
        lines = []
        for week in schedule:
            lines.append(f"## Week {week['week']}")
            lines.append("")
            # Determine column widths for aligned output
            columns = [week["header"]] + [[str(cell) for cell in row] for row in week["rows"]]
            col_widths = [max(len(str(item)) for item in col) for col in zip(*columns)]

            def format_row(row_values):
                padded = [str(value).ljust(width) for value, width in zip(row_values, col_widths)]
                return "| " + " | ".join(padded) + " |"

            lines.append(format_row(week["header"]))
            lines.append("| " + " | ".join(["-" * width for width in col_widths]) + " |")
            for row in week["rows"]:
                lines.append(format_row([str(cell) for cell in row]))
            lines.append("")
        return "\n".join(lines)

    filtered_markdown_text = format_filtered_markdown(filtered_schedule_data)

    base_colors = [
        "#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2",
        "#7f7f7f", "#17becf", "#bcbd22", "#393b79", "#637939", "#8c6d31",
        "#843c39", "#7b4173", "#5254a3", "#6b6ecf", "#9c9ede", "#ce6dbd",
        "#de9ed6", "#8c6d31", "#e7ba52", "#bd9e39", "#db843d", "#ad494a"
    ]
    group_colors = {label: base_colors[i % len(base_colors)] for i, label in enumerate(filtered_group_labels)}

    excel_output = b""
    if filtered_schedule_data:
        output_buffer = BytesIO()
        with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
            # Create the combined first worksheet before individual week sheets.
            combined_sheet = writer.book.create_sheet(title="All Weeks", index=0)
            writer.sheets["All Weeks"] = combined_sheet
            current_row = 1
            for week in filtered_schedule_data:
                # Week title row
                combined_sheet.cell(row=current_row, column=1, value=f"Week {week['week']}")
                combined_sheet.cell(row=current_row, column=1).font = openpyxl.styles.Font(bold=True)
                if len(week["header"]) > 1:
                    combined_sheet.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(week["header"]))
                current_row += 1

                # Header row
                for idx, header in enumerate(week["header"], start=1):
                    cell = combined_sheet.cell(row=current_row, column=idx, value=header)
                    cell.fill = openpyxl.styles.PatternFill(fill_type="solid", start_color="FFD9D9D9")
                    cell.font = openpyxl.styles.Font(bold=True, color="FF000000")
                current_row += 1

                # Data rows
                for row in week["rows"]:
                    for c, value in enumerate(row, start=1):
                        cell = combined_sheet.cell(row=current_row, column=c, value=value)
                        if c == 1:
                            cell.font = openpyxl.styles.Font(bold=True)
                        elif value:
                            color = group_colors.get(value, "#555555").lstrip("#")
                            cell.fill = openpyxl.styles.PatternFill(fill_type="solid", start_color=color)
                            cell.font = openpyxl.styles.Font(color="FFFFFFFF")
                        else:
                            cell.fill = openpyxl.styles.PatternFill(fill_type="solid", start_color="FFFFFFFF")
                            cell.font = openpyxl.styles.Font(color="FFFFFFFF")
                    current_row += 1

                current_row += 1  # blank row between weeks

            for idx in range(1, len(filtered_schedule_data[0]["header"]) + 1):
                combined_sheet.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = 18

            for week in filtered_schedule_data:
                df = pd.DataFrame(week["rows"], columns=week["header"])
                sheet_name = f"Week{week['week']}"
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                worksheet = writer.sheets[sheet_name]
                for idx, header in enumerate(week["header"], start=1):
                    cell = worksheet.cell(row=1, column=idx)
                    cell.fill = openpyxl.styles.PatternFill(fill_type="solid", start_color="FFD9D9D9")
                    cell.font = openpyxl.styles.Font(bold=True, color="FF000000")
                for r, row in enumerate(week["rows"], start=2):
                    for c, value in enumerate(row, start=1):
                        cell = worksheet.cell(row=r, column=c)
                        if c == 1:
                            cell.font = openpyxl.styles.Font(bold=True)
                        elif value:
                            color = group_colors.get(value, "#555555").lstrip("#")
                            cell.fill = openpyxl.styles.PatternFill(fill_type="solid", start_color=color)
                            cell.font = openpyxl.styles.Font(color="FFFFFFFF")
                        else:
                            cell.fill = openpyxl.styles.PatternFill(fill_type="solid", start_color="FFFFFFFF")
                            cell.font = openpyxl.styles.Font(color="FFFFFFFF")
                for idx in range(1, len(week["header"]) + 1):
                    worksheet.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = 18

        excel_output = output_buffer.getvalue()

    col1, col2 = st.columns([0.5, 0.5])
    with col1:
        st.subheader("📅 Weekly Schedule")
    with col2:
        btn1, btn2 = st.columns([0.5, 0.5])
        with btn1:
            st.download_button(
                label="Download Schedule as Markdown text",
                data=filtered_markdown_text,
                file_name="nursing_schedule.txt",
                mime="text/plain"
            )
        with btn2:
            if excel_output:
                st.download_button(
                    label="Download Schedule as Excel",
                    data=excel_output,
                    file_name="nursing_schedule.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    def render_schedule_html(schedule):
        html = ["<div style='font-family:Arial, sans-serif;'>"]
        for week in schedule:
            html.append(f"<h3>Week {week['week']}</h3>")
            html.append("<table style='border-collapse:collapse;width:100%;margin-bottom:1.5rem;'>")
            html.append("<tr>")
            for header in week["header"]:
                html.append(
                    f"<th style='border:1px solid #ddd;padding:8px;background:#f2f2f2;text-align:left;color:#333;'>{header}</th>"
                )
            html.append("</tr>")
            for row in week["rows"]:
                html.append("<tr>")
                html.append(
                    f"<td style='border:1px solid #ddd;padding:8px;background:#ffffff;color:#111;font-weight:bold;'>{row[0]}</td>"
                )
                for cell in row[1:]:
                    if cell:
                        color = group_colors.get(cell, "#555555")
                        html.append(
                            f"<td style='border:1px solid #ddd;padding:8px;background:{color};color:#ffffff;text-align:center;font-weight:bold;'>{cell}</td>"
                        )
                    else:
                        html.append(
                            "<td style='border:1px solid #ddd;padding:8px;background:#ffffff;color:#ffffff;text-align:center;'></td>"
                        )
                html.append("</tr>")
            html.append("</table>")
        html.append("</div>")
        return "".join(html)

    styled_schedule_html = render_schedule_html(filtered_schedule_data) if filtered_schedule_data else ""
    if styled_schedule_html:
        st.markdown(styled_schedule_html, unsafe_allow_html=True)
    else:
        st.markdown(filtered_markdown_text)

# ------------------------------------------------------------
# End of App
# ------------------------------------------------------------
