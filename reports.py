from flask import render_template, redirect, request, current_app, abort
from flask.views import MethodView
import urllib.parse
import yaml
import datetime
import re

import models
import authorizer
import logic
import error_check_logic

def get_param(k,*args):
  v = request.args.get(k) or request.form.get(k)
  if not v:
    if len(args)<=0:
      current_app.logger.critical(f"no {k}")
    else:
      default = args[0]
      current_app.logger.info(f"no {k}, using default={default}")
      v = default
  return v

def listOrder(c):
  return (c['name'],
          c['dayorder'],
          c['instructor'] if 'instructor' in c else '')

def alphaOrder(c):
  return (c['name'],
          c['instructor'] if 'instructor' in c else '')

def removeTaken(taken, students):
  return [s for s in students if s['email'] not in (taken or [])]

# Strips off leading string "Taken" and possible underscore "_".
# For example, given either "Taken_Boxing" or "TakenBoxing", returns "Boxing"
def getClassNameId(taken):
  y = yaml.safe_load(taken)
  if y and 'group_name' in y[0]:
    g_name = y[0]['group_name']
    if "_" in g_name:
      g_name = removePrefix(g_name, "taken_")
    else:
      g_name = removePrefix(g_name, "taken")
    return g_name
  else:
    return ''

# Removes prefix from str, case-insensitive
def removePrefix(str, prefix):
  if bool(re.match(prefix, str, re.I)):
    return str[len(prefix):]
  return str

# Get grade levels from student list so they aren't hardcoded in the html page.
def getGradeLevels(students):
  # Use Set to get unique grade levels
  grade_set = set()
  for s in students:
    grade_set.add(s['current_grade'])
  # Because sets are not sorted, save into array to sort
  grade_levels = []
  for g in grade_set:
    grade_levels.append([g, "grade"+str(g)])
  grade_levels.sort(reverse=True) # highest grade first
  return grade_levels

def addStudentData(class_roster, students_by_email):
  class_roster['students'] = []
  for e in class_roster['emails']:
    class_roster['students'].append(students_by_email[e])

def augmentClass(institution, session, c, students):
  c['daypart'] = "/".join([str(dp['daypart'])
                           for dp in c['schedule']])
  c['location'] = "/".join([str(dp['location'])
                            for dp in c['schedule']])
  roster = models.ClassRoster.FetchEntity(institution, session, c['id'])
  if not roster: roster = {}
  c['roster'] = [students[email] for email in roster['emails']]
  c['roster'].sort(key=lambda s: s['last'])
  attendance = models.Attendance.FetchJson(institution, session, str(c['id']))
  if attendance:
    # First date is for lookups, second truncated date is for displaying
    c['dates_sorted'] = [[d, d[-5:]] for d in sorted(filter(lambda s: re.match('^[\d-]+$',s), attendance.keys()))]
    c['attendance'] = attendance


@classmethod
def GetClassList(cls, institution, session, auth):
  classes = models.Classes.FetchJson(institution, session)
  dayparts = models.Dayparts.FetchJson(institution, session)
  dp_dict = {} # used for ordering by col then row
  for dp in dayparts:
    dp_dict[dp['name']] = str(dp['col'])+str(dp['row'])
  for c in classes:
    r = models.ClassRoster.FetchEntity(institution, session, c['id'])
    c['num_enrolled'] = len(r['emails'])
    w = models.ClassWaitlist.FetchEntity(institution, session, c['id'])
    c['num_waitlist'] = len(w['emails'])
    c['dayorder'] = dp_dict[c['schedule'][0]['daypart']]
  if classes:
    classes.sort(key=listOrder)

  return {
    'classes': classes,
  }

@classmethod
def GetHomeroom(cls, institution, session, auth):
  students = models.Students.FetchJson(institution, session)
  if students:
    students.sort(key=lambda s: (s['last'], s['first']))

  by_homeroom = {}
  for s in students:
    if s['current_homeroom'] in by_homeroom:
      by_homeroom[s['current_homeroom']].append(s)
    else:
      by_homeroom[s['current_homeroom']] = [s]
  return by_homeroom

