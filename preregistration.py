from flask import render_template, redirect, request, current_app
from flask.views import MethodView
import urllib.parse
import models
import authorizer



class Preregistration(MethodView):
  def get(self):
    auth = authorizer.Authorizer()
    if not auth.HasStudentAccess():
      return auth.Redirect()

    institution = request.args.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.args.get("session")
    if not session:
      current_app.logger.critical("no session")
    if not auth.HasPageAccess(institution, session, "materials"):
      return auth.RedirectTemporary(institution, session)

    message = request.args.get('message')
    session_query = urllib.parse.urlencode({'institution': institution,
                                      'session': session})
    welcome_msg = models.Materials.Fetch(institution, session)

    return render_template("preregistration.html", 
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      session_query=session_query,
      self=request.url,
      welcome_msg=welcome_msg,
      impersonation=f"&student={auth.student_email}" if auth.email!=auth.student_email else ""
    )
