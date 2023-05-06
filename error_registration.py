from flask import render_template, redirect, request, current_app
from flask.views import MethodView
import urllib.parse

import models
import authorizer

ALL_GRADES = 100

def orderScheduleByDP(sched_obj, classes_by_id):
  schedule_by_dp = {}
  sched_list = sched_obj.get("class_ids").split(',')
  for cId in sched_list:
    c = classes_by_id[int(cId)]
    for dp in c['schedule']:
      schedule_by_dp[dp['daypart']] = {
          'name': c['name'],
          'location': dp['location'],
          'fitness': c.get('fitness', False)}
  return schedule_by_dp

def getErrorMsgs(schedule_by_dp, len_dayparts, institution, session):
  err_msgs = []
  if (len(schedule_by_dp) != len_dayparts):
    err_msgs.append("Incomplete schedule")
  err_msgs.extend(getFitnessErrorMsgs(schedule_by_dp))
  return err_msgs

# Takes a schedule object
#   {'Mon A': {'name': 'PE',
#              'fitness': True,},
#    . . .}
# Returns list of error messages, [] if no error
def getFitnessErrorMsgs(schedule_by_dp):
  num_PE = num_Dance = num_fitness = num_PE_MT = num_PE_TF = 0
  err_msgs = []
  for dp_key, dp_obj in schedule_by_dp.items():
    if (dp_obj['name'] == 'PE'):
      num_PE += 1
      if (dp_key.startswith('Mon') or
          dp_key.startswith('Tues')):
        num_PE_MT += 1
      if (dp_key.startswith('Thurs') or
          dp_key.startswith('Fri')):
        num_PE_TF += 1
    if (dp_obj['name'] == 'Dance'):
      num_Dance += 1
    if (dp_obj['fitness'] == True):
      num_fitness += 1
  if (num_PE < 1 and num_Dance < 2):
    err_msgs.append("At least one PE or Dance required.")
  if num_PE > 2:
    err_msgs.append("Too many PE's, maximum is two.")
  if num_fitness < 2:
    err_msgs.append("At least two PE or PE alternatives required.")
  if num_fitness > 3:
    err_msgs.append("Too many PE or PE alternatives, maximum is three.")
  if num_PE_MT > 1 or num_PE_TF > 1:
    err_msgs.append("Not allowed to have two PE's on Mon/Tues or Thurs/Fri.")
  return err_msgs

class ErrorRegistration(MethodView):
  def get(self):
    auth = authorizer.Authorizer()
    if not auth.CanAdministerInstitutionFromUrl():
      return auth.Redirect()

    user_type = 'None'
    if auth.CanAdministerInstitutionFromUrl():
      user_type = 'Admin'
    elif auth.HasTeacherAccess():
      user_type = 'Teacher'

    institution = request.args.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.args.get("session")
    if not session:
      current_app.logger.critical("no session")

    message = request.args.get('message')
    session_query = urllib.parse.urlencode({'institution': institution,
                                      'session': session})

    err_list = [] # list of tuples where
                  #   first element contains a list of error messages
                  #   second element is the student object
                  #   third element is the student schedule object by daypart

    grade_level = request.args.get("grade_level")
    if grade_level:
      grade_level = int(grade_level)
      len_dayparts = len(models.Dayparts.FetchJson(institution, session))

      classes = models.Classes.FetchJson(institution, session)
      classes_by_id = {}
      for c in classes:
        classes_by_id[c['id']] = c

      students = models.Students.FetchJson(institution, session)
      students.sort(key=lambda s: s['current_homeroom'])
      for s in students:
        if (grade_level != ALL_GRADES) and (s['current_grade'] != grade_level):
          continue
        sched_obj = models.Schedule.FetchEntity(institution, session,
                                              s['email'].lower())
        current_app.logger.info(f"sched_obj=%s" % sched_obj.get("class_ids"))
        if not sched_obj or not sched_obj.get("class_ids"):
          err_list.append((['Missing schedule'], s, {}))
          continue # Entire schedule is missing,
                   # don't bother checking for further errors
        schedule_by_dp = orderScheduleByDP(sched_obj, classes_by_id)
        err_msgs = getErrorMsgs(schedule_by_dp, len_dayparts, institution, session)
        if err_msgs != []:
          err_list.append((err_msgs, s, schedule_by_dp))
    # else no button was clicked, don't do anything

    return render_template("error_registration.html", 
      uid=auth.uid,
      user_type=user_type,
      institution=institution,
      session=session,
      message=message,
      err_list=err_list,
      session_query=session_query,
    )