@classmethod
def GetAttendanceList(cls, institution, session, auth):
  classes = models.Classes.FetchJson(institution, session)
  dayparts = models.Dayparts.FetchJson(institution, session)
  dp_dict = {} # used for ordering by col then row
  for dp in dayparts:
    dp_dict[dp['name']] = str(dp['col'])+str(dp['row'])
  rosters = {}
  for c in classes:
    rosters[c['id']] = models.ClassRoster.FetchEntity(institution, session, c['id'])
    c['num_locations'] = len(set(s['location'] for s in c['schedule']))
    c['dayorder'] = dp_dict[c['schedule'][0]['daypart']]
  if classes:
    classes.sort(key=listOrder)
  students = models.Students.FetchJson(institution, session)
  for s in students:
    s['email'] = s['email'].lower()
  if students:
    students.sort(key=lambda s: s['last'])
  return {
      'user_type' : 'Teacher' if auth.email==auth.teacher_email else 'Admin',
      'classes': classes,
      'rosters': rosters,
      'students': students,
  }

@classmethod
def GetNotTaken(cls, institution, session, auth):
  selected_session = get_param("session-dd", session)

  session_list = models.Session.FetchAll(institution)
  taken = get_param("taken")
  students = models.Students.FetchJson(institution, selected_session)
  not_taken = removeTaken(taken, students)
  class_name_id = getClassNameId(taken) if taken else ''
  grade_levels = getGradeLevels(students)

  return {
      'selected_session': selected_session,
      'session_list': session_list,
      'taken': taken,
      'not_taken': not_taken,
      'class_name_id': class_name_id,
      'grade_levels': grade_levels,
  }

@classmethod
def GetTaken(cls, institution, session, auth):
  selected_session = get_param("session-dd")
  selected_class = get_param("class-dd")
  session_list = models.Session.FetchAll(institution)
  class_list = []
  if selected_session:
    dayparts = models.Dayparts.FetchJson(institution, selected_session)
    dp_dict = {} # used for ordering by col then row
    for dp in dayparts:
      dp_dict[dp['name']] = str(dp['col'])+str(dp['row'])
    class_list = models.Classes.FetchJson(institution, selected_session)
    for c in class_list:
      c['dayorder'] = dp_dict[c['schedule'][0]['daypart']]
    if class_list: # Unfortunately, models returns '' if none.
      class_list.sort(key=listOrder)
  
  taken = []
  if selected_session and selected_class:
    taken = models.ClassRoster.FetchEntity(institution, selected_session, selected_class)
  return {
    'selected_session': selected_session,
    'selected_class': selected_class,
    'session_list': session_list,
    'class_list': class_list,
    'taken': taken,
  }

@classmethod
def GetSignupCard(cls, institution, session, auth):
  dayparts = models.Dayparts.FetchJson(institution, session)
  dp_dict = {} # used for ordering by col then row
  for dp in dayparts:
    dp_dict[dp['name']] = str(dp['col'])+str(dp['row'])

  classes = models.Classes.FetchJson(institution, session)
  classes_to_print = []
  for c in classes:
    c['dayorder'] = dp_dict[c['schedule'][0]['daypart']]
    if 'exclude_from_catalog' not in c or c['name'] == 'PE':
      classes_to_print.append(c)
  if classes_to_print:
    classes_to_print.sort(key=lambda s: (s['dayorder'], s['name']))
  return {
      'classes': classes_to_print,
  }

@classmethod
def GetSignupMain(cls, institution, session, auth):
  dayparts = models.Dayparts.FetchJson(institution, session)
  dp_dict = {} # used for ordering by col then row
  for dp in dayparts:
    dp_dict[dp['name']] = str(dp['col'])+str(dp['row'])
  classes = models.Classes.FetchJson(institution, session)
  for c in classes:
    c['dayorder'] = dp_dict[c['schedule'][0]['daypart']]
  if classes:
    classes.sort(key=listOrder)
  students = models.Students.FetchJson(institution, session)
  students_by_email = {}
  for s in students:
    s['email'] = s['email'].lower()
    students_by_email[s['email']] = s
  if students:
    students.sort(key=lambda s: s['last'])
  class_rosters = {}
  for c in classes:
    class_roster = models.ClassRoster.FetchEntity(institution, session, c['id'])
    class_roster['emails'].sort()
    addStudentData(class_roster, students_by_email)
    class_rosters[c['id']] = class_roster
  return {
      'classes': classes,
      'class_rosters': class_rosters,
  }

