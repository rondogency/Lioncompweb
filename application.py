from __future__ import print_function
import uuid
import decimal
from boto3.dynamodb.conditions import Key, Attr
from flask import Flask, request
from flask import render_template
from flask_socketio import SocketIO, emit, leave_room, join_room, send
import facebook
import boto3
import re
import json

application = Flask(__name__)

socketio = SocketIO(application)

acc_token = 'EAAZABSTsjkwEBABd5p2xh74xyergfCOs8uAVDn9H6qNPss2JRF8Xf6iDje46NZATiI6gCtnhDdNx7xVBYvi2zmudkwakzuEPK8gd67ZAA3mfNeDeWhPcQOOlrYyBqiVL8lUXkWUG4Yf4ZBgu0RfUGp0MjSl2gexopOSuBweungZDZD'

# boto3.resource(
#             'dynamodb',
#             region_name=os.environ['AWS_DYNAMO_REGION'],
#             endpoint_url=os.environ['AWS_DYNAMO_ENDPOINT'],
#             aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
#             aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'])

db = boto3.resource('dynamodb')
s3 = boto3.resource('s3')

user_table = db.Table('User')
route_table = db.Table('Route')
group_table = db.Table('Group')


# Get SNS resource
client = boto3.client('sns', region_name = 'us-west-2')
response = client.create_topic(Name = 'emergencyContact')
topicArn = response['TopicArn']
subscribeResponse = client.subscribe(TopicArn = topicArn, Protocol = 'SMS', Endpoint = '1-917-331-4849')


@application.route('/', methods=['GET', 'POST', 'PUT'])
def index():
    return render_template('index.html')


@application.route('/map')
def map():
    return render_template('map.html')


@application.route('/explore')
def explore():
    print("loading explore")
    graph = facebook.GraphAPI(access_token=acc_token)
    Profile = graph.get_object('me')
    user_id = Profile['id']
    response = group_table.scan(
        FilterExpression=Attr('flag').eq(1)
    )
    restGroup = []
    activeGroup = []
    owner = False
    items = response['Items']
    for item in items:
        if decimal.Decimal(user_id) in [dic['id'] for dic in item['user_list']]:
            if decimal.Decimal(user_id) == [dic['id'] for dic in item['user_list']][0]:
                owner = True
                activeGroup = item
            else:
                activeGroup = item
            group_id = item['GroupID']
            print(group_id)
        else:
            restGroup.append(item)
    context = dict(restGroup=restGroup, activeGroup=activeGroup, owner=owner)
    return render_template('explore.html', **context)


@application.route('/profile')
def profile():
    return render_template('profile.html')


@application.route('/shuttle')
def shuttle():
    return render_template('shuttle.html')


@socketio.on('userPath')
def handle_userPath(message):
    origin = str(message.get('origin'))
    destination = str(message.get('destination'))
    origins = re.findall("\d+\.\d+", origin)
    dests = re.findall("\d+\.\d+", destination)
    travel_type = message.get('travelType')
    travel_mode = message.get('travelMode')
    time = message.get('departureTime')

    graph = facebook.GraphAPI(access_token=acc_token)
    Profile = graph.get_object(id='me')
    user_id = int(Profile['id'])
    route_id = str(uuid.uuid4())
    route_table.put_item(
        Item={
            'RouteID': route_id,
            'originLat': decimal.Decimal(origins[0]),
            'originLong': decimal.Decimal(origins[1]),
            'destinationLat': decimal.Decimal(dests[0]),
            'destinationLong': decimal.Decimal(dests[1]),
            'travel_mode': travel_mode,
            'travel_type': travel_type,
            'departure_time': time,
            'user_id': user_id,
        }
    )
    print('Route created')


@socketio.on('acc_token')
def handle_userProfile(message):
    graph = facebook.GraphAPI(access_token=acc_token)
    Profile = graph.get_object('me')
    user_id = Profile['id']
    user_name = Profile['name']

    response = user_table.query(
        KeyConditionExpression=Key('UserID').eq(user_id)
    )
    if len(response['Items']) == 0:
        user_table.put_item(
            Item={
                'UserID': user_id,
                'UserName': user_name,
            }
        )
    print('User created')


