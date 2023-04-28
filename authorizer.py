#import Cookie
#import os
#import logging
#try:
#  from google.appengine.api import users
#except:
#  current_app.logger.info("google.appengine.api.users not found. "
#                "We must be running in a unit test.")
#import logic
import models
#import urllib
#import yaml

from flask import request, render_template, make_response, current_app, g as app_ctx
import datetime
import time
import urllib.parse

from google.auth import default
from google.cloud import resourcemanager
from firebase_admin import auth, exceptions


def _get_gae_admins():
  'return set of App Engine admins'
  # setup constants for calling Cloud Resource Manager API
  _, PROJ_ID = default(  # Application Default Credentials and project ID
          ['https://www.googleapis.com/auth/cloudplatformprojects.readonly'])
  rm_client = resourcemanager.ProjectsClient()
  _TARGETS = frozenset((     # App Engine admin roles
          'roles/viewer',
          'roles/editor',
          'roles/owner',
          'roles/appengine.appAdmin',
  ))
  # collate users who are members of at least one GAE admin role (_TARGETS)
  admins = set()                      # set of all App Engine admins
  allow_policy = rm_client.get_iam_policy(resource='projects/%s' % PROJ_ID)
  for b in allow_policy.bindings:     # bindings in IAM allow-policy
    if b.role in _TARGETS:            # only look at GAE admin roles
      admins.update(user.split(':', 1).pop() for user in b.members)
  return admins

_ADMINS = _get_gae_admins()

class Authorizer(object):
  """Report the user's access level and Redirect them to their start page."""

  def __init__(self):
    current_app.logger.info("Authorizer.__init__")
    self.email = False
    self.token = False
    self.uid   = False

    self.authenticate()
	
    # record access
    if self.email:
      models.RecentAccess.Store(self.email)
    else:
      models.RecentAccess.Store("anonymous")

  def authenticate(self):  
    # Try to see if session_cookie exists
    session_cookie = request.cookies.get('session')
    # Verify the session cookie. In this case an additional check is added to detect
    # if the user's Firebase session was revoked, user deleted/disabled, etc.
    if session_cookie:
        try:
            decoded_claims = auth.verify_session_cookie(session_cookie, check_revoked=True)
            self.email = decoded_claims.get('email').lower()
            self.uid   = decoded_claims.get('uid') #uid is case-sensitive
            current_app.logger.info("Decoded cookie: %s uid=%s",self.email, self.uid)
            return
        except auth.InvalidSessionCookieError:
            # Session cookie is invalid, expired or revoked. go on and see if new ID token is supplied elsewhere
            current_app.logger.info("Session cookie is invalid, expired or revoked")

    # Try to get the ID token from a few places
    if not self.token:
      self.token = request.headers.get('Authorization')
    #if not self.token:
    #  self.token = request.form.get("token",False)
    #if not self.token:
    #  self.token = request.args.get("token")

    # Try to authenticate
    if self.token:
      try:
        current_app.logger.info("Decoding claim: %s",self.token)
        decoded_claims = auth.verify_id_token(self.token)
        # Only process if the user signed in within the last 5 minutes.
        if True:#time.time() - decoded_claims['auth_time'] < 5 * 60:
          self.email = decoded_claims.get('email').lower() # google capitalizes email addresses sometimes
          self.uid   = decoded_claims.get('uid') #uid is case-sensitive
          current_app.logger.info("Decoded claim: %s uid=%s",self.email, self.uid)
          # Create Cookie in app context to be sent when response object is available; Set session expiration to 5 days.
          expires_in=datetime.timedelta(days=5)
          app_ctx.session_cookie = auth.create_session_cookie(self.token, expires_in=expires_in)
          app_ctx.session_cookie_expires = datetime.datetime.now() + expires_in
        else:
          # User did not sign in recently. To guard against ID token theft, not authenticating.
          current_app.logger.info("User did not sign in recently")
      except auth.InvalidIdTokenError:
          current_app.logger.info("Invalid ID token")
      except exceptions.FirebaseError:
          current_app.logger.error("Failed to create a session cookie")


  def get_roles(self):
    return {'admin': self.email in _ADMINS}, 200

  def IsGlobalAdmin(self):
    if not self.email:
      return False
    if self.email in _ADMINS:
      return True
    return self.email in models.GlobalAdmin.FetchAll()
    # return True  #Toggle with previous line
    # to create a Global Admin on the Admin page.
    # Otherwise on a new instance, you can't get into the system!

  def GetAdministedInstitutionsList(self):
    if not self.email:
      return []
    if self.IsGlobalAdmin():
      return models.Institution.FetchAll()
    return models.Admin.GetInstitutionNames(self.email)

  def CanAdministerInstitutionFromUrl(self):
    if not self.email:
      return False
    if self.IsGlobalAdmin():
      return True
    institution = request.get("institution")
    if not institution:
      return False
    if self.email in models.Admin.FetchAll(institution):
      return True
    return False

  # Administrators can impersonate students by adding student email to the url:
  # * url?student=email@domain
  # The possibly impersonated student email is exported from this class as:
  # * auth.student_email
  def HasStudentAccess(self):
    if not self.email:
      current_app.logger.error("No user")
      return False
    institution = request.args.get("institution")
    if not institution:
      current_app.logger.error("No institution")
      return False
    session = request.args.get("session")
    if not session:
      current_app.logger.error("No session")
      return False
    #if self.CanAdministerInstitutionFromUrl():
    #  return self._VerifyStudent(institution,
    #                             session,
    #                             self.handler.request.get("student").lower())
    #if not self._VerifyServingSession(institution, session):
    #  return False
    #return self._VerifyStudent(institution,
    #                           session,
    #                           self.email)

  def HasTeacherAccess(self):
    if not self.email:
      current_app.logger.error("No user")
      return False
    institution = request.args.get("institution")
    if not institution:
      current_app.logger.error("No institution")
      return False
    session = request.args.get("session")
    if not session:
      current_app.logger.error("No session")
      return False
