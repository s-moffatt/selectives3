from flask import render_template, redirect, request, current_app, jsonify, abort, g as app_ctx
from flask.views import MethodView
import urllib.parse
import csv
from io import StringIO
import random

import schemas
import error_check_logic
import logic
import models
import authorizer

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

def getStudentInfo(student_dict, email):
  if email in student_dict:
    s = student_dict[email]
    if 'edtechid' in s:
      return [s['first'],
              s['last'],
              str(s['current_grade']),
              str(s['current_homeroom']),
              str(s['edtechid'])]
    else:
      return [s['first'],
              s['last'],
              str(s['current_grade']),
              str(s['current_homeroom'])]
  else:
    current_app.logger.error('getStudentInfo: ' + email + ' not found in dictionary')
    return ['']

def getClassObj(class_dict, line):
  if len(line) < 1:
    return {}
  id = line[0]
  if id in class_dict:
    return class_dict[id]
  else:
    return {}

def getStudentEmail(student_dict, line):
  if len(line) < 10:
    return ''
  first = line[6]
  last = line[7]
  grade = line[8]
  homerm = line[9]

  key = first + last + grade + homerm
  if key in student_dict:
    return student_dict[key]
  else:
    return ''

def alphaOrder(c):
  return (c['name'],
          c['dayorder'],
          c['instructor'])

def listOrder(c):
  return (c['name'],
          c['dayorder'],
          c['instructor'] if 'instructor' in c else '')

def buildRoster(c, roster, attendance, students):
  r = {}
  r['name'] = c['name']
  if 'instructor' in c:
    r['instructor'] = c['instructor']
  r['daypart'] = "/".join([str(dp['daypart'])
                           for dp in c['schedule']])
  r['location'] = "/".join([str(dp['location'])
                            for dp in c['schedule']])
  r['emails'] = roster['emails']
  student_list = [students[email] for email in roster['emails']]
  student_list.sort(key=(lambda s: s['last']))
  r['students'] = student_list
  if attendance:
    r['submitted_by'] = attendance['submitted_by']
    # for students not found (withdrawn from school), set last = '_None'
    r['present'] = [students[email] if email in students\
                    else {'email': email, 'last': '_None'}\
                    for email in attendance['present'] ]
    r['present'].sort(key=(lambda s: s['last']))
    r['absent'] = [students[email] if email in students\
                   else {'email': email, 'last': '_None'}\
                   for email in attendance['absent']]
    r['absent'].sort(key=(lambda s: s['last']))
    if 'present_adults' in attendance:
      r['present_adults'] = [adult for adult in attendance['present_adults']]
    if 'absent_adults' in attendance:
      r['absent_adults'] = [adult for adult in attendance['absent_adults']]
    r['submitted_date'] = attendance['submitted_date']
    if 'note' in attendance:
      r['note'] = attendance['note']
    else:
      r['note'] = ''
  return r

def buildClasses(auth, dayparts, classes, my_classes, other_classes):
  dp_dict = {}
  for dp in dayparts:
    dp_dict[dp['name']] = str(dp['col'])+str(dp['row'])
  for c in classes:
    c['dayorder'] = dp_dict[c['schedule'][0]['daypart']]
    c['daypart'] = "/".join([str(dp['daypart'])
                             for dp in c['schedule']])
    if 'instructor' not in c:
      c['instructor'] = 'none'
    hasOwner = False
    if 'owners' in c:
      for owner in c['owners']:
        if auth.teacher_email and owner == auth.teacher_email:
          hasOwner = True
          my_classes.append(c)
    if not hasOwner:
      other_classes.append(c)
  my_classes.sort(key=alphaOrder)
  other_classes.sort(key=alphaOrder)

def addStudentData(class_roster, students):
  class_roster['students'] = []
  for e in class_roster['emails']:
    for s in students:
      if (s['email'].lower() == e.lower()):
        class_roster['students'].append(s)

def ClearPrefs(institution, session):
  students = models.Students.FetchJson(institution, session)
  classes = models.Classes.FetchJson(institution, session)
  for student in students:
    email = student['email']
    #TODO find the list of eligible classes for each student
    models.Preferences.Store(email, institution, session,
                             [], [], [])

def RandomPrefs(institution, session):
  students = models.Students.FetchJson(institution, session)
  classes = models.Classes.FetchJson(institution, session)
  for student in students:
    email = student['email']
    eligible_class_ids = logic.EligibleClassIdsForStudent(
        institution, session, student, classes)
    eligible_class_ids = set(eligible_class_ids)
    want = random.sample(eligible_class_ids, min(len(eligible_class_ids),random.randint(1,5)))
    dontwant = random.sample(eligible_class_ids.difference(want), min(len(eligible_class_ids.difference(want)),random.randint(1,5)))
    # want = [str(item) for item in want]
    # dontwant = [str(item) for item in dontwant]
    models.Preferences.Store(email, institution, session,
                             want, [], dontwant)

