import solver

params = {
    'no_of_weeks': 1,
    'no_of_days': 6,
    'no_of_blocks': 1,
    'no_of_labs': 1,
    'objective': 'Balanced Schedule Distribution',
    'preference_weights': [1],
    'block_availability': [
        [1, 0, 1, 0, 0, 1],
        [0, 1, 1, 1, 0, 1],
        [0, 1, 0, 1, 1, 1],
    ],
    'labs_arrangement': [
        [[1]], [[1]], [[1]], [[1]], [[1]], [[1]],
    ],
    'course_data': [
        {'Student_Level': 'Accelerated', 'Group': 'Group1', 'CourseA': True},
        {'Student_Level': 'Junior', 'Group': 'Group1', 'CourseA': True},
        {'Student_Level': 'Senior', 'Group': 'Group1', 'CourseA': True},
    ],
    'course_columns': ['CourseA'],
    'course_sessions': [1],
}

result = solver.run_ortools_solver(params)
print(result['status'])
for week in result['weekly_schedule']:
    for row in week['rows']:
        if row[1]:
            print(row[0], '->', row[1])
