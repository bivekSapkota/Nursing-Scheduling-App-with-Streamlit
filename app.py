import json
import re
import uuid
import base64
from datetime import date, timedelta
from html import escape
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import openpyxl
from io import BytesIO
from solver import run_ortools_solver, get_default_block_availability, get_default_labs_arrangement


def generate_sample_roster_df(
    senior_groups=2,
    junior_groups=2,
    accelerated_groups=2,
    students_per_group=8,
    senior_course_names=None,
    junior_course_names=None,
):
    levels = ["Senior", "Junior", "Accelerated"]
    groups_by_level = {
        "Senior": [f"Group{i}" for i in range(1, senior_groups + 1)],
        "Junior": [f"Group{i}" for i in range(1, junior_groups + 1)],
        "Accelerated": [f"Group{i}" for i in range(1, accelerated_groups + 1)],
    }
    senior_courses = senior_course_names or ["412L", "422L", "442L"]
    junior_courses = junior_course_names or ["312L", "322L", "382L"]
    all_courses = senior_courses + junior_courses

    rows = []
    group_course_sets = {}

    for level in levels:
        if level == "Senior":
            group_course_sets[level] = {group: senior_courses for group in groups_by_level[level]}
        elif level == "Junior":
            group_course_sets[level] = {group: junior_courses for group in groups_by_level[level]}
        else:
            group_course_sets[level] = {
                group: senior_courses + junior_courses for group in groups_by_level[level]
            }

    for level in levels:
        for group in groups_by_level[level]:
            course_set = group_course_sets[level][group]
            for idx in range(students_per_group):
                student_name = f"{level}-{group}-Student{idx + 1}"
                row = {
                    "Student_Name": student_name,
                    "Student_Level": level,
                    "Group": group,
                }
                for course in all_courses:
                    row[course] = 1 if course in course_set else 0
                rows.append(row)

    return pd.DataFrame(rows)


def load_roster_file(file_obj):
    if file_obj is None:
        return None
    try:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        content = file_obj.read()
        if not content or content.strip() == b"":
            return None
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        return pd.read_csv(BytesIO(content))
    except Exception:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        raise


def get_default_course_requirement_matrix(course_columns):
    levels = ["Senior", "Junior", "Accelerated"]
    default = {level: {course: 0 for course in course_columns} for level in levels}
    for course in course_columns:
        match = re.search(r"(\d+)", str(course))
        course_num = int(match.group(1)) if match else None
        if course_num is None:
            continue
        if course_num >= 400:
            default["Senior"][course] = 1
            default["Accelerated"][course] = 1
        elif course_num >= 300:
            default["Junior"][course] = 1
            default["Accelerated"][course] = 1
    return default


# Initialize session state
if "results" not in st.session_state:
    st.session_state.results = None
if "previous_params" not in st.session_state:
    st.session_state.previous_params = None
if "params_changed" not in st.session_state:
    st.session_state.params_changed = False
if "selected_schedule_cells" not in st.session_state:
    st.session_state.selected_schedule_cells = []

# 2. Streamlit App UI

st.set_page_config(page_title="Nursing Simulation Lab Scheduling Optimization", layout="wide")
st.title(" Nursing Simulation Lab Scheduling Optimization")

st.markdown("Copyright © 2023 Nursing Simulation Lab Scheduling Optimization App. All rights reserved.")
st.markdown("Contributors: Dr. Leonardo Bedoya- Valencia, Dr. Ebisa Wollega, Aminoritse Bajah-Onyejekwe, Bivek Sapkota")


def load_user_guide_html():
    """Inline the guide's local screenshots as base64 so they render inside the iframe."""
    guide_path = Path(__file__).resolve().parent / "User Guide.html"
    if not guide_path.exists():
        return None
    html_text = guide_path.read_text(encoding="utf-8")

    def embed_image(match):
        relative_src = match.group(1)
        image_path = guide_path.parent / relative_src
        if not image_path.exists():
            return match.group(0)
        encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        return match.group(0).replace(f'src="{relative_src}"', f'src="data:image/png;base64,{encoded}"')

    return re.sub(r'src="(screenshots/[^"]+)"', embed_image, html_text)