def ClearAllSchedules(institution, session):
  students = models.Students.FetchJson(institution, session)
  for student in students:
    empty_class_ids = ''
    models.Schedule.Store(institution, session,
                          student['email'].lower(),
                          empty_class_ids)
  classes = models.Classes.FetchJson(institution, session)
  for class_obj in classes:
    no_student_emails = ""
    models.ClassRoster.Store(institution, session,
                             class_obj,
                             no_student_emails)

@classmethod
def getNone(cls, institution, session, auth):
  return None

@classmethod
def WelcomeSetupSave(cls, institution, session, auth):
  data = request.form.get("data")
  if not data:
    current_app.logger.critical(f"no {cls.name} data")
  models.Welcome.Store(data)
  error_check_logic.Checker.setStatus(institution, session, 'UNKNOWN')
  return data

@classmethod
def WelcomeSetupGetData(cls, institution, session, auth):
  data = cls.model.Fetch()
  if not data and cls.sample:
    with open(cls.sample) as x: data = x.read()
  return data

@classmethod
def RostersSave(cls, institution, session, auth):
  rosters = request.form.get("data")
  if not rosters:
    current_app.logger.critical("no rosters")

  class_put_dict = {} # {79:{'name':'3D Printing', etc.}}
  student_put_dict = {} # {'firstlast623': 'first.last19@mydiscoverk8.org'}
  student_put_sched = {} # {'first.last19@mydiscoveryk8.org': [5,6,29,79,10]}

  classes = models.Classes.FetchJson(institution, session)
  for c in classes:
    key = str(c['id'])
    class_put_dict[key] = c

  students = models.Students.FetchJson(institution, session)
  for s in students:
    key = s['first'] +\
          s['last'] +\
          str(s['current_grade']) +\
          str(s['current_homeroom'])
    student_put_dict[key] = s['email'].strip().lower()
    student_put_sched[s['email'].strip().lower()] = []

  # Replace class rosters and build student_put_sched
  rosters = csv.reader(StringIO(rosters))
  curr_class_obj = {}
  student_emails = ''
  for line in rosters:
    # If line contains only student info
    if line != [] and line[0] == '':
      curr_email = getStudentEmail(student_put_dict, line).strip().lower()
      if curr_email in student_put_sched:
        student_put_sched[curr_email].append(curr_class_obj['id'])
        student_emails += curr_email + ','
      else:
        current_app.logger.error("Invalid email: " + curr_email +\
                      "at line: " + str(line))
    # Else, the line contains class data i.e. start of a new class
    # Or it's the last empty line []
    else:
      # If currently processing a roster, store it.
      if curr_class_obj != {}:
        models.ClassRoster.Store(institution, session,
                                 curr_class_obj,
                                 student_emails)
      # Get new class data and start building new email list
      student_emails = ''
      curr_class_obj = getClassObj(class_put_dict, line)
      if curr_class_obj == {} and line != []:
        current_app.logger.error("curr_class_obj: " + str(curr_class_obj) +\
                      " at line: " + str(line))
      curr_email = getStudentEmail(student_put_dict, line).strip().lower()
      if curr_email in student_put_sched:
        student_put_sched[curr_email].append(curr_class_obj['id'])
        student_emails += curr_email + ','
      elif line != []:
        current_app.logger.error("email: " + curr_email +\
                      "at line: " + str(line))

  # Replace student schedules using dictionary built above
  for email_key in student_put_sched:
    models.Schedule.Store(institution, session,
                          email_key,
                          ','.join(str(cid) for cid in student_put_sched[email_key]))

@classmethod
def RostersGetData(cls, institution, session, auth):
  rosters = ''
  classes = models.Classes.FetchJson(institution, session)
  students = models.Students.FetchJson(institution, session)
  classes = sorted(classes, key=lambda c: c['name'])

  student_get_dict = {} # {'John.Smith19@mydiscoveryk8.org': {'first':'John', 'last':'Smith', etc.}}
  for s in students:
    student_get_dict[s['email'].strip().lower()] = s

  for c in classes:
    class_roster = models.ClassRoster.FetchEntity(institution, session,
                                                  c['id'])
    if (len(class_roster['emails']) <= 0):
      continue
    rosters += '"' + str(c['id']) + '",'
    rosters += '"' + c['name'] + '",'
    if 'instructor' in c and c['instructor'] != None:
      rosters += '"' + c['instructor'] + '",'
    else:
      rosters += '"",'
    rosters += '"' + str(c['max_enrollment']) + '",'
    rosters += '"' + '/'.join(s['daypart'] for s in c['schedule']) + '",'
    rosters += '"' + '/'.join(str(s['location']) for s in c['schedule']) + '"'

    roster_students = [getStudentInfo(student_get_dict, s) for s in class_roster['emails']]
    roster_students = sorted(roster_students)
    if (len(roster_students) > 0):
      for student_data_field in roster_students[0]:
        rosters += ',"' + student_data_field + '"'
    rosters += '\n'
    for s in roster_students[1:]:
      if s:
        rosters += '"","","","","","","' + s[0] + '"'
        for student_data_field in s[1:]:
          rosters += ',"' + student_data_field + '"'
        rosters += '\n'
      else:
        current_app.logger.error("Student in roster_students is empty string!")
  return rosters

