import sys
sys.path.insert(0, r'C:\Users\Bivek\Desktop\Nursing-Scheduling APp')
from solver import run_ortools_solver

rows = [
    {'Student_Name':'S1','Student_Level':'Junior','Group':'Group1','312L':1,'322L':0,'382L':0,'412L':0,'422L':0,'442L':0},
    {'Student_Name':'S2','Student_Level':'Junior','Group':'Group1','312L':1,'322L':0,'382L':0,'412L':0,'422L':0,'442L':0},
    {'Student_Name':'S3','Student_Level':'Junior','Group':'Group1','312L':0,'322L':1,'382L':0,'412L':0,'422L':0,'442L':0},
    {'Student_Name':'S4','Student_Level':'Junior','Group':'Group1','312L':0,'322L':1,'382L':0,'412L':0,'422L':0,'442L':0},
]
params = {
    'no_of_weeks': 2,
    'no_of_days': 2,
    'no_of_blocks': 1,
    'no_of_labs': 1,
    'block_availability': [[1, 1], [1, 1], [1, 1]],
    'labs_arrangement': [[[1]], [[1]]],
    'objective': 'Preference Weighted Scheduling',
    'preference_weights': [3, 1],
    'course_data': rows,
    'course_columns': ['312L','322L','382L','412L','422L','442L'],
    'course_sessions': [1, 1, 1, 1, 1, 1],
    'course_requirements': {},
}
res = run_ortools_solver(params)
print('status=', res['status'])
for week in res['weekly_schedule']:
    print('week', week['week'])
    for row in week['rows']:
        print(row)
