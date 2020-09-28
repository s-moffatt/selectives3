import os
import urllib
import jinja2
import webapp2
import logging
import json

import models
import authorizer

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(os.path.dirname(__file__))),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def alphaOrder(c):
  if 'instructor' in c:
    return (c['name'],
            c['instructor'])
  else:
    return (c['name'])

def augmentClass(institution, session, c, students):
  c['daypart'] = "/".join([str(dp['daypart'])
                           for dp in c['schedule']])
  c['location'] = "/".join([str(dp['location'])
                            for dp in c['schedule']])
  roster = models.ClassRoster.FetchEntity(institution, session, c['id'])
  if not roster: roster = {}
  c['roster'] = [students[email] for email in roster['emails']]
  c['roster'].sort(key=lambda s: s['last'])
  attendance = models.Attendance.FetchJson(institution, session, str(c['id']))
  if attendance:
    # First date is for lookups, second truncated date is for displaying
    c['dates_sorted'] = [[d, d[-5:]] for d in sorted(attendance.keys())]
    c['attendance'] = attendance

class ViewAttendance(webapp2.RequestHandler):
  def get(self):
    auth = authorizer.Authorizer(self)
    if not auth.HasTeacherAccess():
      auth.Redirect()
      return

    institution = self.request.get("institution")
    if not institution:
      logging.fatal("no institution")
    session = self.request.get("session")
    if not session:
      logging.fatal("no session")
    selected_daypart = self.request.get('selected_daypart')
    if not selected_daypart:
      selected_daypart = 'All'
    session_query = urllib.urlencode({'institution': institution,
                                      'session': session})

    dayparts = models.Dayparts.FetchJson(institution, session)
    students = models.Students.FetchJson(institution, session)
    if not students: students = []
    students_dict = {}
    for s in students:
      s['email'] = s['email'].lower()
      students_dict[s['email']] = s

    classes_to_display = []
    classes = models.Classes.FetchJson(institution, session)
    if not classes: classes = []
    for c in classes:
      #if 'Core' not in c['name']: #TODO: remove Core classes in a more general way
      if selected_daypart == 'All':
        augmentClass(institution, session, c, students_dict)
        classes_to_display.append(c)
      else:
        for s in c['schedule']:
          if selected_daypart in s['daypart']:
            augmentClass(institution, session, c, students_dict)
            classes_to_display.append(c)
    classes_to_display.sort(key=alphaOrder)

    template_values = {
      'user_email' : auth.email,
      'institution' : institution,
      'session' : session,
      'session_query': session_query,
      'teacher': auth.teacher_entity,
      'dayparts' : dayparts,
      'selected_daypart': selected_daypart,
      'classes': classes_to_display,
    }
    template = JINJA_ENVIRONMENT.get_template('teacher/view_attendance.html')
    self.response.write(template.render(template_values))