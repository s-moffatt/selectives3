from flask import render_template, redirect, request, current_app
from flask.views import MethodView
import urllib.parse
import error_check_logic
import models
import authorizer
import logic



class Impersonation(MethodView):

  def RedirectToSelf(self, institution, session, message):
    return redirect('/impersonation?%s' % urllib.parse.urlencode(
        {'message': message, 
         'institution': institution,
         'session': session}))

  def get(self):
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
    students = models.Students.FetchJson(institution, session)
    return render_template("impersonation.html", 
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      setup_status=setup_status,
      session_query=session_query,
      students=students,
    )