with st.expander("📖 User Guide — How to Use This App", expanded=False):
    guide_html = load_user_guide_html()
    if guide_html:
        components.html(guide_html, height=900, scrolling=True)
    else:
        st.warning("User Guide.html not found next to app.py.")

# Sidebar Inputs
st.sidebar.header("Model Parameters")

st.sidebar.caption("All scheduling inputs are derived from the uploaded CSV roster.")
week_start_date = st.sidebar.date_input(
    "Week starts from",
    value=date.today(),
    min_value=date(2020, 1, 1),
    max_value=date(2100, 12, 31),
    help="Choose the actual calendar date that the first week begins on."
)
no_of_weeks = st.sidebar.number_input("Number of Weeks", min_value=1, max_value=52, value=16)
no_of_days = st.sidebar.number_input("Number of Days per Week", min_value=1, max_value=7, value=6)
no_of_blocks = st.sidebar.slider("Blocks per Day", min_value=1, max_value=5, value=2)
no_of_labs = st.sidebar.slider("Labs per Block", min_value=1, max_value=5, value=2)


def format_week_date_range(start_date, day_count):
    end_date = start_date + timedelta(days=day_count - 1)
    if start_date.month == end_date.month:
        return f"{start_date.strftime('%b')} {start_date.day}–{end_date.day}"
    return f"{start_date.strftime('%b')} {start_date.day}–{end_date.strftime('%b')} {end_date.day}"


def get_week_label(week_index, day_count, start_date):
    week_start = start_date + timedelta(weeks=week_index)
    date_range = format_week_date_range(week_start, day_count)
    return f"Week {week_index + 1} ({date_range})"

st.sidebar.markdown("<hr style='border-top:3px solid green;margin:10px 0;'>", unsafe_allow_html=True)

with st.sidebar.expander("Sample CSV Generator"):
    student_group_size = st.slider("Students per group", min_value=6, max_value=9, value=8, help="Each group in the generated roster will contain this many students.")
    senior_group_count = st.number_input("Senior groups", min_value=1, max_value=10, value=2)
    junior_group_count = st.number_input("Junior groups", min_value=1, max_value=10, value=2)
    accelerated_group_count = st.number_input("Accelerated groups", min_value=1, max_value=10, value=2)

    default_senior_courses = "412L, 422L, 442L"
    default_junior_courses = "312L, 322L, 382L"
    senior_course_names_input = st.text_input(
        "Senior course names",
        value=default_senior_courses,
        help="Comma-separated senior course codes. Default: 412L, 422L, 442L",
    )
    junior_course_names_input = st.text_input(
        "Junior course names",
        value=default_junior_courses,
        help="Comma-separated junior course codes. Default: 312L, 322L, 382L",
    )

    def parse_course_names(raw_text, fallback):
        if raw_text is None or not str(raw_text).strip():
            return fallback
        parsed = [item.strip() for item in str(raw_text).split(",") if item.strip()]
        return parsed if parsed else fallback

    if st.button("Generate & load sample roster"):
        senior_course_names = parse_course_names(senior_course_names_input, ["412L", "422L", "442L"])
        junior_course_names = parse_course_names(junior_course_names_input, ["312L", "322L", "382L"])

        sample_roster = generate_sample_roster_df(
            senior_groups=senior_group_count,
            junior_groups=junior_group_count,
            accelerated_groups=accelerated_group_count,
            students_per_group=student_group_size,
            senior_course_names=senior_course_names,
            junior_course_names=junior_course_names,
        )
        st.session_state["sample_roster_csv"] = sample_roster.to_csv(index=False)
        st.session_state["uploaded_roster_auto_loaded"] = sample_roster
        st.success("Sample roster created and loaded for use.")

    if "sample_roster_csv" in st.session_state:
        sample_roster_preview = pd.read_csv(BytesIO(st.session_state["sample_roster_csv"].encode("utf-8")))
        st.download_button(
            label="Download sample roster CSV",
            data=st.session_state["sample_roster_csv"],
            file_name="sample_roster.csv",
            mime="text/csv",
        )
        st.caption("Preview of the generated roster:")
        st.dataframe(sample_roster_preview.head(10), use_container_width=True)