#    if self.CanAdministerInstitutionFromUrl():
#      return self._VerifyTeacher(institution,
#                                 session,
#                                 self.handler.request.get("teacher").lower())
#    if not self._VerifyServingSession(institution, session):
#      return False
#    return self._VerifyTeacher(institution,
#                               session,
#                               self.email)
#
#  def _VerifyServingSession(self, institution, session):
#    serving_session = models.ServingSession.FetchEntity(institution)
#    current_app.logger.info("currently serving session = %s" % serving_session)
#    if serving_session.session_name == session:
#      return True
#    current_app.logger.error("serving session doesn't match")
#    return False
#
#  def HasPageAccess(self, institution, session, current_page):
#    serving_rules = models.ServingRules.FetchJson(institution, session)
#    page_types = logic.StudentAllowedPageTypes(
#            institution, session, self.student_entity, serving_rules)
#    if current_page in page_types:
#      return True
#    if self.CanAdministerInstitutionFromUrl():
#      # Needed for impersonation page
#      return True
#    return False
#
#  def GetStartPage(self, institution, session):
#    serving_rules = models.ServingRules.FetchJson(institution, session)
#    page_types = logic.StudentAllowedPageTypes(
#             institution, session, self.student_entity, serving_rules)
#    # When a student is listed under multiple serving rules,
#    # return the start page with highest priority.
#    if "schedule" in page_types:
#      return "schedule"
#    if "final" in page_types:
#      return "postregistration"
#    else:
#      return "preregistration"
#
#  def _VerifyStudent(self, institution, session, student_email):
#    # returns true on success
#    students = models.Students.FetchJson(institution, session)
#    student_entity = logic.FindUser(student_email, students)
#    if student_entity:
#      self.student_email = student_email
#      self.student_entity = student_entity
#      return True
#    current_app.logger.error("student not found '%s'" % student_email)
#    return False
#
#  def _VerifyTeacher(self, institution, session, teacher_email):
#    # returns true on success
#    teachers = models.Teachers.FetchJson(institution, session)
#    teacher_entity = logic.FindUser(teacher_email, teachers)
#    if teacher_entity:
#      self.teacher_email = teacher_email
#      self.teacher_entity = teacher_entity
#      return True
#    current_app.logger.error("teacher not found '%s'" % teacher_email)
#    return False
#
  def Redirect(self):
      path = self._Redirect()
      resp = make_response(render_template('base.html', redirect=path))
      current_app.logger.info("Setting Selectives-Redirect Header to: %s", path)
      resp.headers['Selectives-Redirect'] = path
      return resp

  def _Redirect(self):
    current_app.logger.info("Authorizer.Redirect: %s", self.email)
    # are they logged in?
    if not self.email:
      current_app.logger.info("Authorizer.Redirect: not self.email")
      return "/welcome"
    if self.IsGlobalAdmin():
      current_app.logger.info("Authorizer.Redirect: Redirecting %s to index", self.email)
      return "/"
#    # are they an institution admin?
#    institution_list = models.Admin.GetInstitutionNames(self.email)
#    if len(institution_list) > 1:
#      current_app.logger.info("Redirecting %s to /pickinstitution", self.email)
#      self.handler.redirect("/pickinstitution")
#      return
#    if len(institution_list) > 0:
#      institution = institution_list[0]
#      current_app.logger.info("Redirecting %s to /institution", self.email)
#      self.handler.redirect("/institution?%s" % urllib.urlencode(
#          {'institution': institution}))
#      return
#    # are they a student with a serving session?
#    serving_sessions = models.ServingSession.FetchAllEntities()
#    for ss in serving_sessions:
#      institution = ss.institution_name
#      session = ss.session_name
#      verified = self.(institution,
#                                     session,
#                                     self.email)
#      if verified:
#        start_page = self.GetStartPage(institution, session)
#        current_app.logger.info("Redirecting %s to /%s" % (self.email, start_page))
#        self.handler.redirect("/%s?%s" % (start_page, urllib.urlencode(
#            {'institution': institution,
#             'session': session})))
#        return
#    # are they a teacher with a serving session?
#    for ss in serving_sessions:
#      institution = ss.institution_name
#      session = ss.session_name
#      start_page = "teacher/take_attendance"
#      verified = self._VerifyTeacher(institution,
#                                     session,
#                                     self.email)
#      if verified:
#        current_app.logger.info("Redirecting %s to /%s" % (self.email, start_page))
#        self.handler.redirect("/%s?%s" % (start_page, urllib.urlencode(
#            {'institution': institution,
#             'session': session})))
#        return
#    current_app.logger.info("Redirecting %s to /welcome", self.email)
#    self.handler.redirect("/welcome")
    return "/welcome"

#
#  def RedirectTemporary(self, institution, session):
#    self.handler.redirect("/coming_soon?%s" % urllib.urlencode(
#        {'institution': institution,
#         'session': session}))
#
## TODO get rid of the unnecessary handler parameter.
## We really want the request, not the handler, and we could get it from WebApp2.