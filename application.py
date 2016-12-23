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

acc_token = 'EAAZABSTsjkwEBAKpgQxxSMbEZAyZBIy6BvPjgmvGvY41Ij1xoglPfhZAlDZCLjZBI8mPZCd9bnZBh3nhgLosm7qbOPIzIcva7cLZAwPCCyqeCZBvWSz4dZAaZBhjlz3yhZBc6P2RRCpZCDuQEAdDtKEvNSZCsR2MblqqV2PBrKV8AdbcpFtKwZDZD'

# boto3.resource(
#             'dynamodb',
#             region_name=os.environ['AWS_DYNAMO_REGION'],
#             endpoint_url=os.environ['AWS_DYNAMO_ENDPOINT'],
#             aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
#             aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'])

db = boto3.resource('dynamodb')

user_table = db.Table('User')
route_table = db.Table('Route')
group_table = db.Table('Group')


@application.route('/', methods=['GET', 'POST', 'PUT'])
def index():
    return render_template('index.html')


@application.route('/map')
def map():
    return render_template('map.html')


@application.route('/explore')
def explore():
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
        print(user_id)
        print(item['user_list'])
        if decimal.Decimal(user_id) in [dic['id'] for dic in item['user_list']]:
            if decimal.Decimal(user_id) == [dic['id'] for dic in item['user_list']][0]:
                owner = True
                activeGroup = item
            else:
                activeGroup = item
        else:
            restGroup.append(item)
    context = dict(restGroup=restGroup, activeGroup=activeGroup, owner=owner)
    return render_template('explore.html', **context)


@application.route('/friends')
def friends():
    return render_template('friends.html')


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
    Profile = graph.get_object(id='me?fields=id,name,email,link')
    user_id = int(Profile['id'])
    user_name = Profile['name']
    print(Profile)
    users = [{'id':user_id,'name':user_name}]

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
    #room = group_id
    #join_room(room)
    print('Group created')


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
            ':user': [{'id':user_id,'name':user_name}]
        }
    )
    #room = group_id
    #join_room(room)
    #socketio.emit('notification', {'content': str(user_name) + ' has entered group!'}, room=room)
    socketio.emit('notification', {'content': str(user_name) + ' has entered group!'})
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
    #room = group_id
    #socketio.emit('notification', {'content': str(user_name) + ' has left group!'}, room=room)
    socketio.emit('notification', {'content': str(user_name) + ' has left group!'})
    #leave_room(room)
    print('User left group')


@socketio.on('sendChat')
def handle_send_chat(message):
    text = message
    print(text)
    socketio.emit('receiveChat', {'content': text})

@socketio.on('startTravel')
def handle_start_travel(message):
    pass


@socketio.on('endTravel')
def handle_start_travel(message):
    pass


# run the app.
if __name__ == "__main__":
    socketio.run(application)