from datetime import datetime
from flask import current_app

import yaml
import json

from google.cloud import datastore

Client = datastore.Client()
GLOBAL_KEY = Client.key("global", "global")

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
      return Client.key(*path)
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
    return Client.key(*path, parent=parent_key, **kwargs)  

  @classmethod
  def Store(cls, *path_args, data={}, exclude_from_indexes=(), **kwargs):
    current_app.logger.info("%s.Store: %s", cls.__name__, str(path_args))
    entity = datastore.Entity(key=cls.key(*path_args, **kwargs),exclude_from_indexes=exclude_from_indexes)
    data.update({'date_time': datetime.now()})
    if data:
      entity.update(data)
    return Client.put(entity)

  @classmethod
  def Delete(cls, *path_args, **kwargs):
    Client.delete(cls.key(*path_args, **kwargs))

  @classmethod
  def FetchEntity(cls, *path_args, **kwargs):
    entity = Client.get(cls.key(*path_args, **kwargs))
    return entity

  @classmethod
  def Fetch(cls,order=['__key__'],ancestor=None,filters=[],limit=None):
    query = Client.query(kind=cls.__name__,ancestor=ancestor,order=order)
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
      return list({i.key.parent.id_or_name:1 for i in list(filter(lambda j: j.key.id_or_name==child,results))}.keys())

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

class YamlJsonAttribute(Model):
  attribute = None
  default = ''
  defaultJson = []

  @classmethod
  def key(cls, *args):
    nargs = list(args)
    nargs.append(cls.attribute)
    return super().key(*nargs)

  @classmethod
  def Store(cls, *args):
    nargs=list(args)
    data = nargs.pop()
    jdata = yaml.safe_load(data) if data else cls.defaultJson
    current_app.logger.info(f"validated data to be posted={jdata}")
    return super().Store(*nargs, data={
      "data" : data if data else cls.default,
      "jdata": jdata},
      exclude_from_indexes=('data','jdata'))

  @classmethod
  def Fetch(cls, *args):
    entity = cls.FetchEntity(*args)
    return entity.get("data") if entity else cls.default

  @classmethod
  def FetchJson(cls, *args):
    entity = cls.FetchEntity(*args)
    return entity.get("jdata") if entity else cls.defaultJson


#-------------------------------------
class GlobalAdmin(Model):
  """email addresses for users with full access to the site."""
  @classmethod
  def parent_key(cls):
    return GLOBAL_KEY

class Admin(Model):
  ancestors = ["InstitutionKey"]

  @classmethod
  def GetInstitutionNames(cls, email):
    return cls.GetParents(email)

class Institution(Model):
  """Institution name"""
  @classmethod
  def parent_key(cls):
    return GLOBAL_KEY

class Session(Model):
  ancestors = ["InstitutionKey"]

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
    Client.put_multi(changed)

  @classmethod
  def disable(cls, institution, session):
    'Set target session as inactive'
    entity = cls.FetchEntity(institution, session)
    if entity:
      entity['active'] = False
      Client.put(entity)
    else:
      current_app.logger.error("session key not found: %s, %s", institution, session)

  @classmethod
  def ServingSession(cls, *args):
    'Get the active session (should only have 1 or 0 session active)'
    ss = None
    if len(args)>0:
      institution = args[0]
      ss = cls.Fetch(ancestor=cls.parent_key(institution),filters=[("active", "=", True)])
    else:  
      ss = cls.Fetch(filters=[("active", "=", True)])
    return ss

class ServingRules(YamlJsonAttribute):
  """List of serving rules in yaml and json format."""
  ancestors = ["InstitutionKey","Session"]
  attribute = "serving_rules"


class Dayparts(YamlJsonAttribute):
  """Examples: Monday AM, or M-W-F 8am-9am"""
  ancestors = ["InstitutionKey","Session"]
  attribute = "dayparts"

class Classes(YamlJsonAttribute):
  """List of classes in yaml and json format."""
  ancestors = ["InstitutionKey","Session"]
  attribute = "classes"

  @classmethod
  def Store(cls, institution, session, classes):
    super().Store(institution, session, classes)
    # ClassRoster saves a copy of class info in its own jclass_obj
    # (for efficiency?). When Classes changes, make sure
    # ClassRoster's jclass_obj stays in sync by calling
    # ClassRoster.Store(). Otherwise, odd things happen.
    #
    # Also, calling ClassRoster.Store() when there are changes
    # to Classes, udpates the last_modified field. This fixes the
    # bug where last modified dates on attendance sheet and student
    # schedule reports don't update when only Classes info changed
    # but no students were added or deleted.
    #
    # Finally, storing every ClassRoster when the corresponding
    # class is created (because, of course, initially jclass_obj != c),
    # fixes the bug where remaining spots on the schedule page
    # initializes incorrectly to 0 instead of max_enrollment.    
    classes = yaml.safe_load(classes)
    for c in classes:
      roster = ClassRoster.FetchEntity(institution, session, c['id'])
      if not roster or c != roster['class_details']:
        ClassRoster.Store(institution, session, c, ",".join(roster['emails']) if roster else '')