@classmethod
def GetStudentEmails(cls, institution, session, auth):
  classes = models.Classes.FetchJson(institution, session)
  dayparts = models.Dayparts.FetchJson(institution, session)
  dp_dict = {} # used for ordering by col then row
  for dp in dayparts:
    dp_dict[dp['name']] = str(dp['col'])+str(dp['row'])
  rosters = {}
  for c in classes:
    rosters[c['id']] = models.ClassRoster.FetchEntity(institution, session, c['id'])
    c['dayorder'] = dp_dict[c['schedule'][0]['daypart']]
  if classes:
    classes.sort(key=listOrder)
  students = models.Students.FetchJson(institution, session)
  for s in students:
    s['email'] = s['email'].lower()
  if students:
    students.sort(key=lambda s: s['last'])
  return {
    'user_type': 'Teacher' if auth.email==auth.teacher_email else 'Admin',
    'classes': classes,
    'rosters': rosters,
    'students': students,
  }

def getStudentSchedules(institution, session, auth, marked=False):
  dayparts = models.Dayparts.FetchJson(institution, session)
  dp_dict = {} # used for ordering by col then row
  for dp in dayparts:
    dp_dict[dp['name']] = str(dp['col'])+str(dp['row'])

  classes_by_id = {}
  classes = models.Classes.FetchJson(institution, session)
  for c in classes:
    classes_by_id[c['id']] = c
    c['dayorder'] = dp_dict[c['schedule'][0]['daypart']]
  if classes:
    classes.sort(key=listOrder)
  students = models.Students.FetchJson(institution, session)
  # specify UTC timezone just for comparison with date_time from datastore, which came back as UTC. They are actually server time.
  last_modified_overall = datetime.datetime(2000,1,1,tzinfo=datetime.timezone.utc)
  last_modified_overall_str = ''
  homerooms_by_grade = {}
  for s in students:
    if s['current_grade'] in homerooms_by_grade:
      homerooms_by_grade[s['current_grade']].add(s['current_homeroom'])
    else:
      homerooms_by_grade[s['current_grade']] = set([s['current_homeroom']])

    s['email'] = s['email'].lower()
    sched_obj = models.Schedule.FetchEntity(institution, session, s['email'])
    if not sched_obj:
      continue
    s['sched'] = sched_obj['class_ids']
    #s['last_modified'] = sched_obj.date_time
    if sched_obj['date_time']:
      s['last_modified'] = str(sched_obj['date_time'].month) + '/' +\
                           str(sched_obj['date_time'].day) + '/' +\
                           str(sched_obj['date_time'].year) + ' ' +\
                           str(sched_obj['date_time'].hour).zfill(2) + ':' +\
                           str(sched_obj['date_time'].minute).zfill(2)
      if sched_obj['date_time'] > last_modified_overall:
        last_modified_overall = sched_obj['date_time']
        last_modified_overall_str = s['last_modified']
    if (s['sched']):
      s['sched'] = s['sched'].split(',')
      for cId in s['sched']:
        cId_class = classes_by_id[int(cId)]
        for dp in cId_class['schedule']:
          if marked:
            s[dp['daypart']] = cId
          else:
            if dp['location'] == 'Homeroom':
              s[dp['daypart']] = 'Core'
            else:
              s[dp['daypart']] = str(dp['location']) + ', ' + cId_class['name']
            s[dp['daypart']] = s[dp['daypart']][0:26]
  if students:
    students.sort(key=lambda s: s['last'])
  return {
    'user_type': 'Teacher' if auth.email==auth.teacher_email else 'Admin',
    'classes': classes,
    'students': students,
    'last_modified': last_modified_overall_str,
    'homerooms': sorted(homerooms_by_grade, reverse=True),
    'homerooms_by_grade': homerooms_by_grade,
  }

@classmethod
def GetStudentSchedules(cls, institution, session, auth):
  return getStudentSchedules(institution, session, auth)

@classmethod
def GetStudentSchedulesMarked(cls, institution, session, auth):
  return getStudentSchedules(institution, session, auth, marked=True)

@classmethod
def GetComingSoon(cls, institution, session, auth):
  email = auth.student_email
  closed_msg = models.Closed.Fetch(institution, session)
  return {
    'closed_msg' : closed_msg,
  }

