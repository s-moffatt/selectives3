from datetime import datetime
from flask import current_app


from google.cloud import datastore

db = datastore.Client()
GLOBAL_KEY = db.key("global", "global")

class Model:
  @classmethod
  def key(cls, *path_args, **kwargs):
    return db.key(cls.__name__, *path_args, **kwargs)   

  @classmethod
  def Store(cls, *path_args, data={}, **kwargs):
    current_app.logger.info("%s.Store: %s", cls.__name__, str(path_args))
    entity = datastore.Entity(key=cls.key(*path_args, **kwargs))
    data.update({'date_time': datetime.now()})
    if data:
      entity.update(data)
    db.put(entity)

  @classmethod
  def Delete(cls, *path_args, **kwargs):
    db.delete(cls.key(*path_args, **kwargs))

  @classmethod
  def FetchEntity(cls, *path_args, **kwargs):
    entity = db.get(cls.key(*path_args, **kwargs))
    if entity:
      return entity
    entity = datastore.Entity(key=cls.key(*path_args, **kwargs))
    return entity

  @classmethod
  def Fetch(cls,order=['__key__'],ancestor=None,filters=[],limit=None):
    query = db.query(kind=cls.__name__,ancestor=ancestor,order=order)
    for i in filters:
      query.add_filter(*i)
    results = list(query.fetch(limit=limit))
    current_app.logger.info("%s.Fetch: %d results", cls.__name__, sum(1 for i in results))
    return results

  @classmethod
  def FetchAll(cls,key=None):
    results = cls.Fetch()
    return [i.key.id_or_name for i in results]

  @classmethod
  def GetParents(cls,child):
    results = cls.Fetch()
    if results == None:
      return []
    elif len(results) <= 0:
      return []
    else:
      return {i.key.parent.id_or_name:1 for i in results}.keys()

#-------------------------------------
class RecentAccess(Model):
  pass

class GlobalAdmin(Model):
  """email addresses for users with full access to the site."""
  pass

class Institution(Model):
  """Institution name"""
  pass

class Welcome(Model):
  @classmethod
  def Fetch(cls,*args, **kwargs):
    return super().Fetch(*args, **kwargs) or ""

#-------------------------------------
class Model_InstitutionChild(Model):
  @classmethod
  def parent_cls(cls):
   return "Institution"

  @classmethod
  def key(cls, institution, child):
    return db.key(cls.parent_cls(), institution, cls.__name__, child)

  @classmethod
  def parent_key(cls, institution):
    return db.key(cls.parent_cls(), institution)

  @classmethod
  def FetchAllEntities(cls,*parent_key_args):
    return cls.Fetch(ancestor=cls.parent_key(*parent_key_args))

  @classmethod
  def FetchAll(cls,*parent_key_args):
    results = cls.FetchAllEntities(*parent_key_args)
    return [i.key.id_or_name for i in results]

  @classmethod
  def GetInstitutionNames(cls, child):
    return cls.GetParents(child)

#-------------------------------------
class Admin(Model_InstitutionChild):
  pass

class Session(Model_InstitutionChild):
  @classmethod
  def enable(cls, institution, session):
    'Set only one session active at a time'
    changed = []
    for entity in cls.FetchAllEntities(institution):
      if entity.key.id_or_name == session and not entity['active']:
        entity['active'] = True
        changed.append(entity)
      elif entity.key.id_or_name != session and entity['active']:
        entity['active'] = False
        changed.append(entity)
    db.put_multi(changed)

  @classmethod
  def disable(cls, institution, session):
    'Set target session as inactive'
    entity = cls.FetchEntity(institution, session)
    entity['active'] = False

  @classmethod
  def servicing_session(cls, institution):
    'Get the active session (should only have 1 or 0 session active)'
    ss = cls.Fetch(cls,ancestor=cls.parent_key(institution),filters=[("active", "=", True)])
    return ss.id_or_name if ss else None