class Students(YamlJsonAttribute):
  """List of students in yaml and json format."""
  ancestors = ["InstitutionKey","Session"]
  attribute = "students"

class Teachers(YamlJsonAttribute):
  """List of teachers in yaml and json format."""
  ancestors = ["InstitutionKey","Session"]
  attribute = "teachers"

class AutoRegister(YamlJsonAttribute):
  """Examples: 8th Core, 7th Core, 6th Core"""
  ancestors = ["InstitutionKey","Session"]
  attribute = "auto_register"

class Requirements(Model):
  """Examples: one PE required, PEs must be on opposite sides of the week"""
  ancestors = ["InstitutionKey","Session"]
  attribute = "requirements"
  defaultJson = '[]'

  @classmethod
  def key(cls, *args):
    nargs = list(args)
    nargs.append(cls.attribute)
    return super().key(*nargs)

  @classmethod
  def Fetch(cls, *args):
    entity = cls.FetchEntity(*args)
    return entity.get("data") if entity else cls.default

  # for Google datastore, list_value cannot contain a Value containing another list_value. 
  # workaround by storing serialized Json string
  @classmethod
  def Store(cls, *args):
    nargs=list(args)
    data = nargs.pop()
    jdata = yaml.safe_load(data) if data else cls.defaultJson
    current_app.logger.info(f"validated data to be posted={jdata}")
    return super().Store(*nargs, data={
      "data" : data if data else cls.default,
      "jdata": json.dumps(jdata)})

  @classmethod
  def FetchJson(cls, *args):
    entity = cls.FetchEntity(*args)
    jdata = entity.get("jdata") if entity else cls.defaultJson
    return json.loads(jdata)

class GroupsClasses(YamlJsonAttribute):
  """List of class groups in yaml and json format."""
  ancestors = ["InstitutionKey","Session"]
  attribute = "groups_classes"

class GroupsStudents(YamlJsonAttribute):
  """List of student groups in yaml and json format."""
  ancestors = ["InstitutionKey","Session"]
  attribute = "groups_students"

class RecentAccess(Model):
  pass

class Preferences(Model):
  ancestors = ["InstitutionKey","Session"]

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
    prefs = {
      "email": email,
      "want": ','.join(want),
      "dontcare": ','.join(dontcare),
      "dontwant": ','.join(dontwant) }
    #current_app.logger.info('saving preferences = %s' % prefs)
    super().Store(institution,session,email,data=prefs)

  @classmethod
  def FetchEntity(cls, email, institution, session):
    entity = super().FetchEntity(institution, session, email)
    return entity or {
      "email": email,
      "want": "",
      "dontcare": "",
      "dontwant": "" }

class Schedule(Model):
  ancestors = ["InstitutionKey","Session"]

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
  ancestors = ["InstitutionKey","Session"]
#  # comma separated list of student emails
#  student_emails = nClient.TextProperty()
#  # class obj, yaml.dump and yaml.load takes too long
#  jclass_obj = nClient.JsonProperty()
#  last_modified = nClient.DateTimeProperty()

  @classmethod
  def Store(cls, institution, session, class_obj, student_emails):
    class_id = str(class_obj['id'])
    student_emails = student_emails.strip()
    if len(student_emails) and student_emails[-1] == ',':
      student_emails = student_emails[:-1]
    roster = {
      "student_emails" : student_emails,
      "jclass_obj"     : class_obj}
    #current_app.logger.info('saving class_roster = %s' % roster)
    super().Store(institution, session, class_id, data=roster)

