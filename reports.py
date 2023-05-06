from flask import render_template, redirect, request, current_app, abort
from flask.views import MethodView
import urllib.parse
import yaml

import models
import authorizer

def get_param(k):
  v = request.args.get(k) or request.form.get(k)
  if not v:
    current_app.logger.critical(f"no {k}")
  return v

def listOrder(c):
  if 'instructor' in c:
    return (c['name'],
            c['dayorder'],
            c['instructor'])
  else:
    return (c['name'],
            c['dayorder'])

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
      'user_type' : 'Admin' if auth.email==auth.teacher_email else 'Teacher',
      'classes': classes,
      'rosters': rosters,
      'students': students,
  }

@classmethod
def GetNotTaken(cls, institution, session, auth):
  selected_session = get_param("session-dd")
  if not selected_session:
    selected_session = session

  session_list = models.Session.FetchAll(institution)
  taken = get_param("taken")
  students = models.Students.FetchJson(institution, selected_session)
  current_app.logger.info(f"students = {students}")
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

Reports = {
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
  "not_taken": {
    "view"     		: "Report",
    "route"    		: "/report/not_taken",
    "template" 		: "not_taken.html",
    "get_data"		: GetNotTaken,
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
 }

class ReportView(MethodView):
  name = "attendance_list"
  @classmethod
  def __init__(cls):
    cls.template      = Reports[cls.name]["template"]
    cls.route         = Reports[cls.name]["route"]
    cls.teacher_access= Reports[cls.name].get("teacher_access",False)

  @classmethod
  def GetReport(cls, institution, session, auth):
  	return {}

  @classmethod
  def as_view(cls):
    return super().as_view(cls.name)

  @classmethod
  def get(cls):
    auth = authorizer.Authorizer()
    if not (auth.CanAdministerInstitutionFromUrl() or
    	(cls.teacher_access and auth.HasTeacherAccess())):
      return auth.Redirect()

    institution = get_param("institution")
    session     = get_param("session")
    message     = get_param('message')
    session_query = urllib.parse.urlencode({'institution': institution,
                                            'session': session})

    data = cls.GetReport(institution, session, auth)

    return render_template(cls.template, 
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      session_query=session_query,
      self=request.url,
      data=data,
    )

def ReportClass(classname, get_data=None):
  class NewClass(ReportView):
    name = classname     
    if get_data:
      GetReport = get_data
  return NewClass