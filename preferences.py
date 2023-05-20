from flask import render_template, redirect, request, current_app
from flask.views import MethodView
import urllib.parse

import models
import authorizer
import logic


class Preferences(MethodView):

  def RedirectToSelf(self, institution, session, student, message):
    return redirect("/preferences?%s" % urllib.parse.urlencode(
        {'message': message, 
         'student': student,
         'institution': institution,
         'session': session}))

  def post(self):
    auth = authorizer.Authorizer()
    if not auth.HasStudentAccess():
      return auth.Redirect()

    institution = request.args.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.args.get("session")
    if not session:
      current_app.logger.critical("no session")

    email = auth.student_email
    want = request.form.get("want","").split(",")
    if want[0] == '':
      want.pop(0)
    dontcare = request.form.get("dontcare","").split(",")
    if dontcare[0] == '':
      dontcare.pop(0)
    dontwant = request.form.get("dontwant","").split(",")
    if dontwant[0] == '':
      dontwant.pop(0)
    models.Preferences.Store(email, institution, session,
                             want, dontcare, dontwant)
    if request.form.get("Save") == "Save":
      current_app.logger.info("Form Saved")
    else:
      current_app.logger.info("Auto Save")
    return self.RedirectToSelf(institution, session, email, "Saved Preferences")

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

    if not auth.HasPageAccess(institution, session, "preferences"):
      return auth.RedirectTemporary(institution, session)
      
    message = request.args.get('message')
    session_query = urllib.parse.urlencode({'institution': institution,
                                      'session': session})

    classes = models.Classes.FetchJson(institution, session)
    try:
      _ = [c for c in classes]
    except TypeError:
      classes = []
    classes_by_id = {}
    use_full_description = auth.CanAdministerInstitutionFromUrl()
    for c in classes:
      class_id = str(c['id'])
      class_name = c['name']
      class_desc = logic.GetHoverText(institution, session, use_full_description, c)
      classes_by_id[class_id] = {'name': class_name,
                                 'description': class_desc }
    if not classes_by_id:
      classes_by_id['0'] = {'name': 'None', 'desc': 'None'}
    eligible_class_ids = set(logic.EligibleClassIdsForStudent(
        institution, session, auth.student_entity, classes))

    prefs = models.Preferences.FetchEntity(
        auth.student_email, institution, session)
    current_app.logger.critical(f"prefs={prefs}")
    want_ids     = prefs.get("want","").split(',')
    dontcare_ids = prefs.get("dontcare","").split(',')
    dontwant_ids = prefs.get("dontwant","").split(',')

    new_class_ids = eligible_class_ids.difference(want_ids)
    new_class_ids = new_class_ids.difference(dontcare_ids)
    new_class_ids = new_class_ids.difference(dontwant_ids)
    dontcare_ids = list(new_class_ids) + dontcare_ids
    if dontcare_ids[len(dontcare_ids)-1] == '':
      dontcare_ids.pop()

    def RemoveDeletedClasses(class_ids):
      for class_id in class_ids:
        if class_id in eligible_class_ids:
          yield class_id

    want_ids = list(RemoveDeletedClasses(want_ids))
    dontcare_ids = list(RemoveDeletedClasses(dontcare_ids))
    dontwant_ids = list(RemoveDeletedClasses(dontwant_ids))
    current_app.logger.info('want: ' + ','.join(want_ids));
    current_app.logger.info('dont want: ' + ','.join(dontwant_ids));
    current_app.logger.info('dont care: ' + ','.join(dontcare_ids));
    return render_template("preferences.html",
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      session_query=session_query,
      classes=classes_by_id,
      student=auth.student_entity,
      want_ids=want_ids,
      dontwant_ids=dontwant_ids,
      dontcare_ids=dontcare_ids,
    )
