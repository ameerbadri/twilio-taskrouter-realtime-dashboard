#!/usr/bin/python
import os
from flask import Flask, request, Response, jsonify, send_from_directory
# from flask_cors import CORS, cross_origin
import requests
from requests.auth import HTTPBasicAuth
import json
import logging
from twilio.rest import Client
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import SyncGrant

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

#Task to Worker mapping
task_worker = {}
# Task Sid to Recording URls mapping
task_sid_recording_url = {}

# Twilio Settings
twilio_account_sid = os.environ["TWILIO_ACCOUNT_SID"]
twilio_auth_token = os.environ["TWILIO_AUTH_TOKEN"]
twilio_api_key = os.environ["TWILIO_API_KEY"]
twilio_api_secret = os.environ["TWILIO_API_SECRET"]
twilio_sync_service_id = os.environ["TWILIO_SYNC_SERVICE_ID"]
twilio_workspace_sid = os.environ["TWILIO_WORKSPACE_SID"]
twilio_workflow_sid = os.environ["TWILIO_WORKFLOW_SID"]

# Create Client to access Twilio resources
client = Client(twilio_account_sid, twilio_auth_token)

@app.route('/sync_taskrouter_statistics', methods=['GET'])
def sync_taskrouter_statistics():
    # Get TaskRouter Statistics
    stats = {}
    # Get Workspace related stats from last 60 minutes
    statistics = client.taskrouter.workspaces(twilio_workspace_sid).statistics().fetch(minutes=60)
    stats['totalTasks'] = statistics.realtime['total_tasks']
    stats['totalWorkers'] = statistics.realtime['total_workers']
    task_statuses = statistics.realtime['tasks_by_status']
    for (k, v) in task_statuses.items():
        print(k, v)
        task_status = k + 'Tasks'
        stats[task_status] = statistics.realtime['tasks_by_status'][k]

    for x in statistics.realtime['activity_statistics']:
        if (x['friendly_name'] == 'Offline'):
            stats['activityOfflineWorkers'] = x['workers']
        elif (x['friendly_name'] == 'Idle'):
            stats['activityIdleWorkers'] = x['workers']
        elif (x['friendly_name'] == 'Reserved'):
            stats['activityReservedWorkers'] = x['workers']
        elif (x['friendly_name'] == 'Busy'):
            stats['activityBusyWorkers'] = x['workers']

    stats['avgTaskAcceptanceTime'] = statistics.cumulative["avg_task_acceptance_time"]
    stats['startTime'] = statistics.cumulative["start_time"]
    stats['endTime'] = statistics.cumulative["end_time"]

    new_data = {'Data': json.dumps(stats)}
    print('Workspace Statistics: ' + json.dumps(new_data, indent=2))
    sync_document = 'SyncTaskRouterStats'
    url = 'https://sync.twilio.com/v1/Services/' + twilio_sync_service_id + '/Documents/' + sync_document
    response = requests.request("POST", url, data=new_data, auth=HTTPBasicAuth(twilio_account_sid, twilio_auth_token))
    print(response.text)
    return (response.text)

@app.route('/taskrouter_event', methods=['POST'])
def taskrouter_event():
    request_dict = {}
    request_dict = request.form.to_dict()

    # Store the Task to WorkerName mapping in process
    if (request_dict['EventType'] == 'reservation.accepted' or request_dict['EventType'] == 'reservation.created'):
        task_worker[request_dict['TaskSid']] = request_dict['WorkerName']

    new_data = {'Data': json.dumps(request_dict)}
    print(new_data)
    sync_document = 'SyncTaskRouterEvents'
    url = 'https://sync.twilio.com/v1/Services/' + twilio_sync_service_id + '/Documents/' + sync_document
    response = requests.request("POST", url, data=new_data, auth=HTTPBasicAuth(twilio_account_sid, twilio_auth_token))
    print(response.text)

    # Sync all Statistics
    sync_taskrouter_statistics()
    # Sync all Tasks
    #sync_taskrouter_tasks()
    return 'OK'