#-------------------------------------
class Model_SessionChild(Model_InstitutionChild):
  @classmethod
  def parent_cls(cls):
   return "Session"

  @classmethod
  def parent2_cls(cls):
   return "Institution"

  @classmethod
  def key(cls, institution, session, child):
    return db.key(cls.parent2_cls(), institution, cls.parent_cls(), session, cls.__name__, child)

  @classmethod
  def parent_key(cls, institution, session):
    return super().key(institution, session)

#-------------------------------------


#class ServingRules(ndb.Model):
#  """List of serving rules in yaml and json format."""
#  data = ndb.TextProperty()
#  jdata = ndb.JsonProperty()
#
#  @classmethod
#  @timed
#  def serving_rules_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   ServingRules, "serving_rules")
#
#  @classmethod
#  @timed
#  def FetchJson(cls, institution, session):
#    serving_rules = ServingRules.serving_rules_key(institution, session).get()
#    if serving_rules:
#      return serving_rules.jdata
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    serving_rules = ServingRules.serving_rules_key(institution, session).get()
#    if serving_rules:
#      return serving_rules.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, sr_data):
#    serving_rules = ServingRules(data = sr_data,
#                                 jdata = yaml.load(sr_data))
#    serving_rules.key = ServingRules.serving_rules_key(institution, session_name)
#    serving_rules.put()
#
#
#
#class Dayparts(ndb.Model):
#  """Examples: Monday AM, or M-W-F 8am-9am"""
#  data = ndb.TextProperty()
#  jdata = ndb.JsonProperty()
#
#  @classmethod
#  @timed
#  def dayparts_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Dayparts, "dayparts")
#
#  @classmethod
#  @timed
#  def FetchJson(cls, institution, session):
#    dayparts = Dayparts.dayparts_key(institution, session).get()
#    if dayparts:
#      return dayparts.jdata
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    dayparts = Dayparts.dayparts_key(institution, session).get()
#    if dayparts:
#      return dayparts.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, dayparts_data):
#    dayparts = Dayparts(data = dayparts_data,
#                        jdata = yaml.load(dayparts_data))
#    dayparts.key = Dayparts.dayparts_key(institution, session_name)
#    dayparts.put()
#
#
#class Classes(ndb.Model):
#  """List of classes in yaml and json format."""
#  data = ndb.TextProperty()
#  jdata = ndb.JsonProperty()
#
#  @classmethod
#  @timed
#  def classes_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Classes, "classes")
#
#  @classmethod
#  @timed
#  def FetchJson(cls, institution, session):
#    classes = Classes.classes_key(institution, session).get()
#    if classes:
#      return classes.jdata
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    classes = Classes.classes_key(institution, session).get()
#    if classes:
#      return classes.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, classes_data):
#    classes = Classes(data = classes_data,
#                      jdata = yaml.load(classes_data))
#    classes.key = Classes.classes_key(institution, session_name)
#    classes.put()
#
#
#class Students(ndb.Model):
#  """List of students in yaml and json format."""
#  data = ndb.TextProperty()
#  jdata = ndb.JsonProperty()
#
#  @classmethod
#  @timed
#  def students_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Students, "students")
#
#  @classmethod
#  @timed
#  def FetchJson(cls, institution, session):
#    students = Students.students_key(institution, session).get()
#    if students:
#      return students.jdata
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    students = Students.students_key(institution, session).get()
#    if students:
#      return students.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, students_data):
#    students = Students(data = students_data,
#                        jdata = yaml.load(students_data))
#    students.key = Students.students_key(institution, session_name)
#    students.put()
#
#
#class Teachers(ndb.Model):
#  """List of teachers in yaml and json format."""
#  data = ndb.TextProperty()
#  jdata = ndb.JsonProperty()
#
#  @classmethod
#  @timed
#  def teachers_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Teachers, "teachers")
#
#  @classmethod
#  @timed
#  def FetchJson(cls, institution, session):
#    teachers = Teachers.teachers_key(institution, session).get()
#    if teachers:
#      return teachers.jdata
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    teachers = Teachers.teachers_key(institution, session).get()
#    if teachers:
#      return teachers.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, teachers_data):
#    teachers = Teachers(data = teachers_data,
#                        jdata = yaml.load(teachers_data))
#    teachers.key = Teachers.teachers_key(institution, session_name)
#    teachers.put()
#
#
#class AutoRegister(ndb.Model):
#  """Examples: 8th Core, 7th Core, 6th Core"""
#  data = ndb.TextProperty()
#  jdata = ndb.JsonProperty()
#
#  @classmethod
#  @timed
#  def auto_register_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   AutoRegister, "auto_register")
#
#  @classmethod
#  @timed
#  def FetchJson(cls, institution, session):
#    auto_register = AutoRegister.auto_register_key(institution, session).get()
#    if auto_register:
#      return auto_register.jdata
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    auto_register = AutoRegister.auto_register_key(institution, session).get()
#    if auto_register:
#      return auto_register.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, auto_register_data):
#    auto_register = AutoRegister(
#        data = auto_register_data,
#        jdata = yaml.load(auto_register_data))
#    auto_register.key = AutoRegister.auto_register_key(institution, session_name)
#    auto_register.put()
#
#
#class Requirements(ndb.Model):
#  """Examples: one PE required, PEs must be on opposite sides of the week"""
#  data = ndb.TextProperty()
#  jdata = ndb.JsonProperty()
#
#  @classmethod
#  @timed
#  def requirements_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Requirements, "requirements")
#
#  @classmethod
#  @timed
#  def FetchJson(cls, institution, session):
#    requirements = Requirements.requirements_key(institution, session).get()
#    if requirements:
#      return requirements.jdata
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    requirements = Requirements.requirements_key(institution, session).get()
#    if requirements:
#      return requirements.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, requirements_data):
#    requirements = Requirements(
#        data = requirements_data,
#        jdata = yaml.load(requirements_data))
#    requirements.key = Requirements.requirements_key(institution, session_name)
#    requirements.put()
#
#
#class GroupsClasses(ndb.Model):
#  """List of class groups in yaml and json format."""
#  data = ndb.TextProperty()
#  jdata = ndb.JsonProperty()
#
#  @classmethod
#  @timed
#  def groups_classes_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   GroupsClasses, "groups_classes")
#
#  @classmethod
#  @timed
#  def FetchJson(cls, institution, session):
#    groups_classes = GroupsClasses.groups_classes_key(institution, session).get()
#    if groups_classes:
#      return groups_classes.jdata
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    groups_classes = GroupsClasses.groups_classes_key(institution, session).get()
#    if groups_classes:
#      return groups_classes.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, groups_classes_data):
#    groups_classes = GroupsClasses(
#        data = groups_classes_data,
#        jdata = yaml.load(groups_classes_data))
#    groups_classes.key = GroupsClasses.groups_classes_key(institution, session_name)
#    groups_classes.put()
#
#class GroupsStudents(ndb.Model):
#  """List of student groups in yaml and json format."""
#  data = ndb.TextProperty()
#  jdata = ndb.JsonProperty()
#
#  @classmethod
#  @timed
#  def groups_students_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   GroupsStudents, "groups_students")
#
#  @classmethod
#  @timed
#  def FetchJson(cls, institution, session):
#    groups_students = GroupsStudents.groups_students_key(institution, session).get()
#    if groups_students:
#      return groups_students.jdata
#    else:
#      return []
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    groups_students = GroupsStudents.groups_students_key(institution, session).get()
#    if groups_students:
#      return groups_students.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, groups_students_data):
#    groups_students = GroupsStudents(
#        data = groups_students_data,
#        jdata = yaml.load(groups_students_data))
#    groups_students.key = GroupsStudents.groups_students_key(institution, session_name)
#    groups_students.put()
#
#class Preferences(ndb.Model):
#  # Note: Email is not set in the DB Entity because it is part of the key. 
#  # It is added to the object after it is fetched.
#  # TODO: Can email be deleted?
#  email = ndb.StringProperty()
#  want = ndb.StringProperty()
#  dontcare = ndb.StringProperty()
#  dontwant = ndb.StringProperty()
#
#  @classmethod
#  @timed
#  def preferences_key(cls, email, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Preferences, email)
#
#  @classmethod
#  @timed
#  def Store(cls, email, institution, session, want, dontcare, dontwant):
#    """params want, dontcare, and dontwant are lists of ints"""
#    prefs = Preferences()
#    prefs.key = Preferences.preferences_key(email, institution, session)
#    if set(want).intersection(dontcare):
#      raise Exception("some classes are in both want and dontcare." +
#                      "\nwant: " + ','.join(want) + 
#                      "\ndontcare: " + ','.join(dontcare) +
#                      "\ndontwant: " + ','.join(dontwant))
#    if set(dontcare).intersection(dontwant):
#      raise Exception("some classes are in both dontcare and dontwant" +
#                      "\nwant: " + ','.join(want) + 
#                      "\ndontcare: " + ','.join(dontcare) +
#                      "\ndontwant: " + ','.join(dontwant))
#    if set(want).intersection(dontwant):
#      raise Exception("some classes are in both want and dontwant" +
#                      "\nwant: " + ','.join(want) + 
#                      "\ndontcare: " + ','.join(dontcare) +
#                      "\ndontwant: " + ','.join(dontwant))
#    prefs.want = ','.join(want)
#    prefs.dontcare = ','.join(dontcare)
#    prefs.dontwant = ','.join(dontwant)
#    logging.info('saving want = %s' % prefs.want)
#    logging.info('saving dontwant = %s' % prefs.dontwant)
#    logging.info('saving dontcare = %s' % prefs.dontcare)
#    prefs.put()
#
#  @classmethod
#  @timed
#  def FetchEntity(cls, email, institution, session):
#    prefs = Preferences.preferences_key(email, institution, session).get()
#    if not prefs:
#      prefs = Preferences()
#      prefs.email = email
#      prefs.want = ""
#      prefs.dontcare = ""
#      prefs.dontwant = ""
#    return prefs
#
#
#class Schedule(ndb.Model):
#  class_ids = ndb.StringProperty()
#  last_modified = ndb.DateTimeProperty() # See note below.
#
#  @classmethod
#  @timed
#  def schedule_key(cls, institution, session, email):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Schedule, email)
#
#  @classmethod
#  @timed
#  def Store(cls, institution, session, email, class_ids):
#    schedule = Schedule()
#    schedule.key = Schedule.schedule_key(institution, session, email)
#    schedule.class_ids = class_ids
#    # Appengine datetimes are stored in UTC, so by around 4pm the date is wrong.
#    # This kludge gets PST, but it doesn't handle daylight savings time,
#    # but off by one hour is better than off by eight hours. The date will
#    # be wrong half the year when someone is modifying data between
#    # 11pm and midnight.
#    schedule.last_modified = datetime.datetime.now() - datetime.timedelta(hours=8)
#    schedule.put()
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session, email):
#    schedule = Schedule.schedule_key(institution, session, email).get()
#    if not schedule:
#      return ""
#    else:
#      schedule.class_ids = schedule.class_ids.strip(',').strip()
#      return schedule.class_ids
#
#  @classmethod
#  @timed
#  def FetchEntity(cls, institution, session, email):
#    schedule = Schedule.schedule_key(institution, session, email).get()
#    if not schedule:
#      return {}
#    else:
#      schedule.class_ids = schedule.class_ids.strip(',').strip()
#      return schedule
#
#
#class ClassRoster(ndb.Model):
#  # comma separated list of student emails
#  student_emails = ndb.TextProperty()
#  # class obj, yaml.dump and yaml.load takes too long
#  jclass_obj = ndb.JsonProperty()
#  # Not using auto_now=True on purpose, see note below.
#  last_modified = ndb.DateTimeProperty()
#
#  @classmethod
#  @timed
#  def class_roster_key(cls, institution, session, class_id):
#    class_id = str(class_id)
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   ClassRoster, class_id)
#
#  @classmethod
#  @timed
#  def Store(cls, institution, session, class_obj, student_emails):
#    student_emails = student_emails.strip()
#    if len(student_emails) and student_emails[-1] == ',':
#      student_emails = student_emails[:-1]
#    class_id = str(class_obj['id'])
#    roster = ClassRoster()
#    roster.key = ClassRoster.class_roster_key(institution, session, class_id)
#    roster.student_emails = student_emails
#    roster.jclass_obj = class_obj
#    # Appengine datetimes are stored in UTC, so by around 4pm the date is wrong.
#    # This is a kludgy way to get PST. It doesn't handle daylight savings time,
#    # but off by one hour is better than off by eight.
#    # The alternatives:
#    #  - pytz has a few hundred files.
#    #  - tzinfo has four methods to implement which I don't need.
#    # Don't use hour because it will be wrong half the year.
#    # If someone wants to do this the "right" way later, that would be fine.
#    roster.last_modified = datetime.datetime.now() - datetime.timedelta(hours=8)
#    roster.put()
#
#  @classmethod
#  @timed
#  def FetchEntity(cls, institution, session, class_id):
#    class_id = str(class_id)
#    roster = ClassRoster.class_roster_key(institution, session, class_id).get()
#    if roster:
#      c = roster.jclass_obj
#      r = {}
#      r['emails'] = roster.student_emails.split(",")
#      if r['emails'][0] == "":
#        r['emails'] = r['emails'][1:]
#      r['class_name'] = c['name']
#      r['class_id'] = c['id']
#      if 'instructor' in c:
#        r['instructor'] = c['instructor']
#      r['schedule'] = c['schedule']
#      r['class_details'] = roster.jclass_obj
#      if 'max_enrollment' in c:
#        r['max_enrollment'] = c['max_enrollment']
#      if 'open_enrollment' in c:
#        r['open_enrollment'] = c['open_enrollment']
#        r['remaining_space'] = c['open_enrollment'] - len(r['emails'])
#      elif 'max_enrollment' in c:
#        r['remaining_space'] = c['max_enrollment'] - len(r['emails'])
#      else:
#        r['remaining_space'] = 0
#      if 'max_enrollment' in c:
#        r['remaining_firm'] = c['max_enrollment'] - len(r['emails'])
#      else:
#        r['remaining_firm'] = 0
#      if (roster.last_modified):
#        r['last_modified'] = roster.last_modified
#      else:
#        r['last_modified'] = None
#      return r
#    logging.info("Class Roster NOT found: [%s] [%s] [%s]" % (
#          institution, session, class_id))
#    r = {}
#    r['emails'] = []
#    r['class_id'] = 0
#    r['class_name'] = 'None'
#    r['schedule'] = {}
#    r['class_details'] = ''
#    r['max_enrollment'] = 0
#    r['remaining_space'] = 0
#    r['remaining_firm'] = 0
#    r['last_modified'] = None
#    return r
#
#class ClassWaitlist(ndb.Model):
#  # comma separated list of student emails
#  student_emails = ndb.TextProperty()
#  last_modified = ndb.DateTimeProperty()
#
#  @classmethod
#  @timed
#  def class_waitlist_key(cls, institution, session, class_id):
#    class_id = str(class_id)
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   ClassWaitlist, class_id)
#
#  @classmethod
#  @timed
#  def Store(cls, institution, session, class_id, student_emails):
#    student_emails = student_emails.strip()
#    if len(student_emails) and student_emails[-1] == ',':
#      student_emails = student_emails[:-1]
#    waitlist = ClassWaitlist()
#    waitlist.key = ClassWaitlist.class_waitlist_key(institution, session, class_id)
#    waitlist.student_emails = student_emails
#    waitlist.last_modified = datetime.datetime.now() - datetime.timedelta(hours=8)
#    waitlist.put()
#
#  @classmethod
#  @timed
#  def FetchEntity(cls, institution, session, class_id):
#    class_id = str(class_id)
#    waitlist = ClassWaitlist.class_waitlist_key(institution, session, class_id).get()
#    if waitlist:
#      w = {}
#      w['emails'] = waitlist.student_emails.split(",")
#      if w['emails'][0] == "":
#        w['emails'] = w['emails'][1:]
#      return w
#    else:
#      return {'emails': []}
#
#class ErrorCheck(ndb.Model):
#  data = ndb.StringProperty(choices=['OK', 'FAIL', 'UNKNOWN'])
#
#  @classmethod
#  @timed
#  def errorcheck_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   ErrorCheck, "errorcheck")
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    errorcheck = ErrorCheck.errorcheck_key(institution, session).get()
#    if errorcheck:
#      return errorcheck.data
#    else:
#      return 'UNKNOWN'
#
#  @classmethod
#  @timed
#  def Store(cls, institution, session_name, errorcheck_data):
#    errorcheck = ErrorCheck(data = errorcheck_data)
#    errorcheck.key = ErrorCheck.errorcheck_key(institution, session_name)
#    errorcheck.put()
#
#
#class DBVersion(ndb.Model):
#  data = ndb.IntegerProperty()
#
#  @classmethod
#  @timed
#  def db_version_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   DBVersion, "db_version")
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    db_version = DBVersion.db_version_key(institution, session).get()
#    if db_version:
#      return db_version.data
#    else:
#      return 0
#
#  @classmethod
#  @timed
#  def Store(cls, institution, session, version):
#    db_version = DBVersion(data = version)
#    db_version.key = DBVersion.db_version_key(institution, session)
#    db_version.put()
#
#class Attendance(ndb.Model):
#  jdata = ndb.JsonProperty()
#
#  # 'c_id' is a class id.
#  # 'jdata' is a dictionary whose keys are dates which map to objects
#  # representing attendance taken that date.
#  # {date1: { 'absent': [email1, email2, ...],
#  #           'present': [email1, email2, ...],
#  #           'submitted_by': email,
#  #           'submitted_date': date1,
#  #           'note': string },
#  #  date2: { . . . }
#  # }
#  @classmethod
#  def attendance_key(cls, institution, session, c_id):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Attendance, c_id)
#
#  @classmethod
#  def FetchJson(cls, institution, session, c_id):
#    attendance = Attendance.attendance_key(institution, session, c_id).get()
#    if attendance:
#      return attendance.jdata
#    else:
#      return {}
#
#  @classmethod
#  def store(cls, institution, session, c_id, attendance_obj):
#    attendance = Attendance(jdata = attendance_obj)
#    attendance.key = Attendance.attendance_key(institution, session, c_id)
#    attendance.put()
#
#class Closed(ndb.Model):
#  data = ndb.TextProperty()
#
#  @classmethod
#  @timed
#  def closed_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Closed, "closed")
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    closed = Closed.closed_key(institution, session).get()
#    if closed:
#      return closed.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, closed):
#    closed = Closed(data = closed)
#    closed.key = Closed.closed_key(institution, session_name)
#    closed.put()
#
#class Materials(ndb.Model):
#  data = ndb.TextProperty()
#
#  @classmethod
#  @timed
#  def materials_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Materials, "materials")
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    materials = Materials.materials_key(institution, session).get()
#    if materials:
#      return materials.data
#    else:
#      return ''
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, materials):
#    materials = Materials(data = materials)
#    materials.key = Materials.materials_key(institution, session_name)
#    materials.put()
#
#
#class Config(ndb.Model):
#  htmlDesc = ndb.StringProperty()
#  displayRoster = ndb.StringProperty()
#  twoPE = ndb.StringProperty()
#
#  @classmethod
#  @timed
#  def config_key(cls, institution, session):
#    return ndb.Key("InstitutionKey", institution,
#                   Session, session,
#                   Config, "config")
#
#  @classmethod
#  @timed
#  def Fetch(cls, institution, session):
#    config = Config.config_key(institution, session).get()
#    if config:
#      cfg = {'displayRoster': config.displayRoster,
#             'htmlDesc': config.htmlDesc,
#             'twoPE': config.twoPE}
#      return cfg
#    else:
#      return {'displayRoster': 'dRNo',
#              'htmlDesc': 'htmlNo',
#              'twoPE': 'twoPENo'}
#
#  @classmethod
#  @timed
#  def store(cls, institution, session_name, displayRoster, htmlDesc, twoPE):
#    config = Config()
#    config.key = Config.config_key(institution, session_name)
#    config.htmlDesc = htmlDesc
#    config.displayRoster = displayRoster
#    config.twoPE = twoPE
#    config.put()
#