@classmethod
def GetViewAbsence(cls, institution, session, auth):
  selected_date = get_param("selected_date",datetime.date.today())
  selected_daypart = get_param('selected_daypart','All')

  dayparts = models.Dayparts.FetchJson(institution, session)
  classes = models.Classes.FetchJson(institution, session)
  students = models.Students.FetchJson(institution, session)

  if not students: students = []
  students_dict = {}
  for s in students:
    s['email'] = s['email'].lower()
    students_dict[s['email']] = s

  classes_to_display = []
  if not classes: classes = []
  for c in classes:
    #if 'Core' not in c['name']: #TODO: remove Core classes in a more general way
    if selected_daypart == 'All':
      augmentClass(institution, session, c, students_dict)
      classes_to_display.append(c)
    else:
      for s in c['schedule']:
        if selected_daypart in s['daypart']:
          augmentClass(institution, session, c, students_dict)
          classes_to_display.append(c)
  classes_to_display.sort(key=alphaOrder)

  return {
    'user_type' : 'Teacher' if auth.email==auth.teacher_email else 'Admin',
    'selected_date'   : selected_date,
    'selected_daypart': selected_daypart,
    'dayparts'  : current_app.json.dumps(dayparts),
    'classes'   : current_app.json.dumps(classes_to_display),
  }

@classmethod
def GetViewAttendance(cls, institution, session, auth):
  selected_daypart = get_param('selected_daypart','All')

  dayparts = models.Dayparts.FetchJson(institution, session)
  students = models.Students.FetchJson(institution, session)
  if not students: students = []
  students_dict = {}
  for s in students:
    s['email'] = s['email'].lower()
    students_dict[s['email']] = s

  classes_to_display = []
  classes = models.Classes.FetchJson(institution, session)
  if not classes: classes = []
  for c in classes:
    #if 'Core' not in c['name']: #TODO: remove Core classes in a more general way
    if selected_daypart == 'All':
      augmentClass(institution, session, c, students_dict)
      classes_to_display.append(c)
    else:
      for s in c['schedule']:
        if selected_daypart in s['daypart']:
          augmentClass(institution, session, c, students_dict)
          classes_to_display.append(c)
  classes_to_display.sort(key=alphaOrder)

  return {
    'user_type' : 'Teacher' if auth.email==auth.teacher_email else 'Admin',
    'dayparts' : dayparts,
    'selected_daypart': selected_daypart,
    'classes': classes_to_display,
  }


def getClassesByHomeroom(institution, session, classes, selected_daypart, students_dict, room_num):
  classes_to_display = []
  for c in classes:
    class_dayparts = [s['daypart'] for s in c['schedule']]
    if selected_daypart == 'All' or selected_daypart in class_dayparts:
      roster = models.ClassRoster.FetchEntity(institution, session, c['id'])
      if not roster:
        continue
      roster_by_homeroom = [students_dict[email] for email in roster['emails']
                            if students_dict[email]['current_homeroom'] == room_num]
      if len(roster_by_homeroom) == 0:
        continue
      newClass = dict(c)
      newClass['roster'] = roster_by_homeroom
      newClass['roster'].sort(key=lambda s: s['last']) 
      attendance = models.Attendance.FetchJson(institution, session, str(c['id']))
      if attendance:
        # First date is for lookups, second truncated date is for displaying
        newClass['dates_sorted'] = [[d, d[-5:]] for d in sorted(filter(lambda s: re.match('^[\d-]+$',s), attendance.keys()))]
        newClass['attendance'] = attendance
      newClass['daypart'] = "/".join([str(dp['daypart'])
                                 for dp in c['schedule']])
      newClass['location'] = "/".join([str(dp['location'])
                                  for dp in c['schedule']])
      classes_to_display.append(newClass)
  classes_to_display.sort(key=alphaOrder)
  return classes_to_display

