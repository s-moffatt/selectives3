from flask import render_template, redirect, request, current_app, jsonify, abort
from flask.views import MethodView
import urllib.parse

import models
import authorizer

class SpotsAvailable(MethodView):

  def post(self):
    auth = authorizer.Authorizer()
    if not (auth.HasStudentAccess() or
            auth.HasTeacherAccess()):
      abort(403) # Forbidden

    institution = request.form.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.form.get("session")
    if not session:
      current_app.logger.critical("no session")

    if not (auth.HasTeacherAccess() or
            auth.HasPageAccess(institution, session, "schedule")):
      abort(403) # Forbidden

    class_ids = request.form.get("class_ids")
    class_ids = current_app.json.loads(class_ids)
    results = {}
    for class_id in class_ids:
      roster = models.ClassRoster.FetchEntity(institution, session, class_id)
      results[str(class_id)] = roster['remaining_space']
    return jsonify(results)
