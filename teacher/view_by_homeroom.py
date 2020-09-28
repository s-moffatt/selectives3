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

class ViewByHomeroom(webapp2.RequestHandler):
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
    selected_homeroom = self.request.get('selected_homeroom')
    selected_daypart = self.request.get('selected_daypart')
    if not selected_homeroom:
      selected_homeroom = 'All'
    if not selected_daypart:
      selected_daypart = 'All'
    session_query = urllib.urlencode({'institution': institution,
                                      'session': session})

    dayparts = models.Dayparts.FetchJson(institution, session)
    students = models.Students.FetchJson(institution, session)
    if not students: students = []
    students_dict = {}
    homeroom_nums = [] # unique homeroom numbers
    for s in students:
      s['email'] = s['email'].lower()
      students_dict[s['email']] = s
      if s['current_homeroom'] not in homeroom_nums:
        homeroom_nums.append(s['current_homeroom'])
    homeroom_nums.sort()
    classes = models.Classes.FetchJson(institution, session)
    if not classes: classes = []

    def getClassesByHomeroom(room_num):
      classes_to_display = []
      for c in classes:
        class_dayparts = [s['daypart'] for s in c['schedule']]
        if selected_daypart == 'All' or selected_daypart in class_dayparts:
          roster = models.ClassRoster.FetchEntity(institution, session, c['id'])
          if not roster:
            continue
          roster_by_homeroom = [students_dict[email] for email in roster['emails']
                                if students_dict[email]['current_homeroom'] == room_num]
          if len(roster_by_homeroom) == 0:
            continue
          newClass = dict(c)
          newClass['roster'] = roster_by_homeroom
          newClass['roster'].sort(key=lambda s: s['last']) 
          attendance = models.Attendance.FetchJson(institution, session, str(c['id']))
          if attendance:
            # First date is for lookups, second truncated date is for displaying
            newClass['dates_sorted'] = [[d, d[-5:]] for d in sorted(attendance.keys())]
            newClass['attendance'] = attendance
          newClass['daypart'] = "/".join([str(dp['daypart'])
                                     for dp in c['schedule']])
          newClass['location'] = "/".join([str(dp['location'])
                                      for dp in c['schedule']])
          classes_to_display.append(newClass)
      classes_to_display.sort(key=alphaOrder)
      return classes_to_display
      
    classes_by_homeroom = {}
    if selected_homeroom == 'All':
      for room in homeroom_nums:
        classes_by_homeroom[room] = getClassesByHomeroom(room)
    else:
      classes_by_homeroom[selected_homeroom] = getClassesByHomeroom(int(selected_homeroom))

    template_values = {
      'user_email' : auth.email,
      'institution' : institution,
      'session' : session,
      'session_query': session_query,
      'teacher': auth.teacher_entity,
      'dayparts' : dayparts,
      'selected_daypart': selected_daypart,
      'selected_homeroom': selected_homeroom,
      'homeroom_nums': homeroom_nums,
      'classes_by_homeroom': classes_by_homeroom,
    }
    template = JINJA_ENVIRONMENT.get_template('teacher/view_by_homeroom.html')
    self.response.write(template.render(template_values))