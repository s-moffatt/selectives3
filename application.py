import webapp2

import index
import welcome
import institution
import dayparts
import classes
import students
import requirements
import verification
import preferences
import impersonation
import scheduler
import groups_classes
import schedule
import groups_students
import class_list
import class_roster
import error_check
import spots_available
import preregistration
import catalog_print
import catalog_full
import catalog_full_print
import logout
import postregistration
import print_schedule
import rosters
import coming_soon
import serving_rules
import auto_register

application = webapp2.WSGIApplication([
  ('/', index.Index),
  ('/welcome', welcome.Welcome),
  ('/institution', institution.Institution),
  ('/dayparts', dayparts.Dayparts),
  ('/classes', classes.Classes),
  ('/students', students.Students),
  ('/requirements', requirements.Requirements),
  ('/verification', verification.Verification),
  ('/preferences', preferences.Preferences),
  ('/schedule', schedule.Schedule),
  ('/impersonation', impersonation.Impersonation),
  ('/scheduler', scheduler.Scheduler),
  ('/groups_classes', groups_classes.GroupsClasses),
  ('/groups_students', groups_students.GroupsStudents),
  ('/class_list', class_list.ClassList),
  ('/class_roster', class_roster.ClassRoster),
  ('/error_check', error_check.ErrorCheck),
  ('/spots_available', spots_available.SpotsAvailable),
  ('/preregistration', preregistration.Preregistration),
  ('/catalog_print', catalog_print.CatalogPrint),
  ('/catalog_full', catalog_full.CatalogFull),
  ('/catalog_full_print', catalog_full_print.CatalogFullPrint),
  ('/logout', logout.LogoutPage),
  ('/postregistration', postregistration.Postregistration),
  ('/print_schedule', print_schedule.PrintSchedule),
  ('/rosters', rosters.Rosters),
  ('/coming_soon', coming_soon.ComingSoon),
  ('/serving_rules', serving_rules.ServingRules),
  ('/auto_register', auto_register.AutoRegister),
], debug=True)
