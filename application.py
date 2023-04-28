from flask import Flask, request, redirect, make_response, current_app, g as app_ctx
import time
import datetime

from firebase_admin import initialize_app

import index
import welcome
import institution
#import dayparts
#import classes
#import students
#import requirements
#import verification
#import preferences
#import impersonation
#import scheduler
#import groups_classes
#import schedule
#import groups_students
#import class_list
#import class_roster
#import error_check
#import spots_available
#import spots_firm
#import preregistration
#import logout
#import postregistration
#import print_schedule
#import rosters
#import coming_soon
#import serving_rules
#import auto_register
#import report.attendance_list
#import report.student_schedules
#import report.signup_card
#import report.signup_main
#import report.homeroom
#import report.label
#import error_registration
#import teachers
#import teacher.courses
#import teacher.take_attendance
#import teacher.view_attendance
#import teacher.view_by_homeroom
#import class_waitlist
#import hover_text
#import materials
#import welcome_setup
#import report.student_schedules_marked
#import report.taken
#import report.not_taken4
#import config
#import report.student_emails
#import closed

app = Flask(__name__)
initialize_app()

@app.after_request
def redirect_headers_after(resp):
    if hasattr(app_ctx, 'redirect'):
        app.logger.info("Setting Selectives-Redirect Header to: %s", app_ctx.redirect)
        resp.headers['Selectives-Redirect']=app_ctx.redirect
    return resp

@app.after_request
def set_session_cookie_after(resp):
    if hasattr(app_ctx, 'session_cookie'):
        app.logger.info("Setting session cookie")
        resp.set_cookie('session', app_ctx.session_cookie, expires=app_ctx.session_cookie_expires, httponly=True, secure=True, samesite='Strict')
    return resp

@app.route('/sessionSignout', methods=['POST'])
def session_logout():
    response = make_response(redirect('/'))
    response.set_cookie('session', expires=0)
    return response

app.add_url_rule('/'            , view_func=index.Index.as_view('index'))
app.add_url_rule('/welcome'     , view_func=welcome.Welcome.as_view('welcome'))
app.add_url_rule('/institution' , view_func=institution.Institution.as_view('institution'))

#application = webapp2.WSGIApplication([
#  ('/dayparts', dayparts.Dayparts),
#  ('/classes', classes.Classes),
#  ('/students', students.Students),
#  ('/requirements', requirements.Requirements),
#  ('/verification', verification.Verification),
#  ('/preferences', preferences.Preferences),
#  ('/schedule', schedule.Schedule),
#  ('/impersonation', impersonation.Impersonation),
#  ('/scheduler', scheduler.Scheduler),
#  ('/groups_classes', groups_classes.GroupsClasses),
#  ('/groups_students', groups_students.GroupsStudents),
#  ('/class_list', class_list.ClassList),
#  ('/class_roster', class_roster.ClassRoster),
#  ('/error_check', error_check.ErrorCheck),
#  ('/spots_available', spots_available.SpotsAvailable),
#  ('/spots_firm', spots_firm.SpotsFirm),
#  ('/preregistration', preregistration.Preregistration),
#  ('/logout', logout.LogoutPage),
#  ('/postregistration', postregistration.Postregistration),
#  ('/print_schedule', print_schedule.PrintSchedule),
#  ('/rosters', rosters.Rosters),
#  ('/coming_soon', coming_soon.ComingSoon),
#  ('/serving_rules', serving_rules.ServingRules),
#  ('/auto_register', auto_register.AutoRegister),
#  ('/report/attendance_list', report.attendance_list.AttendanceList),
#  ('/report/student_schedules', report.student_schedules.StudentSchedules),
#  ('/report/signup_card', report.signup_card.SignupCard),
#  ('/report/signup_main', report.signup_main.SignupMain),
#  ('/report/homeroom', report.homeroom.Homeroom),
#  ('/report/label', report.label.Label),
#  ('/error_registration', error_registration.ErrorRegistration),
#  ('/teachers', teachers.Teachers),
#  ('/teacher/courses', teacher.courses.Courses),
#  ('/teacher/take_attendance', teacher.take_attendance.TakeAttendance),
#  ('/teacher/view_attendance', teacher.view_attendance.ViewAttendance),
#  ('/teacher/view_by_homeroom', teacher.view_by_homeroom.ViewByHomeroom),
#  ('/class_waitlist', class_waitlist.ClassWaitlist),
#  ('/hover_text', hover_text.HoverText),
#  ('/materials', materials.Materials),
#  ('/welcome_setup', welcome_setup.WelcomeSetup),
#  ('/report/student_schedules_marked', report.student_schedules_marked.StudentSchedulesMarked),
#  ('/report/taken', report.taken.Taken),
#  ('/report/not_taken', report.not_taken.NotTaken),
#  ('/config', config.Config),
#  ('/report/student_emails', report.student_emails.StudentEmails),
#  ('/closed', closed.Closed),
#], debug=True)

if __name__ == "__main__":
    app.run()