@classmethod
def GetViewByHomeroom(cls, institution, session, auth):
  selected_homeroom = get_param('selected_homeroom','All')
  selected_daypart  = get_param('selected_daypart' ,'All')

  dayparts = models.Dayparts.FetchJson(institution, session)
  students = models.Students.FetchJson(institution, session)
  if not students: students = []
  students_dict = {}
  homeroom_nums = [] # unique homeroom numbers
  for s in students:
    s['email'] = s['email'].lower()
    students_dict[s['email']] = s
    if s['current_homeroom'] not in homeroom_nums:
      homeroom_nums.append(s['current_homeroom'])
  homeroom_nums.sort()
  classes = models.Classes.FetchJson(institution, session)
  if not classes: classes = []

  classes_by_homeroom = {}
  if selected_homeroom == 'All':
    for room in homeroom_nums:
      classes_by_homeroom[room] = getClassesByHomeroom(
        institution, session, classes, selected_daypart, students_dict, room)
  else:
    classes_by_homeroom[selected_homeroom] = getClassesByHomeroom(
      institution, session, classes, selected_daypart, students_dict, int(selected_homeroom))

  return {
    'user_type' : 'Teacher' if auth.email==auth.teacher_email else 'Admin',
    'dayparts' : dayparts,
    'selected_daypart': selected_daypart,
    'selected_homeroom': selected_homeroom,
    'homeroom_nums': homeroom_nums,
    'classes_by_homeroom': classes_by_homeroom,
  }

@classmethod
def GetCourses(cls, institution, session, auth):
  dayparts = models.Dayparts.FetchJson(institution, session)
  if not dayparts:
    dayparts = []
  classes = models.Classes.FetchJson(institution, session)
  try:
    _ = [c for c in classes]
  except TypeError:
    classes = []
  classes_by_daypart = {}
  dayparts_ordered = []

  max_row = max([daypart['row'] for daypart in dayparts])
  max_col = max([daypart['col'] for daypart in dayparts])

  # order the dayparts by row and col specified in yaml
  for row in range(max_row):
    dayparts_ordered.append([])
    for col in range(max_col):
      found_daypart = False
      for dp in dayparts:
        if dp['row'] == row+1 and dp['col'] == col+1:
          dayparts_ordered[row].append(dp['name'])
          found_daypart = True
      if found_daypart == False:
        dayparts_ordered[row].append('')
  for daypart in dayparts:
    classes_by_daypart[daypart['name']] = []
  classes_by_id = {}
  use_full_description = auth.CanAdministerInstitutionFromUrl()
  for c in classes:
    class_id = str(c['id'])
    classes_by_id[class_id] = c
    c['hover_text'] = logic.GetHoverText(institution, session, use_full_description, c)
    c['description'] = logic.GetHTMLDescription(institution, session, c)
    for daypart in [s['daypart'] for s in c['schedule']]:
      if daypart in classes_by_daypart:
        classes_by_daypart[daypart].append(c)
  for daypart in classes_by_daypart:
    classes_by_daypart[daypart].sort(key=lambda c:c['name'])

  config = models.Config.Fetch(institution, session)

  return {
    'user_type' : 'Teacher' if auth.email==auth.teacher_email else 'Admin',
    'classes_by_daypart': classes_by_daypart,
    'dayparts_ordered': dayparts_ordered,
    'classes_by_id': classes_by_id,
    'html_desc': config['htmlDesc'],
  }

def orderScheduleByDP(sched_obj, classes_by_id):
  schedule_by_dp = {}
  sched_list = sched_obj.get("class_ids").split(',')
  for cId in sched_list:
    c = classes_by_id[int(cId)]
    for dp in c['schedule']:
      schedule_by_dp[dp['daypart']] = {
          'name': c['name'],
          'location': dp['location'],
          'fitness': c.get('fitness', False)}
  return schedule_by_dp

def getErrorMsgs(schedule_by_dp, len_dayparts, institution, session):
  err_msgs = []
  if (len(schedule_by_dp) != len_dayparts):
    err_msgs.append("Incomplete schedule")
  err_msgs.extend(getFitnessErrorMsgs(schedule_by_dp))
  return err_msgs

# Takes a schedule object
#   {'Mon A': {'name': 'PE',
#              'fitness': True,},
#    . . .}
# Returns list of error messages, [] if no error
def getFitnessErrorMsgs(schedule_by_dp):
  num_PE = num_Dance = num_fitness = num_PE_MT = num_PE_TF = 0
  err_msgs = []
  for dp_key, dp_obj in schedule_by_dp.items():
    if (dp_obj['name'] == 'PE'):
      num_PE += 1
      if (dp_key.startswith('Mon') or
          dp_key.startswith('Tues')):
        num_PE_MT += 1
      if (dp_key.startswith('Thurs') or
          dp_key.startswith('Fri')):
        num_PE_TF += 1
    if (dp_obj['name'] == 'Dance'):
      num_Dance += 1
    if (dp_obj['fitness'] == True):
      num_fitness += 1
  if (num_PE < 1 and num_Dance < 2):
    err_msgs.append("At least one PE or Dance required.")
  if num_PE > 2:
    err_msgs.append("Too many PE's, maximum is two.")
  if num_fitness < 2:
    err_msgs.append("At least two PE or PE alternatives required.")
  if num_fitness > 2:
    err_msgs.append("Too many PE or PE alternatives, maximum is two.")
  if num_PE_MT > 1 or num_PE_TF > 1:
    err_msgs.append("Not allowed to have two PE's on Mon/Tues or Thurs/Fri.")
  return err_msgs