def get_default_roster_file():
    preferred_names = [
        "Test Roaster.csv",
        "Test Roster.csv",
        "test roaster.csv",
        "test roster.csv",
    ]
    candidate_dirs = [Path.cwd(), Path(__file__).resolve().parent]

    for directory in candidate_dirs:
        for name in preferred_names:
            candidate = directory / name
            if candidate.exists() and candidate.is_file():
                return candidate

    for directory in candidate_dirs:
        csv_files = sorted(directory.glob("*.csv"))
        for candidate in csv_files:
            name_lower = candidate.name.lower()
            if "test" in name_lower and ("roaster" in name_lower or "roster" in name_lower):
                return candidate

    for directory in candidate_dirs:
        csv_files = sorted(directory.glob("*.csv"))
        if csv_files:
            return csv_files[0]

    return None


def load_default_roster_if_present():
    default_roster_path = get_default_roster_file()
    if default_roster_path is None:
        return None
    try:
        return pd.read_csv(default_roster_path)
    except Exception:
        return None


uploaded_roster = st.sidebar.file_uploader("Upload student/course roster CSV", type=["csv"])
default_roster_df = load_default_roster_if_present()

if uploaded_roster is not None:
    try:
        roster_df = load_roster_file(uploaded_roster)
        if roster_df is None:
            roster_df = None
            st.sidebar.error("The uploaded CSV is empty. Please upload a valid roster file with column headers and student data.")
    except pd.errors.EmptyDataError:
        roster_df = None
        st.sidebar.error("The uploaded CSV is empty. Please upload a valid roster file with column headers and student data.")
elif "uploaded_roster_auto_loaded" in st.session_state:
    roster_df = st.session_state["uploaded_roster_auto_loaded"]
    st.sidebar.caption("Using the generated sample roster CSV.")
elif default_roster_df is not None:
    roster_df = default_roster_df
    st.session_state["uploaded_roster_auto_loaded"] = roster_df
    st.sidebar.caption("Using the default roster file: Test Roster.csv")
else:
    roster_df = None

if roster_df is not None:
    excluded_cols = {"Student_Name", "Name", "Student_Level", "Level", "Group_Index", "Group", "StudentID", "Student_ID"}
    course_columns = [col for col in roster_df.columns if col not in excluded_cols]
    if course_columns:
        st.sidebar.caption(f"Detected courses: {', '.join(course_columns)}")
        default_course_requirements = get_default_course_requirement_matrix(course_columns)
        if "course_requirement_matrix" not in st.session_state:
            st.session_state.course_requirement_matrix = pd.DataFrame(
                [
                    {course: default_course_requirements[level].get(course, 0) for course in course_columns}
                    for level in ["Senior", "Junior", "Accelerated"]
                ],
                index=pd.Index(["Senior", "Junior", "Accelerated"], name="Level"),
                columns=course_columns,
            )

        st.sidebar.markdown("### Expected Course Requirements")
        st.session_state.course_requirement_matrix = st.sidebar.data_editor(
            st.session_state.course_requirement_matrix,
            hide_index=False,
            use_container_width=True,
            key="course_requirement_matrix_editor",
            disabled=False,
        )

        default_session_pattern = [3, 2, 1, 3, 2, 1]
        course_sessions = []
        for index, course in enumerate(course_columns):
            default_value = default_session_pattern[index % len(default_session_pattern)]
            course_sessions.append(
                st.sidebar.number_input(
                    f"{course} session count",
                    min_value=1,
                    max_value=20,
                    value=default_value,
                    key=f"course_session_{course}"
                )
            )
    else:
        course_columns = []
        course_sessions = []
        st.sidebar.warning("The selected roster file does not contain any course columns.")
else:
    course_columns = []
    course_sessions = []
    st.sidebar.warning("Upload a roster CSV to generate the level, group, course, and student schedule.")

if "uploaded_roster_auto_loaded" in st.session_state and uploaded_roster is not None:
    st.session_state.pop("uploaded_roster_auto_loaded", None)

