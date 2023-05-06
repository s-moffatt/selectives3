from flask import render_template, redirect, request, current_app, jsonify, abort
from flask.views import MethodView
import urllib.parse

import models
import authorizer
import logic



class Schedule(MethodView):

  def RedirectToSelf(self, institution, session, student, message):
    return redirect("/schedule?%s" % urllib.parse.urlencode(
        {'message': message, 
         'student': student,
         'institution': institution,
         'session': session}))

  def post(self):
    auth = authorizer.Authorizer()
    if not auth.HasStudentAccess():
      abort(403) # Forbidden

    institution = request.args.get("institution") or request.form.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.args.get("session") or request.form.get("session")
    if not session:
      current_app.logger.critical("no session")

    if not auth.HasPageAccess(institution, session, "schedule"):
      abort(403) # Forbidden

    email = auth.student_email
    class_id = request.form.get("class_id")
    action = request.form.get("action")

    if action == "add":
      logic.AddStudentToClass(institution, session, email, class_id)
    if action == "del":
      logic.RemoveStudentFromClass(institution, session, email, class_id)
    schedule = models.Schedule.Fetch(institution, session, email)
    schedule = schedule.split(",")
    if schedule and schedule[0] == "":
      schedule = schedule[1:]
    return jsonify(schedule)

  def get(self):
    auth = authorizer.Authorizer()
    if not auth.HasStudentAccess():
      return auth.Redirect()

    institution = request.args.get("institution") or request.form.get("institution")
    if not institution:
      current_app.logger.critical("no institution")
    session = request.args.get("session") or request.form.get("session")
    if not session:
      current_app.logger.critical("no session")
      
    if not auth.HasPageAccess(institution, session, "schedule"):
      return auth.RedirectTemporary(institution, session)

    message = request.args.get('message')
    session_query = urllib.parse.urlencode({'institution': institution,
                                      'session': session})
    email = auth.student_email
    dayparts = models.Dayparts.FetchJson(institution, session)
    if not dayparts:
      dayparts = []
    classes = models.Classes.FetchJson(institution, session)
    try:
      _ = [c for c in classes]
    except TypeError:
      classes = []
    classes_by_daypart = {}
    dayparts_ordered = []

    max_row = max([daypart['row'] for daypart in dayparts])
    max_col = max([daypart['col'] for daypart in dayparts])
      
    # order the dayparts by row and col specified in yaml
    for row in range(max_row):
      dayparts_ordered.append([])
      for col in range(max_col):
        found_daypart = False
        for dp in dayparts:
          if dp['row'] == row+1 and dp['col'] == col+1:
            dayparts_ordered[row].append(dp['name'])
            found_daypart = True
        if found_daypart == False:
          dayparts_ordered[row].append('')
    eligible_classes = logic.EligibleClassIdsForStudent(
        institution, session, auth.student_entity, classes)
    for daypart in dayparts:
      classes_by_daypart[daypart['name']] = []
    classes_by_id = {}
    use_full_description = auth.CanAdministerInstitutionFromUrl()
    for c in classes:
      class_id = str(c['id'])
      if class_id not in eligible_classes:
        continue
      classes_by_id[class_id] = c
      c['hover_text'] = logic.GetHoverText(institution, session, use_full_description, c)
      c['description'] = logic.GetHTMLDescription(institution, session, c)
      for daypart in [s['daypart'] for s in c['schedule']]:
        if daypart in classes_by_daypart:
          classes_by_daypart[daypart].append(c)
    for daypart in classes_by_daypart:
      classes_by_daypart[daypart].sort(key=lambda c:c['name'])
      
    schedule = models.Schedule.Fetch(institution, session, email)
    schedule = schedule.split(",")
    if schedule and schedule[0] == "":
      schedule = schedule[1:]

    config = models.Config.Fetch(institution, session)
    return render_template("schedule.html", 
      uid=auth.uid,
      institution=institution,
      session=session,
      message=message,
      session_query=session_query,
      student=auth.student_entity,
      #dayparts=dayparts,
      classes_by_daypart=classes_by_daypart,
      dayparts_ordered=dayparts_ordered,
      schedule=current_app.json.dumps(schedule),
      classes_by_id=classes_by_id,
      html_desc=config['htmlDesc'],
      impersonation=f"&student={auth.student_email}" if auth.email!=auth.student_email else ""
    )
