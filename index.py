from flask import render_template, request, redirect, current_app, g as app_ctx
from flask.views import MethodView
import urllib.parse

import models
import authorizer


class Index(MethodView):
  def institutionUrl(self, institution_name):
    args = urllib.parse.urlencode({'institution': institution_name})
    return '/institution?%s' % args

  def RedirectToSelf(self, message):
    return redirect("/?%s" % urllib.parse.urlencode(
      {'message': message}))

  def post(self):
    current_app.logger.info("%s", request.form)
    auth = authorizer.Authorizer()
    if not auth.IsGlobalAdmin():
      return auth.Redirect()

    action = request.form.get("action")
    if action == "add_admin":
      email = request.form.get("administrator")
      models.GlobalAdmin.Store(email)
      return self.RedirectToSelf('added user: ' + email)

    if action == "delete_admin":
      msgs = []
      administrators = request.form.getlist("administrator")
      for email in administrators:
        msgs.append(email)
        models.GlobalAdmin.Delete(email)
      return self.RedirectToSelf('delete users: ' + ','.join(msgs))

    if action == "add_institution":
      name = request.form.get("institution")
      models.Institution.Store(name)
      return self.RedirectToSelf('added institution: ' + name)

  def get(self):
    auth = authorizer.Authorizer()
    if not auth.IsGlobalAdmin():
      return auth.Redirect()

    return render_template('index.html', 
      uid=auth.uid,
      institutions=[{'name':i,'url':self.institutionUrl(i)} for i in models.Institution.FetchAll()],
      administrators=models.GlobalAdmin.FetchAll(),
      message=request.args.get("message"),
      recent_access=models.RecentAccess.Fetch(order=['-date_time'],limit=20)
    )