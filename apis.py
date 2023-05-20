from flask import render_template, redirect, request, current_app, jsonify, abort
from flask.views import MethodView
import urllib.parse

import models
import authorizer
import logic

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

def _ClassRosterGetJdata(institution, session, key):
  class_ids = get_param("class_ids")
  class_ids = current_app.json.loads(class_ids)
  results = {}
  for class_id in class_ids:
    roster = models.ClassRoster.FetchEntity(institution, session, class_id)
    results[str(class_id)] = roster[key]
  return results

@classmethod
def SpotsAvailableGetJdata(cls, institution, session, auth):
  return _ClassRosterGetJdata(institution, session, 'remaining_space')

@classmethod
def SpotsFirmGetJdata(cls, institution, session, auth):
  return _ClassRosterGetJdata(institution, session, 'remaining_firm')

@classmethod
def HoverTextGetJdata(cls, institution, session, auth):
  use_full_description = auth.CanAdministerInstitutionFromUrl()
  class_ids = get_param("class_ids")
  class_ids = current_app.json.loads(class_ids)
  results = {}
  classes = models.Classes.FetchJson(institution, session)
  classes_by_id = {}
  for c in classes:
    classes_by_id[c['id']] = c
  for class_id in class_ids:
    results[str(class_id)] = logic.GetHoverText(institution, session, use_full_description, classes_by_id[int(class_id)])
  return results

APIs = {
  "spots_available": {
    "view"           : "API",
    "route"          : "/spots_available",
    "teacher_access" : True,
    "student_access" : True,
    "student_page"   : "schedule",
    "get_jdata"      : SpotsAvailableGetJdata,
  },
  "spots_firm": {
    "view"           : "API",
    "route"          : "/spots_firm",
    "teacher_access" : True,
    "student_access" : True,
    "student_page"   : "schedule",
    "get_jdata"      : SpotsFirmGetJdata,
  },
  "hover_text": {
    "view"           : "API",
    "route"          : "/hover_text",
    "teacher_access" : True,
    "student_access" : True,
    "student_page"   : "schedule",
    "get_jdata"      : HoverTextGetJdata,
  },
}

class APIView(MethodView):
  name = "spots_available"
  @classmethod
  def __init__(cls):
    cls.route         = APIs[cls.name]["route"]
    cls.teacher_access= APIs[cls.name].get("teacher_access",False)
    cls.student_access= APIs[cls.name].get("student_access",False)
    cls.student_page  = APIs[cls.name].get("student_page"  ,None)

  @classmethod
  def GetJdata(cls, institution, session, auth):
    return {}

  @classmethod
  def as_view(cls):
    return super().as_view(cls.name)

  @classmethod
  def post(cls):
    institution = get_param("institution")
    session     = get_param("session")

    auth = authorizer.Authorizer()
    if not (auth.CanAdministerInstitutionFromUrl() or
            (cls.teacher_access and auth.HasTeacherAccess()) or
            (cls.student_access and auth.HasStudentAccess() and auth.HasPageAccess(institution, session, cls.student_page))):
      abort(403) # Forbidden

    results = cls.GetJdata(institution, session, auth)
    return jsonify(results)

def APIClass(classname, get_jdata=None):
  class NewClass(APIView):
    name = classname     
    if get_jdata:
      GetJdata = get_jdata
  return NewClass