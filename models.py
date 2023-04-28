from datetime import datetime
from flask import current_app


from google.cloud import datastore

db = datastore.Client()
GLOBAL_KEY = db.key("global", "global")

# TODO: make all methods camel case with initial caps
# TODO: Fetch methods should come in predictable flavors:
# - Plain Fetch returns a string
# - FetchAll returns a list of strings
# - FetchEntity returns a ndbModel object
# - FetchAllEntities returns a list of ndbModel object

class Model():
  ancestors = []

  @staticmethod
  def paths(pathkinds,pathnames):
    path = []
    for i in range(0,len(pathkinds)):
      path.append(pathkinds[i])
      path.append(pathnames[i])
    return path

  @classmethod
  def parent_key(cls, *parent_key_args, **kwarg):  
    ancestors = cls.ancestors
    if ancestors:
      path = Model.paths(cls.ancestors,parent_key_args)
      return db.key(*path)
    return None

  @classmethod
  def key(cls, *path_args, **kwargs):
    ancestors = cls.ancestors
    parent_key = None
    path=[]
    if ancestors:
      path = Model.paths(ancestors,path_args)
    else:
      parent_key = cls.parent_key()
    path.append(cls.__name__)
    path.append(path_args[len(ancestors)])  
    return db.key(*path, parent=parent_key, **kwargs)  

  @classmethod
  def Store(cls, *path_args, data={}, **kwargs):
    current_app.logger.info("%s.Store: %s", cls.__name__, str(path_args))
    entity = datastore.Entity(key=cls.key(*path_args, **kwargs))
    data.update({'date_time': datetime.now()})
    if data:
      entity.update(data)
    return db.put(entity)

  @classmethod
  def Delete(cls, *path_args, **kwargs):
    db.delete(cls.key(*path_args, **kwargs))

  @classmethod
  def FetchEntity(cls, *path_args, **kwargs):
    entity = db.get(cls.key(*path_args, **kwargs))
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
  def FetchAllEntities(cls,*parent_key_args, **kwargs):
    return cls.Fetch(ancestor=cls.parent_key(*parent_key_args, **kwargs))

  @classmethod
  def FetchAll(cls,*parent_key_args, **kwargs):
    results = cls.FetchAllEntities(*parent_key_args, **kwargs)
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

class Attribute(Model):
  attribute = None
  default = None

  @classmethod
  def key(cls, *args):
    nargs = list(args)
    nargs.append(cls.attribute)
    return super().key(*nargs)

  @classmethod
  def Store(cls, *args):
    nargs=list(args)
    data = nargs.pop()
    return super().Store(*nargs, data={
      "data": data if data else cls.default})

  @classmethod
  def Fetch(cls, *args):
    entity = cls.FetchEntity(*args)
    return entity.get("data") if entity else cls.default

class YamlJsonAttribute(Attribute):
  default = ''
  defaultJson = None

  @classmethod
  def FetchJson(cls, *args):
    entity = cls.FetchEntity(*args)
    return entity.get("jdata") if entity else cls.defaultJson

  @classmethod
  def Store(cls, *args):
    nargs=list(args)
    data = nargs.pop()
    return super().Store(*nargs, data={
      "data" : data if data else cls.default,
      "jdata": yaml.load(data) if data else cls.defaultJson})

#-------------------------------------
class GlobalAdmin(Model):
  """email addresses for users with full access to the site."""
  @classmethod
  def parent_key(cls):
    return GLOBAL_KEY

class Admin(Model):
  ancestors = ["Institution"]

  @classmethod
  def GetInstitutionNames(cls, email):
    return cls.GetParents(email)

class Institution(Model):
  """Institution name"""
  @classmethod
  def parent_key(cls):
    return GLOBAL_KEY

class Session(Model):
  ancestors = ["Institution"]

  @classmethod
  def enable(cls, institution, session):
    'Set only one session active at a time'
    changed = []
    for entity in cls.FetchAllEntities(institution):
      if entity.key.id_or_name == session and not entity.get('active'):
        entity['active'] = True
        changed.append(entity)
      elif entity.key.id_or_name != session and entity.get('active'):
        entity['active'] = False
        changed.append(entity)
    db.put_multi(changed)

  @classmethod
  def disable(cls, institution, session):
    'Set target session as inactive'
    entity = cls.FetchEntity(institution, session)
    if entity:
      entity['active'] = False
      db.put(entity)
    else:
      current_app.logger.error("session key not found: %s, %s", institution, session)

  @classmethod
  def ServingSession(cls, institution):
    'Get the active session (should only have 1 or 0 session active)'
    ss = cls.Fetch(ancestor=cls.parent_key(institution),filters=[("active", "=", True)])
    return ss[0].key.id_or_name if ss else None

class ServingRules(YamlJsonAttribute):
  """List of serving rules in yaml and json format."""
  attribute = "serving_rules"


class Dayparts(YamlJsonAttribute):
  """Examples: Monday AM, or M-W-F 8am-9am"""
  attribute = "dayparts"

class Classes(YamlJsonAttribute):
  """List of classes in yaml and json format."""
  attribute = "classes"

class Students(YamlJsonAttribute):
  """List of students in yaml and json format."""
  attribute = "students"

