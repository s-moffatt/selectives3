# Selectives Web

This is the selectives Python 3 migration.

Selectives web is a Google App Engine program to help schools schedule selectives and assign schedules to students.

## Set up development environment
TODO: Here are instructions to set up the Python 3 version of App Engine with Flask

And instructions to [host your own App Engine test site](https://developer.mozilla.org/en-US/docs/Learn/Common_questions/How_do_you_host_your_website_on_Google_App_Engine).

## Bring up a development site on your local machine
* From a command prompt, start the local development server
```
> cd [source directory]
> dev_appserver.py app.yaml
```
* Since there is no global admin yet, temporarily modify IsGlobalAdmin() in authorizer.py to return True.
* Open `http://localhost:8080` in a Chrome browser.
* Log in and add yourself as a global admin. Remember to restore IsGlobalAdmin.

#### View local datastore
* Open `http://localhost:8000`
* Click Datastore Viewer; select from Entity Kind dropdown; click List Entries.

## Procedure to deploy
1. Test on your local machine.
2. Deploy to your test site and verify everything works in the live site.
3. Deploy to the production site and verify again.
```
> gcloud app deploy --project [your-project]
```
To see the projects and which one is active
```
> gcloud config configurations list
```
## Contacts:
* sarah.y.moffatt@gmail.com