@classmethod
def GetErrorRegistration(cls, institution, session, auth):
  ALL_GRADES = 100
  err_list = [] # list of tuples where
                #   first element contains a list of error messages
                #   second element is the student object
                #   third element is the student schedule object by daypart

  grade_level = get_param("grade_level", None)
  if grade_level:
    grade_level = int(grade_level)
    len_dayparts = len(models.Dayparts.FetchJson(institution, session))

    classes = models.Classes.FetchJson(institution, session)
    classes_by_id = {}
    for c in classes:
      classes_by_id[c['id']] = c

    students = models.Students.FetchJson(institution, session)
    students.sort(key=lambda s: s['current_homeroom'])
    for s in students:
      if (grade_level != ALL_GRADES) and (s['current_grade'] != grade_level):
        continue
      sched_obj = models.Schedule.FetchEntity(institution, session,
                                            s['email'].lower())
      #current_app.logger.info(f"sched_obj=%s" % sched_obj.get("class_ids"))
      if not sched_obj or not sched_obj.get("class_ids"):
        err_list.append((['Missing schedule'], s, {}))
        continue # Entire schedule is missing,
                 # don't bother checking for further errors
      schedule_by_dp = orderScheduleByDP(sched_obj, classes_by_id)
      err_msgs = getErrorMsgs(schedule_by_dp, len_dayparts, institution, session)
      if err_msgs != []:
        err_list.append((err_msgs, s, schedule_by_dp))
  # else no button was clicked, don't do anything

  return {
    'user_type' : 'Teacher' if auth.email==auth.teacher_email else 'Admin',
    'err_list'  : err_list,
  }


@classmethod
def GetVerification(cls, institution, session, auth):
  student_info = auth.GetStudentInfo(institution, session)
  if student_info == None:
    student_info = {'first': 'No Data', 'last': '', 'current_grade': 'No Data'}
  return {
    'student_name' : student_info.get('first','')+" "+student_info.get('last',''),
    'current_grade': student_info['current_grade'],
  }

@classmethod
def GetPreregistration(cls, institution, session, auth):
  welcome_msg = models.Materials.Fetch(institution, session)
  return {
    'welcome_msg' : welcome_msg,
  }

def _getSchedule(institution, session, auth, html=False):
  email = auth.student_email
  dayparts = models.Dayparts.FetchJson(institution, session)
  if not dayparts:
    dayparts = []
  schedule = models.Schedule.Fetch(institution, session, email)
  schedule = schedule.split(",")
  if schedule and schedule[0] == "":
    schedule = schedule[1:]
  classes = models.Classes.FetchJson(institution, session)
  try:
    _ = [c for c in classes]
  except TypeError:
    classes = []
  schedule_by_daypart = {}
  dayparts_ordered = []

  max_row = max([daypart['row'] for daypart in dayparts])
  max_col = max([daypart['col'] for daypart in dayparts])
      
  # order the dayparts by row and col specified in yaml
  for row in range(max_row):
    dayparts_ordered.append([])
    for col in range(max_col):
      found_daypart = False
      for dp in dayparts:
        if dp['row'] == row+1 and dp['col'] == col+1:
          dayparts_ordered[row].append(dp['name'])
          found_daypart = True
      if found_daypart == False:
        dayparts_ordered[row].append('')

  for daypart in dayparts:
    schedule_by_daypart[daypart['name']] = []
  admin_flag = auth.CanAdministerInstitutionFromUrl()
  classes_by_id = {}
  for c in classes:
    if str(c['id']) in schedule:
      for daypart in [s['daypart'] for s in c['schedule']]:
        if daypart in schedule_by_daypart:
          schedule_by_daypart[daypart] = c
      if html:
        classes_by_id[str(c['id'])] = c
        c['description'] = logic.GetHTMLDescription(institution, session, c)
  config = models.Config.Fetch(institution, session)
  #current_app.logger.info(f"student={auth.student_entity}")
  return {
    'student': auth.student_entity,
    'dayparts': dayparts,
    'schedule_by_daypart': schedule_by_daypart,
    'dayparts_ordered': dayparts_ordered,
    'classes_by_id': classes_by_id,
    'html_desc': config['htmlDesc'],
  }

