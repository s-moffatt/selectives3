from flask import render_template, redirect, request, current_app, jsonify, abort
from flask.views import MethodView
import urllib.parse

import models
import authorizer
import logic

class HoverText(MethodView):

  def post(self):
    institution = request.form.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.form.get("session")
    if not session:
      current_app.logger.critical("no session")

    auth = authorizer.Authorizer()
    if not (auth.CanAdministerInstitutionFromUrl() or
            auth.HasTeacherAccess() or
            (auth.HasStudentAccess() and
             auth.HasPageAccess(institution, session, "schedule"))):
      abort(403) # Forbidden

    use_full_description = auth.CanAdministerInstitutionFromUrl()

    class_ids = request.form.get("class_ids")
    class_ids = current_app.json.loads(class_ids)
    results = {}
    classes = models.Classes.FetchJson(institution, session)
    classes_by_id = {}
    for c in classes:
      classes_by_id[c['id']] = c
    for class_id in class_ids:
      results[str(class_id)] = logic.GetHoverText(institution, session, use_full_description, classes_by_id[int(class_id)])
    return jsonify(results)