@classmethod
def ConfigGetJdata(cls, institution, session, auth):
  db_version = models.DBVersion.Fetch(institution, session)
  config = models.Config.Fetch(institution, session)
  return {
    'db_version': db_version,
    'config'    : config
  }

@classmethod
def ConfigSave(cls, institution, session, auth):
  displayRoster = request.form.get("displayRoster")
  if not displayRoster:
    current_app.logger.critical("no displayRoster")
  htmlDesc = request.form.get("htmlDesc")
  if not htmlDesc:
    current_app.logger.critical("no htmlDesc")
  twoPE = request.form.get("twoPE")
  if not twoPE:
    current_app.logger.critical("no twoPE")
  current_app.logger.info("*********************")
  current_app.logger.info(twoPE)
  models.Config.Store(institution, session, displayRoster, htmlDesc, twoPE)
  error_check_logic.Checker.setStatus(institution, session, 'UNKNOWN')
  return {
    'displayRoster':displayRoster, 
    'htmlDesc': htmlDesc,
    'twoPE': twoPE
  }

@classmethod
def AutoRegisterAfterSave(cls, institution, session, auto_register):
  if request.form.get("action") == "Register":
    auto_register = models.AutoRegister.FetchJson(institution, session)
    students = models.Students.FetchJson(institution, session)
    for auto_class in auto_register:
      class_id = str(auto_class['class_id'])
      if (auto_class['applies_to'] == []): # applies to all students
        for s in students:
          if not ('exempt' in auto_class and s['email'] in auto_class['exempt']):
            logic.AddStudentToClass(institution, session, s['email'].lower(), class_id)
            current_app.logger.info(f"added {s['email']} to {class_id}")
      for grp in auto_class['applies_to']:
        if 'current_grade' in grp:
          for s in students:
            if (s['current_grade'] == grp['current_grade']):
              if not ('exempt' in auto_class and s['email'] in auto_class['exempt']):
                logic.AddStudentToClass(institution, session, s['email'].lower(), class_id)
                current_app.logger.info(f"added {s['email']} to {class_id}")
        if 'group' in grp:
          student_groups = models.GroupsStudents.FetchJson(institution, session)
          for sg in student_groups:
            if (sg['group_name'] == grp['group']):
              for s_email in sg['emails']:
                if not ('exempt' in auto_class and s_email in auto_class['exempt']):
                  logic.AddStudentToClass(institution, session, s_email.lower(), class_id)
                  current_app.logger.info(f"added {s_email} to {class_id}")
        if 'email' in grp:
          # We have no way to prevent an exempt field here, so we should check for it.
          # But there really is no point to an exempt field when applies_to is email.
          if not ('exempt' in auto_class and grp['email'] in auto_class['exempt']):
            logic.AddStudentToClass(institution, session, grp['email'].lower(), class_id)
            current_app.logger.info(f"added {grp['email']} to {class_id}")

@classmethod
def AutoRegisterGetJdata(cls, institution, session, auth):
  auto_register = models.AutoRegister.FetchJson(institution, session)
  classes = models.Classes.FetchJson(institution, session)
  dayparts = models.Dayparts.FetchJson(institution, session)
  dp_dict = {} # used for ordering by col then row
  for dp in dayparts:
    dp_dict[dp['name']] = str(dp['col'])+str(dp['row'])
  for c in classes:
    r = models.ClassRoster.FetchEntity(institution, session, c['id'])
    c['num_enrolled'] = len(r['emails'])
    c['dayorder'] = dp_dict[c['schedule'][0]['daypart']]
  if classes:
    classes.sort(key=listOrder)

  students = models.Students.FetchJson(institution, session)
  grades_dict = {}
  for s in students:
    grade = s['current_grade']
    grades_dict[str(grade)] = grades_dict.get(str(grade), 0) + 1
    grades_dict['All'] = grades_dict.get('All', 0) + 1
  grades = []
  for g in sorted(grades_dict, reverse=True):
    grades.append([g, grades_dict[g]])

  groups = models.GroupsStudents.FetchJson(institution, session)
  if groups:
    groups.sort(key=lambda g: g['group_name'])
  for g in groups:
    g['num_students'] = len(g['emails'])

  return {
    "auto_register": auto_register,
    "classes": classes,
    "grades": grades,
    "groups": groups,
  }