#    # Appengine datetimes are stored in UTC, so by around 4pm the date is wrong.
#    # This is a kludgy way to get PST. It doesn't handle daylight savings time,
#    # but off by one hour is better than off by eight.
#    # The alternatives:
#    #  - pytz has a few hundred files.
#    #  - tzinfo has four methods to implement which I don't need.
#    # Don't use hour because it will be wrong half the year.
#    # If someone wants to do this the "right" way later, that would be fine.
#    roster.last_modified = datetime.datetime.now() - datetime.timedelta(hours=8)

  @classmethod
  def FetchEntity(cls, institution, session, class_id):
    class_id = str(class_id)
    entity = super().FetchEntity(institution, session, class_id)
    if entity:
      c = entity.get("jclass_obj")
      r = {}
      r['emails'] = entity.get("student_emails").split(",")
      if r['emails'][0] == "":
        r['emails'] = r['emails'][1:]
      r['class_name'] = c['name']
      r['class_id'] = c['id']
      if 'instructor' in c:
        r['instructor'] = c['instructor']
      r['schedule'] = c['schedule']
      r['class_details'] = entity.get("jclass_obj")
      if 'max_enrollment' in c:
        r['max_enrollment'] = c['max_enrollment']
      if 'open_enrollment' in c:
        r['open_enrollment'] = c['open_enrollment']
        r['remaining_space'] = c['open_enrollment'] - len(r['emails'])
      elif 'max_enrollment' in c:
        r['remaining_space'] = c['max_enrollment'] - len(r['emails'])
      else:
        r['remaining_space'] = 0
      if 'max_enrollment' in c:
        r['remaining_firm'] = c['max_enrollment'] - len(r['emails'])
      else:
        r['remaining_firm'] = 0
      if (entity.get("date_time")):
        r['last_modified'] = entity.get("date_time")
      else:
        r['last_modified'] = None
      return r
    current_app.logger.info("Class Roster NOT found: [%s] [%s] [%s]" % (
          institution, session, class_id))
    r = {}
    r['emails'] = []
    r['class_id'] = 0
    r['class_name'] = 'None'
    r['schedule'] = {}
    r['class_details'] = ''
    r['max_enrollment'] = 0
    r['remaining_space'] = 0
    r['remaining_firm'] = 0
    r['last_modified'] = None
    return r

class ClassWaitlist(Model):
  ancestors = ["InstitutionKey","Session"]
  # comma separated list of student emails
  @classmethod
  def Store(cls, institution, session, class_id, student_emails):
    class_id = str(class_id)
    student_emails = student_emails.strip()
    if len(student_emails) and student_emails[-1] == ',':
      student_emails = student_emails[:-1]
    super().Store(institution, session, class_id, data={
      "student_emails" : student_emails})

  @classmethod
  def FetchEntity(cls, institution, session, class_id):
    class_id = str(class_id)
    entity = super().FetchEntity(institution, session, class_id)
    if entity:
      w = {}
      w['emails'] = entity.get("student_emails").split(",")
      if w['emails'][0] == "":
        w['emails'] = w['emails'][1:]
      return w
    else:
      return {'emails': []}

class ErrorCheck(Attribute):
  ancestors = ["InstitutionKey","Session"]
  attribute = 'errorcheck'
  default = 'UNKNOWN'

class DBVersion(Attribute):
  ancestors = ["InstitutionKey","Session"]
  attribute = "db_version"
  default = 0

class Attendance(Model):
  ancestors = ["InstitutionKey","Session"]
  # 'class_id' is a class id.
  # 'jdata' is a dictionary whose keys are dates which map to objects
  # representing attendance taken that date.
  # {date1: { 'absent': [email1, email2, ...],
  #           'present': [email1, email2, ...],
  #           'submitted_by': email,
  #           'submitted_date': date1,
  #           'note': string },
  #  date2: { . . . }
  # }
  @classmethod
  def Store(cls, institution, session, class_id, attendance_obj):
    class_id = str(class_id)
    super().Store(institution, session, class_id, data=attendance_obj)

  @classmethod
  def FetchJson(cls, institution, session, class_id):
    class_id = str(class_id)
    entity = cls.FetchEntity(institution, session, class_id)
    return entity if entity else {}

class Closed(Attribute):
  ancestors = ["InstitutionKey","Session"]
  attribute = 'closed'
  default = ''

class Materials(Attribute):
  ancestors = ["InstitutionKey","Session"]
  attribute = 'materials'
  default = ''

class Welcome(Attribute):
  attribute = "welcome"
  default = ""

class Config(Attribute):
  ancestors = ["InstitutionKey","Session"]
  attribute = "config"
  default = {'displayRoster': 'dRNo',
              'htmlDesc': 'htmlNo',
              'twoPE': 'twoPENo'}

  @classmethod
  def Store(cls, institution, session_name, displayRoster, htmlDesc, twoPE):
    super().Store(institution, session_name, {
      'displayRoster': displayRoster,
      'htmlDesc'     : htmlDesc,
      'twoPE'        : twoPE})
