from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random
import string
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Store session codes and their associated SocketIO session IDs
sessions = {}  # {session_code: {'sid': socketio_session_id, 'paired_with': target_session_code}}

def generate_session_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route('/')
def index():
    session_code = generate_session_code()
    while session_code in sessions:  # Ensure unique session code
        session_code = generate_session_code()
    sessions[session_code] = {'sid': None, 'paired_with': None}
    return render_template('index.html', session_code=session_code)

@socketio.on('connect')
def handle_connect():
    session_code = request.args.get('session_code')
    if session_code in sessions:
        sessions[session_code]['sid'] = request.sid
    else:
        emit('connection_status', {'status': 'Error: Invalid session code'}, to=request.sid)

@socketio.on('connect_to_session')
def handle_connect_to_session(data):
    target_code = data.get('target_code')
    user_session_code = None
    for code, info in sessions.items():
        if info['sid'] == request.sid:
            user_session_code = code
            break

    if not user_session_code:
        emit('connection_status', {'status': 'Error: Your session not found'}, to=request.sid)
        return

    if target_code == user_session_code:
        emit('connection_status', {'status': 'Error: Cannot connect to your own session'}, to=request.sid)
        return

    if target_code in sessions:
        if sessions[target_code]['sid'] is None:
            emit('connection_status', {'status': 'Error: Target user not connected'}, to=request.sid)
            return
        sessions[user_session_code]['paired_with'] = target_code
        sessions[target_code]['paired_with'] = user_session_code
        emit('connection_status', {'status': f'Connected to {target_code}'}, to=request.sid)
        emit('connection_status', {'status': f'Connected to {user_session_code}'}, to=sessions[target_code]['sid'])
    else:
        emit('connection_status', {'status': 'Invalid session code'}, to=request.sid)

@socketio.on('send_message')
def handle_message(data):
    message = data.get('message')
    if not message:
        emit('connection_status', {'status': 'Error: Empty message'}, to=request.sid)
        return

    user_session_code = None
    for code, info in sessions.items():
        if info['sid'] == request.sid:
            user_session_code = code
            break

    if not user_session_code:
        emit('connection_status', {'status': 'Error: Your session not found'}, to=request.sid)
        return

    target_code = sessions[user_session_code]['paired_with']
    if target_code and target_code in sessions and sessions[target_code]['sid']:
        emit('receive_message', {'message': f'You: {message}'}, to=request.sid)
        emit('receive_message', {'message': f'Other: {message}'}, to=sessions[target_code]['sid'])
    else:
        emit('connection_status', {'status': 'Error: Not connected to a user'}, to=request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    user_session_code = None
    for code, info in sessions.items():
        if info['sid'] == request.sid:
            user_session_code = code
            break

    if user_session_code:
        target_code = sessions[user_session_code]['paired_with']
        if target_code and target_code in sessions:
            sessions[target_code]['paired_with'] = None
            if sessions[target_code]['sid']:
                emit('connection_status', {'status': 'Other user disconnected'}, to=sessions[target_code]['sid'])
        del sessions[user_session_code]

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)