@classmethod
def TakeAttendancePostAction(cls, institution, session, auth):
  submitted_date = get_param("submitted_date")
  c_id           = get_param("c_id")
  present_kids   = get_param("present_kids", "")
  absent_kids    = get_param("absent_kids" , "")
  present_adults = get_param("present_adults", "")
  absent_adults  = get_param("absent_adults" , "")
  note           = get_param("note"        , "")

  present_kids   = [e for e in present_kids.split(',') if e]
  absent_kids    = [e for e in absent_kids.split(',') if e]
  present_adults = [e for e in present_adults.split(',') if e]
  absent_adults  = [e for e in absent_adults.split(',') if e]

  teachers = models.Teachers.FetchJson(institution, session)
  teacher = logic.FindUser(auth.email, teachers)
  if not teacher:
    teacher = {}
    teacher['first'] = ""
    teacher['last'] = auth.email

  attendance = models.Attendance.FetchJson(institution, session, c_id)
  # Clobber existing data, or if none, create a new element
  attendance[submitted_date] = {
    "present": present_kids,
    "absent": absent_kids,
    "present_adults": present_adults,
    "absent_adults": absent_adults,
    "submitted_by": " ".join([teacher['first'], teacher['last']]),
    "submitted_date": submitted_date,
    "note": note,
  }
  models.Attendance.Store(institution, session, c_id, attendance)
  return cls.RedirectToSelf(institution, session, f"saved {cls.name} data", url_args={
    'selected_cid' : c_id,
    'selected_date': submitted_date,   
  })

@classmethod
def TakeAttendanceGetJdata(cls, institution, session, auth):
  selected_cid  = get_param('selected_cid',0)
  selected_date = get_param('selected_date',None)
  session_query = urllib.parse.urlencode({'institution': institution,
                                    'session': session,
                                    'current_cid': selected_cid})

  dayparts = models.Dayparts.FetchJson(institution, session)
  classes = models.Classes.FetchJson(institution, session)
  if not classes: classes = []
  my_classes = []
  other_classes = []
  selected_class = []
  buildClasses(auth, dayparts, classes, my_classes, other_classes)

  students = models.Students.FetchJson(institution, session)
  # create a dictionary of students to avoid multiple loops in buildRoster
  students_dict = {}
  if not students: students = []
  for s in students:
    s['email'] = s['email'].lower()
    students_dict[s['email']] = s

  my_roster = {}
  if selected_cid != 0 and selected_date:
    selected_attendance = models.Attendance.FetchJson(institution, session,
                                                      selected_cid)
    current_app.logger.info(f"selected_attendance={selected_attendance}")
    attendance = selected_attendance.get(selected_date, None)
    #if selected_date in selected_attendance:
    #  attendance = selected_attendance[selected_date]
    #else:
    #  attendance = None
    current_app.logger.info(f"attendance={attendance}")  
    selected_class = next(c for c in classes if c['id'] == int(selected_cid))
    selected_roster = models.ClassRoster.FetchEntity(institution, session, selected_cid)
    if not selected_roster:
      selected_roster = {}

    my_roster = buildRoster(selected_class, selected_roster,
                            attendance,
                            students_dict)
  # my_classes and other_classes are lists of classes
  # my_roster is a dictionary:
  # {'name': 'Circuit Training',
  #  'instructor': 'name',
  #    ...,
  #  'emails': [list of student emails],
  #  'students': [list of student objects based on the emails]}
  return {
    'user_type' : 'Teacher' if auth.email==auth.teacher_email else 'Admin',
    'current_cid': selected_cid,
    'current_date': selected_date,
    'session_query': session_query,
    'my_classes': my_classes,
    'my_roster': current_app.json.dumps(my_roster),
    'other_classes': other_classes,
    'selected_class': current_app.json.dumps(selected_class)
  }

@classmethod
def ClassRosterPostAction(cls, institution, session, auth):
  class_id = get_param("class_id")
  action   = get_param("action")

  if action == "remove student":
    email = get_param("email")
    logic.RemoveStudentFromClass(institution, session, email, class_id)
    return cls.RedirectToSelf(institution, session, "removed %s" % email, url_args={
      'class_id': class_id,
    })

  if action == "run lottery":
    cid = get_param("cid")
    app_ctx.class_id = cid

    candidates = get_param("candidates","")
    if candidates == "":
      candidates = []
    else:
      candidates = candidates.split(",")
    logic.RunLottery(institution, session, cid, candidates)
    return cls.RedirectToSelf(institution, session, "lottery %s" % cid, url_args={
      'class_id': cid,
    })

  return cls.RedirectToSelf(institution, session, "Unknown action", url_args={
    'class_id': class_id,
  })

