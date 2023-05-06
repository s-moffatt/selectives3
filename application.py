from flask import Flask, request, redirect, make_response, current_app, g as app_ctx
import time
import datetime

from firebase_admin import initialize_app

import views
import reports

import index
import welcome
import institution
import verification
import preferences
import impersonation
import scheduler
#import groups_classes
import schedule
#import groups_students
#import class_list
import class_roster
import error_check
import spots_available
#import spots_firm
import preregistration
#import logout
import postregistration
import print_schedule
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
import error_registration
#import teachers
#import teacher.courses
#import teacher.take_attendance
#import teacher.view_attendance
#import teacher.view_by_homeroom
import class_waitlist
import hover_text
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

for k,v in views.Views.items():
  if v["view"] == "Form":
    app.add_url_rule(v["route"], view_func=views.FormClass(k, 
        save=v.get("save"),
        after_save=v.get("after_save"), 
        get_data=v.get("get_data"),
        get_jdata=v.get("get_jdata"),
        url_args=v.get("url_args"),
        ).as_view())

for k,v in reports.Reports.items():
  if v["view"] == "Report":
    app.add_url_rule(v["route"], view_func=reports.ReportClass(k, 
        get_data=v.get("get_data"),
        ).as_view())

app.add_url_rule('/', view_func=index.Index.as_view('index'))
app.add_url_rule('/welcome', view_func=welcome.Welcome.as_view('welcome'))
app.add_url_rule('/institution', view_func=institution.Institution.as_view('institution'))
app.add_url_rule('/verification', view_func=verification.Verification.as_view('verification'))
app.add_url_rule('/preferences', view_func=preferences.Preferences.as_view('preferences'))
app.add_url_rule('/schedule', view_func=schedule.Schedule.as_view('schedule'))
app.add_url_rule('/impersonation', view_func=impersonation.Impersonation.as_view('impersonation'))
app.add_url_rule('/scheduler', view_func=scheduler.Scheduler.as_view('scheduler'))
#app.add_url_rule('/class_list', view_func=class_list.ClassList.as_view('class_list'))
app.add_url_rule('/class_roster', view_func=class_roster.ClassRoster.as_view('class_roster'))
app.add_url_rule('/error_check', view_func=error_check.ErrorCheck.as_view('error_check'))
app.add_url_rule('/spots_available', view_func=spots_available.SpotsAvailable.as_view('spots_available'))
#app.add_url_rule('/spots_firm', view_func=spots_firm.SpotsFirm.as_view('spots_firm'))
app.add_url_rule('/preregistration', view_func=preregistration.Preregistration.as_view('preregistration'))
#app.add_url_rule('/logout', view_func=logout.LogoutPage.as_view('logout'))
app.add_url_rule('/postregistration', view_func=postregistration.Postregistration.as_view('postregistration'))
app.add_url_rule('/print_schedule', view_func=print_schedule.PrintSchedule.as_view('print_schedule'))
#app.add_url_rule('/rosters', view_func=rosters.Rosters.as_view('rosters'))
#app.add_url_rule('/coming_soon', view_func=coming_soon.ComingSoon.as_view('coming_soon'))

#app.add_url_rule('/report/attendance_list', view_func=report.attendance_list.AttendanceList.as_view('attendance_list'))
#app.add_url_rule('/report/student_schedules', view_func=report.student_schedules.StudentSchedules.as_view('student_schedules'))
#app.add_url_rule('/report/signup_card', view_func=report.signup_card.SignupCard.as_view('signup_card'))
#app.add_url_rule('/report/signup_main', view_func=report.signup_main.SignupMain.as_view('signup_main'))
#app.add_url_rule('/report/homeroom', view_func=report.homeroom.Homeroom.as_view('homeroom'))
#app.add_url_rule('/report/label', view_func=report.label.Label.as_view('label'))
app.add_url_rule('/error_registration', view_func=error_registration.ErrorRegistration.as_view('error_registration'))
#app.add_url_rule('/teachers', view_func=teachers.Teachers.as_view('teachers'))
#app.add_url_rule('/teacher/courses', view_func=teacher.courses.Courses.as_view('courses'))
#app.add_url_rule('/teacher/take_attendance', view_func=teacher.take_attendance.TakeAttendance.as_view('take_attendance'))
#app.add_url_rule('/teacher/view_attendance', view_func=teacher.view_attendance.ViewAttendance.as_view('view_attendance'))
#app.add_url_rule('/teacher/view_by_homeroom', view_func=teacher.view_by_homeroom.ViewByHomeroom.as_view('view_by_homeroom'))
app.add_url_rule('/class_waitlist', view_func=class_waitlist.ClassWaitlist.as_view('class_waitlist'))
app.add_url_rule('/hover_text', view_func=hover_text.HoverText.as_view('hover_text'))
#app.add_url_rule('/materials', view_func=materials.Materials.as_view('materials'))
#app.add_url_rule('/welcome_setup', view_func=welcome_setup.WelcomeSetup.as_view('welcome_setup'))
#app.add_url_rule('/report/student_schedules_marked', view_func=report.student_schedules_marked.StudentSchedulesMarked.as_view('student_schedules_marked'))
#app.add_url_rule('/report/taken', view_func=report.taken.Taken.as_view('taken'))
#app.add_url_rule('/report/not_taken', view_func=report.not_taken.NotTaken.as_view('not_taken'))
#app.add_url_rule('/report/student_emails', view_func=report.student_emails.StudentEmails.as_view('student_emails'))
#app.add_url_rule('/closed', view_func=closed.Closed.as_view('closed'))

if __name__ == "__main__":
    app.run()
