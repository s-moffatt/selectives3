from flask import render_template, redirect, request, current_app
from flask.views import MethodView
import urllib.parse

import models
import authorizer
import logic
import error_check_logic
import yayv
import schemas

class ErrorCheck(MethodView):
  def RedirectToSelf(cls, institution, session, message):
    return redirect('/error_check?%s' % urllib.parse.urlencode(
        {'message': message, 
         'institution': institution,
         'session': session}))

  def post(cls):
    auth = authorizer.Authorizer()
    if not auth.CanAdministerInstitutionFromUrl():
      return auth.Redirect()

    institution = request.args.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.args.get("session")
    if not session:
      current_app.logger.critical("no session")

    checker = error_check_logic.Checker(institution, session)
    checker.RunUpgradeScript()
    return cls.RedirectToSelf(institution, session, "upgrade")

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
    checker = error_check_logic.Checker(institution, session)
    setup_status, error_chk_detail = checker.ValidateSetup()

    return render_template("error_check.html", 
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      setup_status=setup_status,
      error_chk_detail=error_chk_detail,
      session_query=session_query,
    )