class Teachers(YamlJsonAttribute):
  """List of teachers in yaml and json format."""
  attribute = "teachers"

class AutoRegister(YamlJsonAttribute):
  """Examples: 8th Core, 7th Core, 6th Core"""
  attribute = "auto_register"

class Requirements(YamlJsonAttribute):
  """Examples: one PE required, PEs must be on opposite sides of the week"""
  attribute = "requirements"

class GroupsClasses(YamlJsonAttribute):
  """List of class groups in yaml and json format."""
  attribute = "groups_classes"

class GroupsStudents(YamlJsonAttribute):
  """List of student groups in yaml and json format."""
  attribute = "groups_students"

class RecentAccess(Model):
  pass

class Preferences(Model):
  ancestors = ["Institution","Session"]

  @classmethod
  def Store(cls, email, institution, session, want, dontcare, dontwant):
    """params want, dontcare, and dontwant are lists of ints"""
    prefs = {}
    if set(want).intersection(dontcare):
      raise Exception("some classes are in both want and dontcare." +
                      "\nwant: " + ','.join(want) + 
                      "\ndontcare: " + ','.join(dontcare) +
                      "\ndontwant: " + ','.join(dontwant))
    if set(dontcare).intersection(dontwant):
      raise Exception("some classes are in both dontcare and dontwant" +
                      "\nwant: " + ','.join(want) + 
                      "\ndontcare: " + ','.join(dontcare) +
                      "\ndontwant: " + ','.join(dontwant))
    if set(want).intersection(dontwant):
      raise Exception("some classes are in both want and dontwant" +
                      "\nwant: " + ','.join(want) + 
                      "\ndontcare: " + ','.join(dontcare) +
                      "\ndontwant: " + ','.join(dontwant))
    prefs["email"] = email
    prefs["want"] = ','.join(want)
    prefs["dontcare"] = ','.join(dontcare)
    prefs["dontwant"] = ','.join(dontwant)
    current_app.logger.info('saving preferences = %s' % prefs)
    super().Store(institution,session,email,data={"preferences":prefs})

  @classmethod
  def FetchEntity(cls, email, institution, session):
    entity = super().FetchEntity(institution, session, email)
    return entity.get("preferences") if entity else {
      "email": email,
      "want": "",
      "dontcare": "",
      "dontwant": "" }

class Schedule(Model):
  ancestors = ["Institution","Session"]

  @classmethod
  def Store(cls, institution, session, email, class_ids):
    super().Store(institution, session, email, data={
      "class_ids":class_ids})
#    # Appengine datetimes are stored in UTC, so by around 4pm the date is wrong.
#    # This kludge gets PST, but it doesn't handle daylight savings time,
#    # but off by one hour is better than off by eight hours. The date will
#    # be wrong half the year when someone is modifying data between
#    # 11pm and midnight.
#    schedule.last_modified = datetime.datetime.now() - datetime.timedelta(hours=8)

  @classmethod
  def Fetch(cls, institution, session, email):
    entity = super().FetchEntity(institution, session, email)
    return entity.get("class_ids","").strip(',').strip() if entity else ""

class ClassRoster(Model):
#  # comma separated list of student emails
#  student_emails = ndb.TextProperty()
#  # class obj, yaml.dump and yaml.load takes too long
#  jclass_obj = ndb.JsonProperty()
#  last_modified = ndb.DateTimeProperty()

  @classmethod
  def Store(cls, institution, session, class_obj, student_emails):
    student_emails = student_emails.strip()
    if len(student_emails) and student_emails[-1] == ',':
      student_emails = student_emails[:-1]
    class_id = str(class_obj['id'])
    roster = {}
    if set(want).intersection(dontcare):
      raise Exception("some classes are in both want and dontcare." +
                      "\nwant: " + ','.join(want) + 
                      "\ndontcare: " + ','.join(dontcare) +
                      "\ndontwant: " + ','.join(dontwant))
    if set(dontcare).intersection(dontwant):
      raise Exception("some classes are in both dontcare and dontwant" +
                      "\nwant: " + ','.join(want) + 
                      "\ndontcare: " + ','.join(dontcare) +
                      "\ndontwant: " + ','.join(dontwant))
    if set(want).intersection(dontwant):
      raise Exception("some classes are in both want and dontwant" +
                      "\nwant: " + ','.join(want) + 
                      "\ndontcare: " + ','.join(dontcare) +
                      "\ndontwant: " + ','.join(dontwant))
    prefs["email"] = email
    prefs["want"] = ','.join(want)
    prefs["dontcare"] = ','.join(dontcare)
    prefs["dontwant"] = ','.join(dontwant)
    current_app.logger.info('saving preferences = %s' % prefs)
    super().Store(institution,session,email,data={"preferences":prefs})
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
#    current_app.logger.info("Class Roster NOT found: [%s] [%s] [%s]" % (
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

class ErrorCheck(Attribute):
  attribute = 'errorcheck'
  default = 'UNKNOWN'

class DBVersion(Attribute):
  attribute = "db_version"
  default = 0

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

class Welcome(Attribute):
  attribute = "welcome"
  default = ""

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