st.sidebar.markdown("### Block Availability (Allowed Days)")
st.sidebar.caption("Define the actual days each level is allowed to attend lab. These are hard constraints enforced by the solver.")

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
    st.caption("Higher values mean lower scheduling preference for that week.")

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
    "senior_groups": 0,
    "junior_groups": 0,
    "accelerated_groups": 0,
    "senior_sessions": 0,
    "junior_sessions": 0,
    "accelerated_sessions": 0,
    "objective": objective_choice,
    "preference_weights": preference_weights,
    "block_availability": block_availability,
    "labs_arrangement": labs_arrangement,
    "course_data": roster_df.to_dict(orient="records") if roster_df is not None else None,
    "course_columns": course_columns,
    "course_sessions": course_sessions,
    "course_requirements": st.session_state.get("course_requirement_matrix", pd.DataFrame()).to_dict(orient="index") if "course_requirement_matrix" in st.session_state else {},
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

    def extract_assignment_parts(value):
        if not value:
            return None, None, None
        match = re.match(r"^(.*)-([^\-]+)-Group(\d+)$", str(value))
        if match:
            return match.group(1), match.group(2), int(match.group(3))
        return None, None, None

    group_labels = []
    level_options = set()
    for week in schedule_data:
        for row in week["rows"]:
            for cell in row[1:]:
                if not cell:
                    continue
                course, level, group_no = extract_assignment_parts(cell)
                if course is None:
                    continue
                if cell not in group_labels:
                    group_labels.append(cell)
                if level:
                    level_options.add(level)

    level_options = sorted(level_options)
    selected_levels = st.multiselect("Filter by level", options=level_options, default=level_options)
    filtered_group_labels = sorted([
        label for label in group_labels
        if extract_assignment_parts(label)[1] in selected_levels
    ])
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
            week_label = get_week_label(week["week"] - 1, no_of_days, week_start_date)
            lines.append(f"## {week_label}")
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
                week_label = get_week_label(week["week"] - 1, no_of_days, week_start_date)
                combined_sheet.cell(row=current_row, column=1, value=week_label)
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
                week_label = get_week_label(week["week"] - 1, no_of_days, week_start_date)
                sheet_name = week_label[:31]
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

    def parse_cell_assignment(cell_value):
        if not cell_value:
            return None
        match = re.match(r"^(.*)-([^\-]+)-Group(\d+)$", str(cell_value))
        if not match:
            return None
        course_name, level_name, group_number = match.groups()
        return {
            "course": course_name,
            "level": level_name,
            "group": f"Group{group_number}",
        }

    def normalize_flag(value):
        if pd.isna(value):
            return 0
        if isinstance(value, str):
            value = value.strip()
            if value.lower() in {"true", "t", "yes", "y"}:
                return 1
            if value.lower() in {"false", "f", "no", "n"}:
                return 0
        if isinstance(value, bool):
            return int(value)
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def get_students_for_cell(cell_value):
        if roster_df is None or cell_value in (None, ""):
            return []
        assignment = parse_cell_assignment(cell_value)
        if assignment is None:
            return []

        course_name = str(assignment["course"]).strip()
        level_name = str(assignment["level"]).strip()
        group_name = str(assignment["group"]).strip()

        requirement_matrix = st.session_state.get("course_requirement_matrix")
        expected_map = {}
        if isinstance(requirement_matrix, pd.DataFrame) and not requirement_matrix.empty:
            for index_name in requirement_matrix.index:
                if str(index_name).strip() == level_name:
                    expected_map = {str(k).strip(): v for k, v in requirement_matrix.loc[index_name].items()}
                    break

        student_names = []
        for _, row in roster_df.iterrows():
            if str(row.get("Student_Level", "")).strip() != level_name:
                continue
            if str(row.get("Group", "")).strip() != group_name:
                continue

            student_name = row.get("Student_Name")
            if pd.isna(student_name):
                continue
            student_name = str(student_name).strip()

            actual_flag = normalize_flag(row.get(course_name))
            expected_flag = normalize_flag(expected_map.get(course_name, 0))

            if actual_flag == 1 or expected_flag == 1:
                student_names.append({
                    "name": student_name,
                    "mismatch": actual_flag == 0 and expected_flag == 1,
                })

        unique_students = {}
        for student in student_names:
            name = student["name"]
            if name not in unique_students:
                unique_students[name] = student
            elif student["mismatch"] and not unique_students[name]["mismatch"]:
                unique_students[name] = student

        return [unique_students[name] for name in sorted(unique_students)]

    def build_schedule_grid_html(schedule, colors):
        if not schedule:
            return ""

        html_parts = [
            "<div style='font-family:Arial, sans-serif; overflow-x:auto;'>",
        ]

        for week in schedule:
            week_label = get_week_label(week["week"] - 1, no_of_days, week_start_date)
            html_parts.append(f"<h3 style='margin:0.8rem 0 0.5rem;'>{week_label}</h3>")
            html_parts.append("<table style='border-collapse:collapse; width:100%; table-layout:fixed; border:1px solid #ddd; font-size:12px; margin-bottom:1rem;'>")
            html_parts.append("<tr>")
            for header in week["header"]:
                html_parts.append(
                    f"<th style='border:1px solid #ddd; background:#f4f4f4; color:#333; padding:8px; text-align:center; min-width:90px;'>{header}</th>"
                )
            html_parts.append("</tr>")

            for row in week["rows"]:
                html_parts.append("<tr>")
                html_parts.append(f"<th style='border:1px solid #ddd; background:#fafafa; color:#111; padding:8px; text-align:left;'>{escape(str(row[0]))}</th>")
                for cell in row[1:]:
                    if cell:
                        color = colors.get(str(cell), "#64748b")
                        students = get_students_for_cell(cell)
                        student_data = json.dumps(students)
                        html_parts.append(
                            f"<td style='border:1px solid #ddd; background:{color}; color:#fff; padding:8px; text-align:center; font-weight:bold; vertical-align:middle; min-height:52px; white-space:normal;'><button class='course-cell' data-course='{escape(str(cell), quote=True)}' data-students='{escape(student_data, quote=True)}' type='button' style='all:unset; display:block; width:100%; height:100%; min-height:52px; cursor:pointer; color:#fff; font-weight:bold; text-align:center; background:transparent; padding:0;'> {escape(str(cell))} </button></td>"
                        )
                    else:
                        html_parts.append("<td style='border:1px solid #ddd; background:#ffffff; padding:8px; text-align:center; min-height:52px;'></td>")
                html_parts.append("</tr>")
            html_parts.append("</table>")

        html_parts.append("</div>")
        return "".join(html_parts)

    def render_schedule_with_tabs(schedule, colors):
        schedule_html = build_schedule_grid_html(schedule, colors)
        if not schedule_html:
            st.markdown(filtered_markdown_text)
            return

        html_string = """
        <style>
        * { box-sizing: border-box; }
        body { margin: 0; font-family: Arial, sans-serif; }
        .tab-strip {
            display: flex;
            align-items: flex-end;
            gap: 6px;
            padding: 8px 8px 0 8px;
            border-bottom: 1px solid rgba(0,0,0,0.12);
            background: transparent;
            margin-bottom: 12px;
        }
        .tab {
            position: relative;
            appearance: none;
            border: 1px solid rgba(0,0,0,0.12);
            border-bottom: none;
            background: #f3f4f6;
            color: #1f2937;
            padding: 8px 14px 8px 14px;
            border-radius: 8px 8px 0 0;
            font-size: 13px;
            font-weight: 600;
            line-height: 1.2;
            cursor: pointer;
            white-space: nowrap;
            height: 36px;
        }
        .tab.active {
            background: #ffffff;
            box-shadow: inset 2px 0 0 #4f46e5;
        }
        .tab-close {
            opacity: 0;
            margin-left: 8px;
            color: #4b5563;
            font-weight: 700;
            padding: 0 2px;
            cursor: pointer;
            transition: opacity 0.15s ease;
        }
        .tab:hover .tab-close {
            opacity: 1;
        }
        .tab-panel { display: none; }
        .tab-panel.active { display: block; }
        .student-list {
            background: #ffffff;
            border: 1px solid rgba(0,0,0,0.08);
            border-radius: 8px;
            padding: 12px 14px;
            margin-top: 8px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        }
        .student-list ul {
            margin: 0;
            padding-left: 18px;
        }
        .student-list li {
            margin: 6px 0;
        }
        .course-cell {
            all: unset;
            display: block;
            width: 100%;
            height: 100%;
            min-height: 52px;
            line-height: 52px;
            text-align: center;
            cursor: pointer;
            color: #fff;
            font-weight: bold;
            font-size: 12px;
        }
        </style>
        <div id="schedule-tab-root">
            <div class="tab-strip" id="tab-strip">
                <button class="tab active" type="button" data-tab="main">Weekly Schedule <span aria-hidden="true"></span></button>
            </div>
            <div class="tab-panel active" id="tab-panel-main">{schedule_html}</div>
        </div>
        <script>
        const root = document.getElementById('schedule-tab-root');
        const tabStrip = document.getElementById('tab-strip');
        const mainTab = document.querySelector('[data-tab="main"]');
        const closeTab = (tabId) => {
            const tab = root.querySelector('[data-tab="' + tabId + '"]');
            const panel = root.querySelector('[data-panel="' + tabId + '"]');
            if (tab) tab.remove();
            if (panel) panel.remove();
            if (root.querySelectorAll('.tab').length === 0) {
                mainTab.classList.add('active');
                const mainPanel = document.getElementById('tab-panel-main');
                if (mainPanel) mainPanel.classList.add('active');
            }
        };
        document.querySelectorAll('.course-cell').forEach((btn) => {
            btn.addEventListener('click', function () {
                const course = this.dataset.course;
                const students = JSON.parse(this.dataset.students || '[]');
                const key = 'course-' + course.replace(/[^a-zA-Z0-9]/g, '-');
                if (root.querySelector('[data-tab="' + key + '"]')) {
                    root.querySelector('[data-tab="' + key + '"]').click();
                    return;
                }
                const tabButton = document.createElement('button');
                tabButton.className = 'tab';
                tabButton.type = 'button';
                tabButton.dataset.tab = key;
                tabButton.innerHTML = course + '<span class="tab-close" aria-label="Close tab">×</span>';
                tabButton.addEventListener('click', () => {
                    root.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
                    root.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.remove('active'));
                    tabButton.classList.add('active');
                    const panel = root.querySelector('[data-panel="' + key + '"]');
                    if (panel) panel.classList.add('active');
                });
                tabButton.querySelector('.tab-close').addEventListener('click', (event) => {
                    event.stopPropagation();
                    closeTab(key);
                    if (!root.querySelector('.tab.active')) {
                        mainTab.classList.add('active');
                        document.getElementById('tab-panel-main').classList.add('active');
                    }
                });
                tabStrip.appendChild(tabButton);
                const panel = document.createElement('div');
                panel.className = 'tab-panel';
                panel.dataset.panel = key;
                const studentList = students.length ? '<ul>' + students.map((s) => '<li style="color:' + (s.mismatch ? 'red' : '#1f2937') + ';">' + s.name + '</li>').join('') + '</ul>' : '<p>No students are enrolled in this course.</p>';
                panel.innerHTML = '<div class="student-list"><h4>' + course + '</h4>' + studentList + '</div>';
                root.appendChild(panel);
                root.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
                root.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
                tabButton.classList.add('active');
                panel.classList.add('active');
            });
        });
        mainTab.addEventListener('click', () => {
            root.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
            root.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.remove('active'));
            mainTab.classList.add('active');
            document.getElementById('tab-panel-main').classList.add('active');
        });
        </script>
        """.replace("{schedule_html}", schedule_html)

        components.html(html_string, height=1200, scrolling=True)

    st.caption("Weekly schedule view.")

    if filtered_schedule_data:
        render_schedule_with_tabs(filtered_schedule_data, group_colors)
    else:
        st.markdown(filtered_markdown_text)

# ------------------------------------------------------------
# End of App
# ------------------------------------------------------------
