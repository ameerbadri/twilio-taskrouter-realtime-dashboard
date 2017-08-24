# twilio-taskrouter-realtime-dashboard
Twilio TaskRouter Realtime Dashboard using Twilio Sync

In a modern contact center that serves customers over multiple channels, realtime monitoring of the tasks and their progress becomes an operational imperative.  Twilio provides all the necessary building blocks to build a contact center (https://github.com/nash-md/twilio-contact-center) and the ability to build a realtime task monitoring dashboard using Twilio Sync (https://www.twilio.com/sync).

This demo shows how such an operational monitoring dashboard could be built.  I've used the following technologies to built this dashbaord

![](taskrouter_dashboard.png)

Note: Please keep in mind the source code shared here (JS and Python) is pretty much demo quality.  For production use, I am sure the code can be optimised significantly.

# Setup

## Step 1: Installing the web app
This will install the web application and all the dependencies on Heroku (login required) for you. As part of the installation, the Heroku app will walk you through configuration of environment variables.  Please click on the following button to deploy the application.

One Click Heroku Deploy of Web App
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/ameerbadri/twilio-taskrouter-realtime-dashboard)

Next, make a note of the URL that Heroku creates as you'll need it for the next Step

## Step 2: Configuring Taskrouter Workspace
