from flask import Flask, request, redirect, make_response, current_app, g as app_ctx
import time
import datetime

from firebase_admin import initialize_app

import views
import reports
import apis

import index
import welcome
import institution

app = Flask(__name__)
initialize_app()

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
        post_action=v.get("post_action"),
        save=v.get("save"),
        after_save=v.get("after_save"), 
        get_data=v.get("get_data"),
        get_jdata=v.get("get_jdata"),
        ).as_view())

for k,v in reports.Reports.items():
  if v["view"] == "Report":
    app.add_url_rule(v["route"], view_func=reports.ReportClass(k, 
        get_data=v.get("get_data"),
        ).as_view())

for k,v in apis.APIs.items():
  if v["view"] == "API":
    app.add_url_rule(v["route"], view_func=apis.APIClass(k, 
        get_jdata=v.get("get_jdata"),
        ).as_view())

app.add_url_rule('/', view_func=index.Index.as_view('index'))
app.add_url_rule('/welcome', view_func=welcome.Welcome.as_view('welcome'))
app.add_url_rule('/institution', view_func=institution.Institution.as_view('institution'))

if __name__ == "__main__":
    app.run()
