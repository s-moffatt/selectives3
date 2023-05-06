from flask import render_template, redirect, request, current_app, abort
from flask.views import MethodView
import urllib.parse
import csv
from io import StringIO

import schemas
import error_check_logic
import logic
import models
import authorizer

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
    return ''

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

def listOrder(c):
  if 'instructor' in c:
    return (c['name'],
            c['dayorder'],
            c['instructor'])
  else:
    return (c['name'],
            c['dayorder'])

@classmethod
def getNone(cls, institution, session):
  return None

@classmethod
def WelcomeSetupSave(cls, institution, session):
  data = request.form.get("data")
  if not data:
    current_app.logger.critical(f"no {cls.name} data")
  models.Welcome.Store(data)
  error_check_logic.Checker.setStatus(institution, session, 'UNKNOWN')
  return data

@classmethod
def RostersSave(cls, institution, session):
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
def RostersGetData(cls, institution, session):
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
def ClassListGetJdata(cls, institution, session):
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
  current_app.logger.info(f"classes={classes}")
  return classes

@classmethod
def ConfigGetJdata(cls, institution, session):
  db_version = models.DBVersion.Fetch(institution, session)
  config = models.Config.Fetch(institution, session)
  return {
    'db_version': db_version,
    'config'    : config
  }

@classmethod
def ConfigSave(cls, institution, session):
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
def AutoRegisterGetJdata(cls, institution, session):
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
    grades_dict[str(grade)] = grades_dict.get(grade, 0) + 1
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