@socketio.on('createGroupPath')
def handle_createGroup(message):
    graph = facebook.GraphAPI(access_token=acc_token)
    Profile = graph.get_object(id='me?')
    user_id = int(Profile['id'])
    user_name = Profile['name']
    users = [{'id': user_id, 'name': user_name}]

    origin = str(message.get('origin'))
    destination = str(message.get('destination'))
    originPosition = str(message.get('originPosition'))
    destinationPosition = str(message.get('destinationPosition'))
    originPositions = re.findall("\d+\.\d+", originPosition)
    destPositions = re.findall("\d+\.\d+", destinationPosition)
    travel_type = message.get('travelType')
    travel_mode = message.get('travelMode')

    if len(message.get('groupDescription')) != 0:
        description = message.get('groupDescription')
    else:
        description = 'No description'

    conversation = [{'name': user_name, 'content': 'Group Created'}]
    time = message.get('departureTime')
    group_id = str(uuid.uuid4())
    group_table.put_item(
        Item={
            'GroupID': group_id,
            'flag': 1,
            'description': description,
            'origin': origin,
            'destination': destination,
            'originLat': decimal.Decimal(originPositions[0]),
            'originLong': decimal.Decimal(originPositions[1]),
            'destinationLat': decimal.Decimal(destPositions[0]),
            'destinationLong': decimal.Decimal(destPositions[1]),
            'travel_mode': travel_mode,
            'travel_type': travel_type,
            'departure_time': time,
            'user_list': users,
            'conversation': conversation
        }
    )
    room = group_id
    join_room(room)
    print('Group created')
    open(r'logs.txt', 'a').write('\n\n' + str(dict(
        origin=origin,
        destination=destination,
        departure_time=time,
        travel_type=travel_type, 
        users=users)))
    s3.Bucket('lionlog').upload_file('logs.txt',
                                     'logs.txt')


@socketio.on('joinGroup')
def handle_join_group(message):
    graph = facebook.GraphAPI(access_token=acc_token)
    Profile = graph.get_object(id='me')
    user_id = int(Profile['id'])
    user_name = Profile['name']
    group_id = message.get('GroupID')
    group_table.update_item(
        Key={
            'GroupID': group_id
        },
        UpdateExpression='SET user_list = list_append(user_list, :user)',
        ExpressionAttributeValues={
            ':user': [{'id': user_id, 'name': user_name}]
        }
    )
    response = group_table.get_item(
        Key={
            'GroupID': group_id
        }
    )
    item = response['Item']
    item['user_list'] = user_id

    print('User added to group')
    open(r'logs.txt', 'a').write('\n\n' + str(item))
    s3.Bucket('lionlog').upload_file('logs.txt',
                                     'logs.txt')
    room = group_id
    join_room(room)
    socketio.emit('notification', {'content': str(user_name) + ' has entered group!'}, room=room)
    print('User added to group')


@socketio.on('leaveGroup')
def handle_leave_group(message):
    graph = facebook.GraphAPI(access_token=acc_token)
    Profile = graph.get_object(id='me')
    user_id = int(Profile['id'])
    user_name = Profile['name']
    group_id = message.get('GroupID')
    group_table.update_item(
        Key={
            'GroupID': group_id
        },
        UpdateExpression='REMOVE user_list[0]'
    )
    room = group_id
    socketio.emit('notification', {'content': str(user_name) + ' has left group!'}, room=room)
    leave_room(room)
    print('User left group')


@socketio.on('sendChat')
def handle_send_chat(message):
    graph = facebook.GraphAPI(access_token=acc_token)
    Profile = graph.get_object(id='me')
    user_id = int(Profile['id'])
    user_name = Profile['name']
    group_id = message.get('GroupID')
    text = message.get('content')
    group_table.update_item(
        Key={
            'GroupID': group_id
        },
        UpdateExpression='SET conversation = list_append(conversation, :item)',
        ExpressionAttributeValues={
            ':item': [{'name': user_name, 'content': text}]
        }
    )
    room = group_id
    socketio.emit('receiveChat', {'content': text}, room=room)


@socketio.on('room')
def handle_join_room(message):
    room = message.get('GroupID')
    join_room(room)


@socketio.on('emergency')
def handle_emergency(coordinates):
    message = "Something bad happened on me! Check " + json.dumps(coordinates)

    publichResponse = client.publish(TopicArn = topicArn, Message = message)

# run the app.
if __name__ == "__main__":
    socketio.run(application)
