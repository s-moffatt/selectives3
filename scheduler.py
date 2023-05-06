from flask import render_template, redirect, request, current_app, abort
from flask.views import MethodView
import urllib.parse
import random

import authorizer
import models
import logic

class Scheduler(MethodView):

  def RedirectToSelf(self, institution, session, message):
    return redirect("/scheduler?%s" % urllib.parse.urlencode(
        {'message': message, 
         'institution': institution,
         'session': session}))

  def ClearPrefs(self, institution, session):
    students = models.Students.FetchJson(institution, session)
    classes = models.Classes.FetchJson(institution, session)
    for student in students:
      email = student['email']
      #TODO find the list of eligible classes for each student
      models.Preferences.Store(email, institution, session,
                               [], [], [])

  def RandomPrefs(self, institution, session):
    students = models.Students.FetchJson(institution, session)
    classes = models.Classes.FetchJson(institution, session)
    for student in students:
      email = student['email']
      eligible_class_ids = logic.EligibleClassIdsForStudent(
          institution, session, student, classes)
      eligible_class_ids = set(eligible_class_ids)
      want = random.sample(eligible_class_ids, min(len(eligible_class_ids),random.randint(1,5)))
      dontwant = random.sample(eligible_class_ids.difference(want), min(len(eligible_class_ids.difference(want)),random.randint(1,5)))
      # want = [str(item) for item in want]
      # dontwant = [str(item) for item in dontwant]
      models.Preferences.Store(email, institution, session,
                               want, [], dontwant)

  def ClearAllSchedules(self, institution, session):
    students = models.Students.FetchJson(institution, session)
    for student in students:
      empty_class_ids = ''
      models.Schedule.Store(institution, session,
                            student['email'].lower(),
                            empty_class_ids)
    classes = models.Classes.FetchJson(institution, session)
    for class_obj in classes:
      no_student_emails = ""
      models.ClassRoster.Store(institution, session,
                               class_obj,
                               no_student_emails)

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

    action = request.form.get("action")
    if action == "Clear Prefs":
      self.ClearPrefs(institution, session)
    if action == "Random Prefs":
      self.RandomPrefs(institution, session)
    if action == "Clear Schedules":
      self.ClearAllSchedules(institution, session)
    return self.RedirectToSelf(institution, session, "saved classes")

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

    num_students = len(models.Students.FetchJson(institution, session))

    return render_template('scheduler.html',
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      session_query=session_query,
      self=request.url,
      num_students=num_students,
    )
