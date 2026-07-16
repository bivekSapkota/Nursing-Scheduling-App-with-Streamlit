import streamlit as st
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

no_of_weeks = st.sidebar.number_input("Number of Weeks", min_value=1, max_value=52, value=12)
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

days_list = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
levels_list = ["Senior", "Junior", "Accelerated"]

# Get default block availability pattern
default_block_availability = get_default_block_availability()

block_availability = []

for lvl_idx, lvl in enumerate(levels_list):
    st.sidebar.markdown(f"**{lvl}**")
    row = []
    cols = st.sidebar.columns(len(days_list))
    for i, d in enumerate(days_list):
        default_value = default_block_availability[lvl_idx][i]
        row.append(cols[i].checkbox(d, value=bool(default_value), key=f"{lvl}_{d}"))
    block_availability.append(row)
    st.sidebar.markdown("---")


st.sidebar.markdown("<hr style='border-top:3px solid green;margin:10px 0;'>", unsafe_allow_html=True)
st.sidebar.markdown("### Labs Arrangement (Which Labs Run)")

# Get default labs arrangement pattern
default_labs_arrangement = get_default_labs_arrangement(no_of_blocks, no_of_labs)

labs_arrangement = []

for day_idx, day in enumerate(days_list):
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
    st.warning("⚠️ Sidebar values have changed. Please run the solver again to update the schedule.")

# 3. Run Solver Button
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

    st.subheader("Solver Status")
    st.write(results.get("status", "Unknown"))

    st.subheader("Objective Value")
    st.write(results.get("objective_value", "N/A"))

    markdown_text = results.get("markdown_output", "No schedule returned.")
    
    col1, col2 = st.columns([0.5, 0.5])
    with col1:
        st.subheader("📅 Weekly Schedule")
    with col2:
        st.download_button(
            label="Download Schedule as TXT",
            data=markdown_text,
            file_name="nursing_schedule.txt",
            mime="text/plain"
        )
    
    st.markdown(markdown_text)

# ------------------------------------------------------------
# End of App
# ------------------------------------------------------------