@app.route('/taskrouter_tasks', methods=['GET'])
def taskrouter_tasks():
    current_tasks = client.taskrouter.workspaces(twilio_workspace_sid).tasks.list(ordering='Priority:desc,DateCreated:asc')
    task_model = {}
    tasks_results = []
    for task in current_tasks:
        task_model['TaskSid'] = task.sid
        task_model['Priority'] = task.priority
        attributes = json.loads(task.attributes)
        for (key, value) in attributes.items():
            task_model[key] = value
        try:
            task_model['WorkerName'] = task_worker[task.sid]
        except:
            task_model['WorkerName'] = ""
        # Workaround to Video channel task missing team name
        if (task_model['channel'] == 'video'):
            task_model['team'] = 'Support'

        # Get previously stored recording url
        try:
            task_model['RecordingUrl'] = task_sid_recording_url[task.sid]
        except:
            task_model['RecordingUrl'] = ""

        task_model['TaskStatus'] = task.assignment_status
        tasks_results.append(dict(task_model))
    result = json.dumps(tasks_results)
    print(result)
    return result

@app.route('/sync_taskrouter_tasks', methods=['GET'])
def sync_taskrouter_tasks():
    results = json.loads(taskrouter_tasks())
    sync_map = 'SyncTaskRouterTasks'
    new_data = {}

    print(len(results))
    print(results)

    # Delete the current Sync Map and re-create if we have Tasks
    if (len(results) > 0):
        # Delete the Sync Map
        url = "https://sync.twilio.com/v1/Services/' + twilio_sync_service_id + '/Maps/" + sync_map
        response = requests.request("DELETE", url, auth=HTTPBasicAuth(twilio_account_sid, twilio_auth_token))
        print('Map Deleted')
        print(response)

        # Re-create the Sync Map
        new_data = {'UniqueName': sync_map}
        url = 'https://sync.twilio.com/v1/Services/' + twilio_sync_service_id + '/Maps'
        response = requests.request("POST", url, data=new_data, auth=HTTPBasicAuth(twilio_account_sid, twilio_auth_token))
        print('Map Created')
        print(response)

        for result in results:
            item_key = result['TaskSid']
            new_data = {'Key': item_key,
                        'Data': json.dumps(result)}
            print(new_data)
            # Insert into Sync Map
            url = 'https://sync.twilio.com/v1/Services/' + twilio_sync_service_id + '/Maps/' + sync_map + '/Items'
            response = requests.request("POST", url, data=new_data, auth=HTTPBasicAuth(twilio_account_sid, twilio_auth_token))
            print(response.text)
    return 'OK'


@app.route('/taskrouter_recording_callback', methods=['POST'])
def taskrouter_recording_callback():
    task_sid = request.values.get('TaskSid', '')
    request_dict = {}
    request_dict = request.form.to_dict()
    recording_url = request_dict["RecordingUrl"] + ".mp3"
    task_sid_recording_url[task_sid] = recording_url
    #print(json.dumps(task_sid_recording_url))
    return 'OK'


@app.route('/taskrouter_workers', methods=['GET'])
def taskrouter_workers():
    workers = client.taskrouter.workspaces(twilio_workspace_sid).workers.list()
    worker_model = {}
    workers_results = []
    for worker in workers:
        worker_model['worker_sid'] = worker.sid
        worker_model['friendly_name'] = worker.friendly_name
        worker_model['activity_name'] = worker.activity_name
        worker_model['account_sid'] = worker.account_sid
        worker_model['workspace_sid'] = worker.workspace_sid
        attributes = json.loads(worker.attributes)
        for (key, value) in attributes.items():
            worker_model[key] = value
            print(key, value)
        workers_results.append(dict(worker_model))
    result = json.dumps(workers_results)
    return result


@app.route('/create_test_calls', methods=['GET'])
def create_test_calls():
    total_inbound_calls = int(request.values.get('calls', '1'))
    for x in range(0, total_inbound_calls):
        print (x)
        url = "http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical&Message=This%20is%20a%20test%20call%20number%20" + str(x) + '&'
        call = client.calls.create(to="+16502295161", from_="+447477471576", send_digits="ww1", url=url)
        print(call.sid)
    return "OK"

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/<path:path>')
def send_js(path):
    return send_from_directory('static', path)

def create_sync_map(userid):
    map_instance = client.sync.services(twilio_sync_service_id).sync_maps.create(unique_name=userid)
    return (map_instance.sid)


@app.route('/token')
def token():
    # get the userid from the incoming request
    identity = request.values.get('identity', None)
    # Create access token with credentials
    token = AccessToken(twilio_account_sid, twilio_api_key, twilio_api_secret, identity=identity)
    # Create a Sync grant and add to token
    sync_grant = SyncGrant(service_sid=twilio_sync_service_id)
    token.add_grant(sync_grant)
    # Return token info as JSON
    return jsonify(identity=identity, token=token.to_jwt().decode('utf-8'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, threaded=True)
