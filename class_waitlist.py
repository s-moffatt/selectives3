from flask import render_template, redirect, request, current_app
from flask.views import MethodView
import urllib.parse

import models
import authorizer
import logic

def addStudentData(class_roster, students):
  class_roster['students'] = []
  for e in class_roster['emails']:
    for s in students:
      if (s['email'] == e):
        class_roster['students'].append(s)

class ClassWaitlist(MethodView):

  def RedirectToSelf(self, institution, session, class_id, message):
    return redirect("/class_waitlist?%s" % urllib.parse.urlencode(
        {'message': message,
         'institution': institution,
         'session': session,
         'class_id': class_id}))

  def post(self):
    auth = authorizer.Authorizer()
    if not auth.CanAdministerInstitutionFromUrl():
      return auth.Redirect()

    institution = request.args.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.args.get("session")
    if not session:
      current_app.logger.critical("no session")
    class_id = request.args.get("class_id")
    if not class_id:
      current_app.logger.critical("no class_id")
    action = request.form.get("action")
    if not action:
      current_app.logger.critical("no action")

    if action == "remove student":
      email = request.form.get("email")
      logic.RemoveStudentFromWaitlist(institution, session, email, class_id)
      return self.RedirectToSelf(institution, session, class_id, "removed %s" % email)

    return self.RedirectToSelf(institution, session, class_id, "Unknown action")

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
    class_id = request.args.get("class_id")
    if not class_id:
      current_app.logger.critical("no class_id")

    message = request.args.get('message')
    session_query = urllib.parse.urlencode({'institution': institution,
                                            'session': session})

    waitlist = models.ClassWaitlist.FetchEntity(institution, session, class_id)
    waitlist['emails'].sort()
    students = models.Students.FetchJson(institution, session)
    addStudentData(waitlist, students)
    classes = models.Classes.FetchJson(institution, session)
    class_details = ''
    for c in classes:
      if (str(c['id']) == class_id):
        class_details = c
        break
    return render_template('class_waitlist.html', 
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      session_query=session_query,
      class_waitlist=waitlist,
      students=students,
      class_details=class_details
    )