@classmethod
def ClassRosterGetJdata(cls, institution, session, auth):
  class_id = get_param("class_id")

  class_roster = models.ClassRoster.FetchEntity(institution, session, class_id)
  class_roster['emails'].sort()
  students = models.Students.FetchJson(institution, session)
  addStudentData(class_roster, students)
  classes = models.Classes.FetchJson(institution, session)
  class_details = ''
  for c in classes:
    if (str(c['id']) == class_id):
      class_details = c
      break
  return {
    'class_roster'    : class_roster,
    'students'        : students,
    'class_details'   : class_details
  }

@classmethod
def ClassWaitlistPostAction(cls, institution, session, auth):
  class_id = get_param("class_id")
  app_ctx.class_id = class_id

  action   = get_param("action")

  if action == "remove student":
    email = get_param("email")
    logic.RemoveStudentFromWaitlist(institution, session, email, class_id)
    return cls.RedirectToSelf(institution, session, "removed %s" % email, url_args={
      'class_id': class_id,
    })

  return cls.RedirectToSelf(institution, session, "Unknown action", url_args={
    'class_id': class_id,
  })

@classmethod
def ClassWaitlistGetJdata(cls, institution, session, auth):
  class_id = get_param("class_id")

  waitlist = models.ClassWaitlist.FetchEntity(institution, session, class_id)
  waitlist['emails'].sort()
  students = models.Students.FetchJson(institution, session)
  addStudentData(waitlist, students)
  classes = models.Classes.FetchJson(institution, session)
  class_details = ''
  for c in classes:
    if (str(c['id']) == class_id):
      class_details = c
      break
  return {
    'class_waitlist'  : waitlist,
    'students'        : students,
    'class_details'   : class_details
  }

@classmethod
def ErrorCheckPostAction(cls, institution, session, auth):
  checker = error_check_logic.Checker(institution, session)
  checker.RunUpgradeScript()
  return cls.RedirectToSelf(institution, session, "upgrade")

@classmethod
def ErrorCheckGetJdata(cls, institution, session, auth):
  checker = error_check_logic.Checker(institution, session)
  setup_status, error_chk_detail = checker.ValidateSetup()
  return {
    'setup_status': setup_status,
    'error_chk_detail': error_chk_detail,
  }

@classmethod
def SchedulerPostAction(cls, institution, session, auth):
  action = get_param("action")
  if action == "Clear Prefs":
    ClearPrefs(institution, session)
  if action == "Random Prefs":
    RandomPrefs(institution, session)
  if action == "Clear Schedules":
    ClearAllSchedules(institution, session)
  return cls.RedirectToSelf(institution, session, "saved classes")

@classmethod
def SchedulerGetJdata(cls, institution, session, auth):
  num_students = len(models.Students.FetchJson(institution, session))
  return {
    'num_students': num_students,
  }

@classmethod
def PreferencesPostAction(cls, institution, session, auth):
  email = auth.student_email
  want = get_param("want","").split(",")
  if want[0] == '':
    want.pop(0)
  dontcare = get_param("dontcare","").split(",")
  if dontcare[0] == '':
    dontcare.pop(0)
  dontwant = get_param("dontwant","").split(",")
  if dontwant[0] == '':
    dontwant.pop(0)
  current_app.logger.info(f"want={want}, dontcare={dontcare}, dontwant={dontwant}")
  models.Preferences.Store(email, institution, session,
                           want, dontcare, dontwant)
  if get_param("Save", None) == "Save":
    current_app.logger.info("Form Saved")
  else:
    current_app.logger.info("Auto Save")
  return cls.RedirectToSelf(institution, session, "Saved Preferences", url_args={
    'student': email,
  })