@classmethod
def GetPrintSchedule(cls, institution, session, auth):
  return _getSchedule(institution, session, auth, html=False)

@classmethod
def GetPostregistration(cls, institution, session, auth):
  return _getSchedule(institution, session, auth, html=True)

@classmethod
def GetImpersonation(cls, institution, session, auth):
  setup_status = error_check_logic.Checker.getStatus(institution, session)
  students = models.Students.FetchJson(institution, session)
  return {
    'setup_status': setup_status,
    'students': students,
  }

Reports = {
  "class_list": {
    "view"     : "Report",
    "route"    : "/class_list",
    "template" : "class_list.html",
    "get_data" : GetClassList,
  },
  "attendance_list": {
    "view"     		: "Report",
    "route"    		: "/report/attendance_list",
    "template" 		: "attendance_list.html",
    "teacher_access": True,
    "get_data"		: GetAttendanceList,
  },
  "homeroom": {
    "view"     		: "Report",
    "route"    		: "/report/homeroom",
    "template" 		: "homeroom.html",
    "get_data"		: GetHomeroom,
  },
  "label": {
    "view"     		: "Report",
    "route"    		: "/report/label",
    "template" 		: "label.html",
    "teacher_access": True,
    "get_data"		: GetAttendanceList,
  },
  "signup_card": {
    "view"     		: "Report",
    "route"    		: "/report/signup_card",
    "template" 		: "signup_card.html",
    "get_data"		: GetSignupCard,
  },
  "signup_main": {
    "view"     		: "Report",
    "route"    		: "/report/signup_main",
    "template" 		: "signup_main.html",
    "get_data"		: GetSignupMain,
  },
  "student_emails": {
    "view"        : "Report",
    "route"       : "/report/student_emails",
    "template"    : "student_emails.html",
    "teacher_access": True,
    "get_data"    : GetStudentEmails,
  },
  "student_schedules": {
    "view"        : "Report",
    "route"       : "/report/student_schedules",
    "template"    : "student_schedules.html",
    "teacher_access": True,
    "get_data"    : GetStudentSchedules,
  },
  "student_schedules_marked": {
    "view"        : "Report",
    "route"       : "/report/student_schedules_marked",
    "template"    : "student_schedules_marked.html",
    "teacher_access": True,
    "get_data"    : GetStudentSchedulesMarked,
  },
  "not_taken": {
    "view"        : "Report",
    "route"       : "/report/not_taken",
    "template"    : "not_taken.html",
    "get_data"    : GetNotTaken,
  },
  "taken": {
    "view"        : "Report",
    "route"       : "/report/taken",
    "template"    : "taken.html",
    "get_data"    : GetTaken,
  },
  "coming_soon": {
    "view"        : "Report",
    "route"       : "/coming_soon",
    "template"    : "coming_soon.html",
    "student_access": True,
    "get_data"    : GetComingSoon,
  },
  "view_absence": {
    "view"        : "Report",
    "route"       : "/teacher/view_absence",
    "template"    : "view_absence.html",
    "teacher_access": True,
    "get_data"    : GetViewAbsence,
  },
  "view_attendance": {
    "view"        : "Report",
    "route"       : "/teacher/view_attendance",
    "template"    : "view_attendance.html",
    "teacher_access": True,
    "get_data"    : GetViewAttendance,
  },
  "view_by_homeroom": {
    "view"        : "Report",
    "route"       : "/teacher/view_by_homeroom",
    "template"    : "view_by_homeroom.html",
    "teacher_access": True,
    "get_data"    : GetViewByHomeroom,
  },
  "courses": {
    "view"        : "Report",
    "route"       : "/teacher/courses",
    "template"    : "courses.html",
    "teacher_access": True,
    "get_data"    : GetCourses,
  },
  "error_registration": {
    "view"        : "Report",
    "route"       : "/error_registration",
    "template"    : "error_registration.html",
    "teacher_access": True,
    "get_data"    : GetErrorRegistration,
  },
  "verification": {
    "view"        : "Report",
    "route"       : "/verification",
    "template"    :  "verification.html",
    "admimurlaccess": False,
    "student_access": True,
    "get_data"    : GetVerification,
  },
  "preregistration": {
    "view"        : "Report",
    "route"       : "/preregistration",
    "template"    :  "preregistration.html",
    "admimurlaccess": False,
    "student_access": True,
    "student_page"  : "materials",
    "get_data"    : GetPreregistration,
  },
  "postregistration": {
    "view"        : "Report",
    "route"       : "/postregistration",
    "template"    :  "postregistration.html",
    "admimurlaccess": False,
    "student_access": True,
    "student_page"  : "final",
    "get_data"    : GetPostregistration,
  }, 
  "print_schedule": {
    "view"        : "Report",
    "route"       : "/print_schedule",
    "template"    :  "print_schedule.html",
    "admimurlaccess": False,
    "student_access": True,
    "get_data"    : GetPrintSchedule,
  },
  "impersonation": {
    "view"        : "Report",
    "route"       : "/impersonation",
    "template"    :  "impersonation.html",
    "get_data"    : GetImpersonation,
  },
 }

