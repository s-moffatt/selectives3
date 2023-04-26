from flask import render_template, redirect, request, current_app
from flask.views import MethodView
import urllib.parse

import models
import authorizer
#import error_check_logic

class Institution(MethodView):

  def RedirectToSelf(self, institution, message):
    return redirect("/institution?%s" % urllib.parse.urlencode(
      {'message': message, 'institution': institution}))
   
  def post(self):
    #auth = authorizer.Authorizer(self)
    #if not auth.CanAdministerInstitutionFromUrl():
    #  return auth.Redirect()
      
    institution = request.args.get("institution")
    action = request.form.get("action");

    if action == "add_admin":
      email = request.form.get("administrator")
      models.Admin.Store(institution, email)
      return self.RedirectToSelf(institution, 'added admin %s' % email)
      

    if action == "delete_admin":
      msgs = []
      administrators = request.form.getlist("administrator")
      for email in administrators:
        msgs.append(email)
        models.Admin.Delete(institution, email)
      return self.RedirectToSelf(institution, 'deleted admins %s' % ','.join(msgs))
      

    if action == "add_session":
      name = request.form.get("session")
      current_app.logger.info('adding session: %s for institution: %s' % (name, institution))
      models.Session.Store(institution, name, data={'active': False})
      # Set current database version when creating a new session
      # so we don't get upgrade error message.
#      error_check_logic.Checker.setDBVersion(institution, name)
      return self.RedirectToSelf(institution, 'added session %s' % name)
      

    if action == "remove_session":
      name = request.form.get("session")
      current_app.logger.info('removing session: %s from institution: %s' % (name, institution))
      models.Session.Delete(institution, name)
      return self.RedirectToSelf(institution, 'removed session %s' % name)
      

    if action == "enable_logins":
      name = request.form.get("session")
      current_app.logger.info('enable session: %s from institution: %s' % (name, institution))
      models.Session.enable(institution, name)
      return self.RedirectToSelf(institution, 'enabled logins for %s' % name)


    if action == "disable_logins":
      name = request.form.get("session")
      current_app.logger.info('disable session: %s from institution: %s' % (name, institution))
      models.Session.disable(institution, name)
      return self.RedirectToSelf(institution, 'disabled logins for %s' % name)
      

    name = request.args.get("session")
    error = 'Unexpected action: %s session: %s institution: %s' % ( action, name, institution)
    current_app.logger.error('%s',error)
    return self.RedirectToSelf(institution, error)

  def get(self):
    auth = authorizer.Authorizer()
    if not auth.CanAdministerInstitutionFromUrl():
      return auth.Redirect()

    institution = request.args.get("institution")

    # Hack: fixing a bug. URL parameters override posted form fields.
    # so lets get rid of the offending url parameter
    if request.args.get("session"):
      return self.RedirectToSelf(institution, "hack remove session from url")

    administrators = models.Admin.FetchAll(institution)
    sessions = models.Session.FetchAllEntities(institution)
    #serving_session = models.ServingSession.FetchEntity(institution)
    #current_app.logger.info("currently serving session = %s", serving_session)

    sessions_and_urls = []
    for session in sessions:
      args = urllib.parse.urlencode({'institution': institution,
                               'session': session.key.id_or_name})
      sessions_and_urls.append(
          {'name': session.key.id_or_name,
           'management_url': ('/dayparts?%s' % args),
           'active_session': session['active'],
          })

    message = request.args.get('message')
    return render_template('institution.html', 
      uid=auth.uid,
      institution=institution,
      sessions=sessions_and_urls,
      administrators=administrators,
      message=message
    )
