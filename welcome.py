from flask import render_template, url_for, redirect
from flask.views import MethodView

import models
import authorizer

class Welcome(MethodView):
  def post(self):
    return self.get()

  def get(self):
    auth = authorizer.Authorizer()
    if auth.HasStudentAccess():
        return auth.Redirect()
    if auth.HasTeacherAccess():
        return auth.Redirect()
    return render_template('welcome.html', 
      uid=auth.uid,
      welcome_msg= models.Welcome.Fetch()
    )