'''
This Taken and the Not Taken page are used for generating
student groups. Listed below are different types of Student Groups
and how they are created.

Manually generated group - This group is usually chosen during the
pre-signup process. Instructors provide the selective team with
a list of pre-qualified students. This group type is not generated
from this page. Examples: Yearbook, French, Shakespeare To Go.

Taken 'XYZ' - Students who have previously taken class XYZ. From this
page, you can generate a student list from a specified class during a
specified session. You may need to combine lists from multiple
sessions as some students may have taken the class in a previous
semester or year. Examples: students who have taken Boxing qualify
for Advanced Boxing, Woodworking qualify for Advanced Woodworking.

Not Taken 'XYZ' - Students who have not yet taken class XYZ. To
generate this list, first create the list of students who HAVE taken
the class. (Remember, you may need to combine lists from multiple
sessions.) Then copy and paste the combined list into the Not Taken
page which will generate the inverse of the Taken list using students
from the current session. Examples: no repeat classes such as Boxing,
Woodworking, Cooking Block A, Cooking Block B.

Students from a particular grade or homeroom. Example: DowlingScience
is open only to students not from Rm 29. Use grade and homeroom instead
of Student Groups for this type of filter.

Auto-generated groups of lottery winners. These are generated from
the lottery page, not here.
'''

class ReportView(MethodView):
  name = "attendance_list"
  @classmethod
  def __init__(cls):
    cls.template      = Reports[cls.name]["template"]
    cls.route         = Reports[cls.name]["route"]
    cls.admimurlaccess= Reports[cls.name].get("admimurlaccess",True)
    cls.student_access= Reports[cls.name].get("student_access",False)
    cls.teacher_access= Reports[cls.name].get("teacher_access",False)
    cls.student_page  = Reports[cls.name].get("student_page"  ,None)

  @classmethod
  def GetReport(cls, institution, session, auth):
  	return {}

  @classmethod
  def as_view(cls):
    return super().as_view(cls.name)

  @classmethod
  def get(cls):
    auth = authorizer.Authorizer()
    if not ((cls.admimurlaccess and auth.CanAdministerInstitutionFromUrl()) or
            (cls.teacher_access and auth.HasTeacherAccess()) or
            (cls.student_access and auth.HasStudentAccess())):
      return auth.Redirect()

    institution = get_param("institution")
    session     = get_param("session")
    message     = get_param('message', None)
    session_query = urllib.parse.urlencode({'institution': institution,
                                            'session': session})

    if cls.student_page and not auth.HasPageAccess(institution, session, cls.student_page):
      return auth.RedirectTemporary(institution, session)

    data = cls.GetReport(institution, session, auth)

    return render_template(cls.template, 
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      session_query=session_query,
      self=request.url,
      data=data,
      impersonation=f"&student={auth.student_email}" if auth.email!=auth.student_email else "",
    )

def ReportClass(classname, get_data=None):
  class NewClass(ReportView):
    name = classname     
    if get_data:
      GetReport = get_data
  return NewClass