Views = {
  "Config": {
    "view"     : "Form",
    "route"    : "/config",
    "template" : "config.html",
    "schema"   : None,
    "model"    : models.Config,
    "sample"   : None,
    "save"     : ConfigSave,
    "get_data" : getNone,
    "get_jdata": ConfigGetJdata,
  },
  "Dayparts": {
    "view"    : "Form",
    "route"   : "/dayparts",
    "template": "dayparts.html",
    "schema"  : schemas.Dayparts,
    "model"   : models.Dayparts,
    "sample"  : "samples/dayparts.yaml"
  },
  "Classes": {
    "view"    : "Form",
    "route"   : "/classes",
    "template": "classes.html",
    "schema"  : schemas.Classes,
    "model"   : models.Classes,
    "sample"  : "samples/classes.yaml"
  },
  "Students": {
    "view"    : "Form",
    "route"   : "/students",
    "template": "students.html",
    "schema"  : schemas.Students,
    "model"   : models.Students,
    "sample"  : "samples/students.yaml"
  },
  "Teachers": {
    "view"    : "Form",
    "route"   : "/teachers",
    "template": "teachers.html",
    "schema"  : schemas.Teachers,
    "model"   : models.Teachers,
    "sample"  : "samples/teachers.yaml"
  },
  "GroupsClasses": {
    "view"    : "Form",
    "route"   : "/groups_classes",
    "template": "groups_classes.html",
    "schema"  : schemas.ClassGroups,
    "model"   : models.GroupsClasses,
    "sample"  : "samples/groups_classes.yaml"
  },
  "GroupsStudents": {
    "view"    : "Form",
    "route"   : "/groups_students",
    "template": "groups_students.html",
    "schema"  : schemas.StudentGroups,
    "model"   : models.GroupsStudents,
    "sample"  : "samples/groups_students.yaml"
  },
  "Requirements": {
    "view"    : "Form",
    "route"   : "/requirements",
    "template": "requirements.html",
    "schema"  : schemas.Requirements,
    "model"   : models.Requirements,
    "sample"  : "samples/requirements.yaml"
  },
  "AutoRegister": {
    "view"      : "Form",
    "route"     : "/auto_register",
    "template"  : "auto_register.html",
    "schema"    : schemas.AutoRegister,
    "model"     : models.AutoRegister,
    "sample"    : "samples/auto_register.yaml",
    "after_save": AutoRegisterAfterSave,
    "get_jdata" : AutoRegisterGetJdata,
  },
  "ServingRules": {
    "view"    : "Form",
    "route"   : "/serving_rules",
    "template": "serving_rules.html",
    "schema"  : schemas.ServingRules,
    "model"   : models.ServingRules,
    "sample"  : "samples/serving_rules.yaml"
  },
  "Rosters": {
    "view"    : "Form",
    "route"   : "/rosters",
    "template": "rosters.html",
    "schema"  : None,
    "model"   : None,
    "sample"  : None,
    "save"    : RostersSave,
    "get_data" : RostersGetData,
    "get_jdata": getNone,
  },
  "WelcomeSetup": {
    "view"    : "Form",
    "route"   : "/welcome_setup",
    "template": "welcome_setup.html",
    "schema"  : None,
    "model"   : models.Welcome,
    "sample"  : "samples/welcome.html",
    "save"    : WelcomeSetupSave,
    "get_jdata": getNone,
  },
  "Closed": {
    "view"    : "Form",
    "route"   : "/closed",
    "template": "closed.html",
    "schema"  : None,
    "model"   : models.Closed,
    "sample"  : "samples/closed.html",
    "get_jdata": getNone,
  },
  "Materials": {
    "view"    : "Form",
    "route"   : "/materials",
    "template": "materials.html",
    "schema"  : None,
    "model"   : models.Materials,
    "sample"  : "samples/materials.html",
    "get_jdata": getNone,
  },
  "ClassList": {
    "view"    : "Form",
    "route"   : "/class_list",
    "template": "class_list.html",
    "schema"  : None,
    "model"   : None,
    "sample"  : None,
    "get_data": getNone,
    "get_jdata": ClassListGetJdata,
    "disallow_post": True
  },

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
    cls.disallow_post = Views[cls.name].get("disallow_post",False)

  @classmethod
  def as_view(cls):
    return super().as_view(cls.name)

  @classmethod
  def UrlArgs(cls):
    return {}

  @classmethod
  def RedirectToSelf(cls, institution, session, message):
    args = {'message': message, 
            'institution': institution,
            'session': session}
    args.update(cls.UrlArgs())
    return redirect(f'{cls.route}?%s' % urllib.parse.urlencode(args))

  @classmethod
  def Save(cls, institution, session):
    data = request.form.get("data")
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
  def post(cls):
    if cls.disallow_post:
      abort(405) #METHOD NOT ALLOWED

    auth = authorizer.Authorizer()
    if not auth.CanAdministerInstitutionFromUrl():
      return auth.Redirect()

    institution = request.args.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.args.get("session")
    if not session:
      current_app.logger.critical("no session")

    data = cls.Save(institution, session)
    cls.AfterSave(institution, session, data)

    return cls.RedirectToSelf(institution, session, f"saved {cls.name} data")

  @classmethod
  def GetData(cls, institution, session):
    data = cls.model.Fetch(institution, session)
    if not data and cls.sample:
      with open(cls.sample) as x: data = x.read()
    return data

  @classmethod
  def GetJdata(cls, institution, session):
    return cls.model.FetchJson(institution, session)

  @classmethod
  def get(cls):
    auth = authorizer.Authorizer()
    if not auth.CanAdministerInstitutionFromUrl():
      return auth.Redirect()

    institution = request.args.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.args.get("session")
    if not session:
      current_app.logger.critical("no session")

    message = request.args.get('message')
    session_query = urllib.parse.urlencode({'institution': institution,
                                      'session': session})
    setup_status = error_check_logic.Checker.getStatus(institution, session)

    data = cls.GetData(institution, session)
    jdata = cls.GetJdata(institution, session)

    return render_template(cls.template, 
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      setup_status=setup_status,
      session_query=session_query,
      data=data,
      jdata=jdata,
      self=request.url
    )

def FormClass(classname, save=None, after_save=None, get_data=None, get_jdata=None, url_args=None):
  class NewClass(FormView):
    name = classname     
    if save:
      Save = save
    if after_save:
      AfterSave = after_save
    if get_data:
      GetData = get_data
    if get_jdata:
      GetJdata = get_jdata
    if url_args:
      UrlArgs = url_args
  return NewClass