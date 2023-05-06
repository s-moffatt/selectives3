from flask import request, render_template
from flask.views import MethodView

import models
import authorizer

class Verification(MethodView):

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

    student_info = auth.GetStudentInfo(institution, session)
    if student_info == None:
      student_info = {'first': 'No Data', 'last': '', 'current_grade': 'No Data'}

    return render_template('verification.html', 
      uid=auth.uid,
      institution=institution,
      session=session,
      student_name=student_info.get('first','')+" "+student_info.get('last',''),
      current_grade=student_info['current_grade'],
    )