@classmethod
def PreferencesGetJdata(cls, institution, session, auth):
  current_app.logger.info(f"auth={auth}")
  classes = models.Classes.FetchJson(institution, session)
  try:
    _ = [c for c in classes]
  except TypeError:
    classes = []
  classes_by_id = {}
  use_full_description = auth.CanAdministerInstitutionFromUrl()
  for c in classes:
    class_id = str(c['id'])
    class_name = c['name']
    class_desc = logic.GetHoverText(institution, session, use_full_description, c)
    classes_by_id[class_id] = {'name': class_name,
                               'description': class_desc }
  if not classes_by_id:
    classes_by_id['0'] = {'name': 'None', 'desc': 'None'}
  eligible_class_ids = set(logic.EligibleClassIdsForStudent(
      institution, session, auth.student_entity, classes))

  prefs = models.Preferences.FetchEntity(
      auth.student_email, institution, session)
  want_ids     = prefs.get("want","").split(',')
  dontcare_ids = prefs.get("dontcare","").split(',')
  dontwant_ids = prefs.get("dontwant","").split(',')

  new_class_ids = eligible_class_ids.difference(want_ids)
  new_class_ids = new_class_ids.difference(dontcare_ids)
  new_class_ids = new_class_ids.difference(dontwant_ids)
  dontcare_ids = list(new_class_ids) + dontcare_ids
  if dontcare_ids[len(dontcare_ids)-1] == '':
    dontcare_ids.pop()

  def RemoveDeletedClasses(class_ids):
    for class_id in class_ids:
      if class_id in eligible_class_ids:
        yield class_id

  want_ids = list(RemoveDeletedClasses(want_ids))
  dontcare_ids = list(RemoveDeletedClasses(dontcare_ids))
  dontwant_ids = list(RemoveDeletedClasses(dontwant_ids))
  current_app.logger.info('want: ' + ','.join(want_ids));
  current_app.logger.info('dont want: ' + ','.join(dontwant_ids));
  current_app.logger.info('dont care: ' + ','.join(dontcare_ids));
  return {
    'classes': classes_by_id,
    'student': auth.student_entity,
    'want_ids': want_ids,
    'dontwant_ids': dontwant_ids,
    'dontcare_ids': dontcare_ids,
  }

@classmethod
def SchedulePostAction(cls, institution, session, auth):
  email = auth.student_email
  class_id = get_param("class_id")
  action   = get_param("action")

  if action == "add":
    logic.AddStudentToClass(institution, session, email, class_id)
  if action == "del":
    logic.RemoveStudentFromClass(institution, session, email, class_id)
  schedule = models.Schedule.Fetch(institution, session, email)
  schedule = schedule.split(",")
  if schedule and schedule[0] == "":
    schedule = schedule[1:]
  return jsonify(schedule)

@classmethod
def ScheduleGetJdata(cls, institution, session, auth):
  email = auth.student_email
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
  eligible_classes = logic.EligibleClassIdsForStudent(
      institution, session, auth.student_entity, classes)
  for daypart in dayparts:
    classes_by_daypart[daypart['name']] = []
  classes_by_id = {}
  use_full_description = auth.CanAdministerInstitutionFromUrl()
  for c in classes:
    class_id = str(c['id'])
    if class_id not in eligible_classes:
      continue
    classes_by_id[class_id] = c
    c['hover_text'] = logic.GetHoverText(institution, session, use_full_description, c)
    c['description'] = logic.GetHTMLDescription(institution, session, c)
    for daypart in [s['daypart'] for s in c['schedule']]:
      if daypart in classes_by_daypart:
        classes_by_daypart[daypart].append(c)
  for daypart in classes_by_daypart:
    classes_by_daypart[daypart].sort(key=lambda c:c['name'])
    
  schedule = models.Schedule.Fetch(institution, session, email)
  schedule = schedule.split(",")
  if schedule and schedule[0] == "":
    schedule = schedule[1:]

  config = models.Config.Fetch(institution, session)
  return {
    "student": auth.student_entity,
    #"dayparts": dayparts,
    "classes_by_daypart": classes_by_daypart,
    "dayparts_ordered"  : dayparts_ordered,
    "schedule"          : current_app.json.dumps(schedule),
    "classes_by_id"     : classes_by_id,
    "html_desc"         : config['htmlDesc'],
    #"impersonation"     : f"&student={auth.student_email}" if auth.email!=auth.student_email else ""
  }

Views = {
  # plain text (csv) data
  "Rosters": {
    "view"     : "Form",
    "route"    : "/rosters",
    "template" :  "rosters.html",
    "schema"   : None,
    "model"    : None,
    "sample"   : None,
    "save"     : RostersSave,
    "get_data" : RostersGetData,
    "get_jdata": getNone,
  },
  # yaml form pages
  "Dayparts": {
    "view"    : "Form",
    "route"   : "/dayparts",
    "template":  "dayparts.html",
    "schema"  : schemas.Dayparts,
    "model"   : models.Dayparts,
    "sample"  : "samples/dayparts.yaml"
  },
  "Classes": {
    "view"    : "Form",
    "route"   : "/classes",
    "template":  "classes.html",
    "schema"  : schemas.Classes,
    "model"   : models.Classes,
    "sample"  : "samples/classes.yaml"
  },
  "Students": {
    "view"    : "Form",
    "route"   : "/students",
    "template":  "students.html",
    "schema"  : schemas.Students,
    "model"   : models.Students,
    "sample"  : "samples/students.yaml"
  },
  "Teachers": {
    "view"    : "Form",
    "route"   : "/teachers",
    "template":  "teachers.html",
    "schema"  : schemas.Teachers,
    "model"   : models.Teachers,
    "sample"  : "samples/teachers.yaml"
  },
  "GroupsClasses": {
    "view"    : "Form",
    "route"   : "/groups_classes",
    "template":  "groups_classes.html",
    "schema"  : schemas.ClassGroups,
    "model"   : models.GroupsClasses,
    "sample"  : "samples/groups_classes.yaml"
  },
  "GroupsStudents": {
    "view"    : "Form",
    "route"   : "/groups_students",
    "template":  "groups_students.html",
    "schema"  : schemas.StudentGroups,
    "model"   : models.GroupsStudents,
    "sample"  : "samples/groups_students.yaml"
  },
  "Requirements": {
    "view"    : "Form",
    "route"   : "/requirements",
    "template":  "requirements.html",
    "schema"  : schemas.Requirements,
    "model"   : models.Requirements,
    "sample"  : "samples/requirements.yaml"
  },
  "ServingRules": {
    "view"    : "Form",
    "route"   : "/serving_rules",
    "template":  "serving_rules.html",
    "schema"  : schemas.ServingRules,
    "model"   : models.ServingRules,
    "sample"  : "samples/serving_rules.yaml"
  },
  "AutoRegister": {
    "view"      : "Form",
    "route"     : "/auto_register",
    "template"  :  "auto_register.html",
    "schema"    : schemas.AutoRegister,
    "model"     : models.AutoRegister,
    "sample"    : "samples/auto_register.yaml",
    "after_save": AutoRegisterAfterSave,
    "get_jdata" : AutoRegisterGetJdata,
  },
  # HTML data
  "WelcomeSetup": {
    "view"     : "Form",
    "route"    : "/welcome_setup",
    "template" :  "welcome_setup.html",
    "schema"   : None,
    "model"    : models.Welcome,
    "sample"   : "samples/welcome.html",
    "save"     : WelcomeSetupSave,
    "get_data" : WelcomeSetupGetData,
    "get_jdata": getNone,
  },
  "Closed": {
    "view"     : "Form",
    "route"    : "/closed",
    "template" :  "closed.html",
    "schema"   : None,
    "model"    : models.Closed,
    "sample"   : "samples/closed.html",
    "get_jdata": getNone,
  },
  "Materials": {
    "view"     : "Form",
    "route"    : "/materials",
    "template" :  "materials.html",
    "schema"   : None,
    "model"    : models.Materials,
    "sample"   : "samples/materials.html",
    "get_jdata": getNone,
  },
  # json data
  "Config": {
    "view"     : "Form",
    "route"    : "/config",
    "template" :  "config.html",
    "schema"   : None,
    "model"    : None,
    "sample"   : None,
    "save"     : ConfigSave,
    "get_data" : getNone,
    "get_jdata": ConfigGetJdata,
  },
  # json data, more complex redirect after post
  "TakeAttendance": {
    "view"        : "Form",
    "route"       : "/teacher/take_attendance",
    "template"    : "take_attendance.html",  
    "schema"      : None,
    "model"       : None,
    "sample"      : None, 
    "get_data"    : getNone,
    "get_jdata"   : TakeAttendanceGetJdata,
    "post_action" : TakeAttendancePostAction,
    "teacher_access": True,
  },
  "ClassRoster": {
    "view"       : "Form",
    "route"      : "/class_roster",
    "template"   :  "class_roster.html",  
    "schema"     : None,
    "model"      : None,
    "sample"     : None, 
    "get_data"   : getNone,
    "get_jdata"  : ClassRosterGetJdata,
    "post_action": ClassRosterPostAction,
  },
  "ClassWaitlist": {
    "view"       : "Form",
    "route"      : "/class_waitlist",
    "template"   :  "class_waitlist.html", 
    "schema"     : None,
    "model"      : None,
    "sample"     : None,  
    "get_data"   : getNone,
    "get_jdata"  : ClassWaitlistGetJdata,
    "post_action": ClassWaitlistPostAction,
  },
  "ErrorCheck": {
    "view"       : "Form",
    "route"      : "/error_check",
    "template"   :  "error_check.html",   
    "schema"     : None,
    "model"      : None,
    "sample"     : None,
    "get_data"   : getNone,
    "get_jdata"  : ErrorCheckGetJdata,
    "post_action": ErrorCheckPostAction,
  },
  "Scheduler": {
    "view"       : "Form",
    "route"      : "/scheduler",
    "template"   :  "scheduler.html",   
    "schema"     : None,
    "model"      : None,
    "sample"     : None,
    "get_data"   : getNone,
    "get_jdata"  : SchedulerGetJdata,
    "post_action": SchedulerPostAction,
  },
  "Preferences": {
    "view"       : "Form",
    "route"      : "/preferences",
    "template"   :  "preferences.html",   
    "schema"     : None,
    "model"      : None,
    "sample"     : None,
    "get_data"   : getNone,
    "get_jdata"  : PreferencesGetJdata,
    "post_action": PreferencesPostAction,
    "admimurlaccess": False,
    "student_access": True,
    "student_page"  : "preferences",
  },
  "Schedule": {
    "view"       : "Form",
    "route"      : "/schedule",
    "template"   :  "schedule.html",   
    "schema"     : None,
    "model"      : None,
    "sample"     : None,
    "get_data"   : getNone,
    "get_jdata"  : ScheduleGetJdata,
    "post_action": SchedulePostAction,
    "admimurlaccess": False,
    "student_access": True,
    "student_page"  : "schedule",
    "use_403"       : True,
  },
#app.add_url_rule('/schedule', view_func=schedule.Schedule.as_view('schedule'))
}

class FormView(MethodView):
  name = "Dayparts"
  @classmethod
  def __init__(cls):
    cls.schema        = Views[cls.name]["schema"]
    cls.model         = Views[cls.name]["model"]
    cls.template      = Views[cls.name]["template"]
    cls.route         = Views[cls.name]["route"]
    cls.sample        = Views[cls.name]["sample"]
    cls.admimurlaccess= Views[cls.name].get("admimurlaccess",True)
    cls.student_access= Views[cls.name].get("student_access",False)
    cls.teacher_access= Views[cls.name].get("teacher_access",False)
    cls.student_page  = Views[cls.name].get("student_page"  ,None)
    cls.use_403       = Views[cls.name].get("use_403"       ,False)

  @classmethod
  def as_view(cls):
    return super().as_view(cls.name)

  @classmethod
  def RedirectToSelf(cls, institution, session, message, url_args={}):
    args = {'message': message, 
            'institution': institution,
            'session': session}
    args.update(url_args)
    return redirect(f'{cls.route}?%s' % urllib.parse.urlencode(args))

  @classmethod
  def Save(cls, institution, session, auth):
    data = get_param("data", None)
    if not data:
      current_app.logger.critical(f"no {cls.name} data")
    if cls.schema:
      validator = cls.schema()
      data = validator.Update(data)
    cls.model.Store(institution, session, data)
    error_check_logic.Checker.setStatus(institution, session, 'UNKNOWN')
    return data

  @classmethod
  def AfterSave(cls, institution, session, data):
    pass

  @classmethod
  def PostAction(cls, institution, session, auth):
    data = cls.Save(institution, session, auth)
    cls.AfterSave(institution, session, data)
    return cls.RedirectToSelf(institution, session, f"saved {cls.name} data")

  @classmethod
  def post(cls):
    auth = authorizer.Authorizer()
    if not ((cls.admimurlaccess and auth.CanAdministerInstitutionFromUrl()) or
            (cls.teacher_access and auth.HasTeacherAccess()) or
            (cls.student_access and auth.HasStudentAccess())):
      if cls.use_403:
        abort(403)
      return auth.Redirect()

    institution = get_param("institution")
    session     = get_param("session")

    if cls.student_page and not auth.HasPageAccess(institution, session, cls.student_page):
      if cls.use_403:
        abort(403)
      return auth.RedirectTemporary(institution, session)

    return cls.PostAction(institution, session, auth)

  @classmethod
  def GetData(cls, institution, session, auth):
    data = cls.model.Fetch(institution, session)
    if not data and cls.sample:
      with open(cls.sample) as x: data = x.read()
    return data

  @classmethod
  def GetJdata(cls, institution, session, auth):
    return cls.model.FetchJson(institution, session)

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

    setup_status = error_check_logic.Checker.getStatus(institution, session)

    data = cls.GetData(institution, session, auth)
    jdata = cls.GetJdata(institution, session, auth)

    return render_template(cls.template, 
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      setup_status=setup_status,
      session_query=session_query,
      data=data,
      jdata=jdata,
      self=request.url,
      impersonation=f"&student={auth.student_email}" if auth.email!=auth.student_email else "",
    )

def FormClass(classname, post_action=None, save=None, after_save=None, get_data=None, get_jdata=None):
  class NewClass(FormView):
    name = classname     
    if post_action:
      PostAction = post_action  
    if save:
      Save = save
    if after_save:
      AfterSave = after_save
    if get_data:
      GetData = get_data
    if get_jdata:
      GetJdata = get_jdata
  return NewClass