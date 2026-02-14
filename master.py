#!/usr/bin/env python3
"""
SynergyPlus Master Application
Controls remote servers by capturing and forwarding mouse/keyboard input
Web Interface Version — Extended Display Mode
"""

import os
import socket
import threading
import logging
import platform
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from config import DEFAULT_PORT, LOG_FORMAT, LOG_LEVEL, get_master_config
from protocol import (
    send_message, receive_message, MouseMoveMessage, MouseClickMessage,
    MouseScrollMessage, KeyPressMessage, KeyReleaseMessage, HeartbeatMessage,
    MessageType, EnterScreenMessage
)
from input_controller import InputListener, get_screen_size, is_at_edge

# Configure logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Flask App Setup
app = Flask(__name__)
CORS(app)


class ServerConnection:
    """Represents a connection to a server"""
    
    def __init__(self, host: str, port: int, name: str = ""):
        self.host = host
        self.port = port
        self.name = name if name else f"{host}:{port}"
        self.socket = None
        self.connected = False
        self.screen_w = 1920
        self.screen_h = 1080
        self.receive_thread = None
    
    @property
    def id(self):
        return f"{self.host}:{self.port}"
    
    def connect(self) -> bool:
        """Connect to the server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))
            self.connected = True
            logger.info(f"Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to {self.host}:{self.port}: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from the server"""
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        logger.info(f"Disconnected from {self.host}:{self.port}")
    
    def send(self, message) -> bool:
        """Send message to server"""
        if not self.connected or not self.socket:
            return False
        return send_message(self.socket, message)
    
    def __str__(self):
        return f"{self.host}:{self.port}"


class MasterState:
    """Global state for the master application"""
    
    def __init__(self):
        self.config = get_master_config()
        self.servers = {}  # id -> ServerConnection
        self.logs = []
        self.log_lock = threading.Lock()
        
        # Screen switching engine state
        self.screen_w, self.screen_h = get_screen_size()
        self.active_screen = 'master'  # 'master' or server_id
        self.control_enabled = False
        self.listener = None
        self.last_mouse_x = 0
        self.last_mouse_y = 0
    
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        with self.log_lock:
            self.logs.append(entry)
            if len(self.logs) > 1000:
                self.logs.pop(0)
    
    def get_layout(self):
        """Get screen layout from config"""
        layout = self.config.get('screen_layout', {})
        if not layout:
            layout = {
                'master': {'x': 0, 'y': 0, 'w': self.screen_w, 'h': self.screen_h},
                'servers': {}
            }
        # Always update master screen size
        layout['master'] = {'x': layout.get('master', {}).get('x', 0),
                           'y': layout.get('master', {}).get('y', 0),
                           'w': self.screen_w, 'h': self.screen_h}
        return layout
    
    def find_server_at_edge(self, edge, cursor_x, cursor_y):
        """
        Find which server screen is adjacent to the master at the given edge.
        Returns (server_id, entry_x, entry_y) or None.
        """
        layout = self.get_layout()
        master = layout['master']
        servers_layout = layout.get('servers', {})
        
        for sid, s_layout in servers_layout.items():
            if sid not in self.servers or not self.servers[sid].connected:
                continue
            
            server = self.servers[sid]
            
            if edge == 'right':
                # Server should be to the right of master
                if s_layout['x'] >= master['x'] + master['w'] - 50:
                    # Map cursor Y to server Y
                    rel_y = (cursor_y - master['y']) / master['h']
                    entry_y = int(rel_y * server.screen_h)
                    entry_y = max(0, min(server.screen_h - 1, entry_y))
                    return (sid, 0, entry_y)
            
            elif edge == 'left':
                if s_layout['x'] + s_layout['w'] <= master['x'] + 50:
                    rel_y = (cursor_y - master['y']) / master['h']
                    entry_y = int(rel_y * server.screen_h)
                    entry_y = max(0, min(server.screen_h - 1, entry_y))
                    return (sid, server.screen_w - 1, entry_y)
            
            elif edge == 'top':
                if s_layout['y'] + s_layout['h'] <= master['y'] + 50:
                    rel_x = (cursor_x - master['x']) / master['w']
                    entry_x = int(rel_x * server.screen_w)
                    entry_x = max(0, min(server.screen_w - 1, entry_x))
                    return (sid, entry_x, server.screen_h - 1)
            
            elif edge == 'bottom':
                if s_layout['y'] >= master['y'] + master['h'] - 50:
                    rel_x = (cursor_x - master['x']) / master['w']
                    entry_x = int(rel_x * server.screen_w)
                    entry_x = max(0, min(server.screen_w - 1, entry_x))
                    return (sid, entry_x, 0)
        
        return None


state = MasterState()


def start_receive_thread(server: ServerConnection):
    """Start a thread to receive messages from a server (e.g. LEAVE_SCREEN)"""
    def receive_loop():
        try:
            while server.connected:
                msg = receive_message(server.socket)
                if not msg:
                    break
                
                if msg.type == MessageType.SCREEN_INFO:
                    server.screen_w = msg.data.get('width', 1920)
                    server.screen_h = msg.data.get('height', 1080)
                    state.log(f"Server {server.id} screen: {server.screen_w}x{server.screen_h}")
                
                elif msg.type == MessageType.LEAVE_SCREEN:
                    # Server cursor hit an edge, return control to master
                    edge = msg.data.get('edge', '')
                    state.log(f"Server {server.id} cursor left at edge: {edge}")
                    state.active_screen = 'master'
        except Exception as e:
            if server.connected:
                logger.error(f"Error receiving from {server.id}: {e}")
        finally:
            if server.connected:
                server.disconnect()
                state.log(f"Lost connection to {server.id}")
                if state.active_screen == server.id:
                    state.active_screen = 'master'
    
    server.receive_thread = threading.Thread(target=receive_loop, daemon=True)
    server.receive_thread.start()


def on_mouse_move(x, y):
    """Handle mouse move from InputListener"""
    if not state.control_enabled:
        return
    
    state.last_mouse_x = x
    state.last_mouse_y = y
    
    if state.active_screen == 'master':
        # Check if cursor is at an edge
        edge = is_at_edge(x, y, state.screen_w, state.screen_h)
        if edge:
            result = state.find_server_at_edge(edge, x, y)
            if result:
                sid, entry_x, entry_y = result
                server = state.servers[sid]
                # Send ENTER_SCREEN to server
                enter_msg = EnterScreenMessage(entry_x, entry_y, edge)
                if server.send(enter_msg):
                    state.active_screen = sid
                    state.log(f"Switched to server {sid} at ({entry_x}, {entry_y})")
    else:
        # Forward mouse to active server
        server = state.servers.get(state.active_screen)
        if server and server.connected:
            server.send(MouseMoveMessage(x, y))


def on_mouse_click(button, pressed):
    """Handle mouse click from InputListener"""
    if not state.control_enabled:
        return
    if state.active_screen != 'master':
        server = state.servers.get(state.active_screen)
        if server and server.connected:
            server.send(MouseClickMessage(button, pressed))


def on_mouse_scroll(dx, dy):
    """Handle mouse scroll from InputListener"""
    if not state.control_enabled:
        return
    if state.active_screen != 'master':
        server = state.servers.get(state.active_screen)
        if server and server.connected:
            server.send(MouseScrollMessage(dx, dy))


def on_key_press(key):
    """Handle key press from InputListener"""
    if not state.control_enabled:
        return
    if state.active_screen != 'master':
        server = state.servers.get(state.active_screen)
        if server and server.connected:
            server.send(KeyPressMessage(key))


def on_key_release(key):
    """Handle key release from InputListener"""
    if not state.control_enabled:
        return
    if state.active_screen != 'master':
        server = state.servers.get(state.active_screen)
        if server and server.connected:
            server.send(KeyReleaseMessage(key))


# ==================== Flask Routes ====================

@app.route('/')
def index():
    return render_template('master.html')


@app.route('/api/status')
def get_status():
    servers_info = []
    for sid, server in state.servers.items():
        servers_info.append({
            'id': sid,
            'host': server.host,
            'port': server.port,
            'connected': server.connected,
            'screen_w': server.screen_w,
            'screen_h': server.screen_h,
            'is_active': state.active_screen == sid
        })
    
    return jsonify({
        'control_enabled': state.control_enabled,
        'active_screen': state.active_screen,
        'master_screen': {'w': state.screen_w, 'h': state.screen_h},
        'servers': servers_info
    })


@app.route('/api/logs')
def get_logs():
    cursor = request.args.get('cursor', 0, type=int)
    with state.log_lock:
        if cursor < 0: cursor = 0
        if cursor >= len(state.logs):
            return jsonify({'logs': [], 'cursor': len(state.logs)})
        new_logs = state.logs[cursor:]
        return jsonify({'logs': new_logs, 'cursor': len(state.logs)})


@app.route('/api/connect', methods=['POST'])
def connect_server():
    data = request.json
    host = data.get('host', '').strip()
    port = int(data.get('port', DEFAULT_PORT))
    
    if not host:
        return jsonify({'status': 'error', 'message': 'Host is required'})
    
    sid = f"{host}:{port}"
    if sid in state.servers and state.servers[sid].connected:
        return jsonify({'status': 'error', 'message': 'Already connected'})
    
    server = ServerConnection(host, port)
    state.log(f"Connecting to {host}:{port}...")
    
    if server.connect():
        state.servers[sid] = server
        start_receive_thread(server)
        
        # Add default layout position (right of master)
        layout = state.get_layout()
        if sid not in layout.get('servers', {}):
            layout.setdefault('servers', {})[sid] = {
                'x': layout['master']['x'] + layout['master']['w'],
                'y': layout['master']['y'],
                'w': server.screen_w,
                'h': server.screen_h
            }
            state.config.set('screen_layout', layout)
            state.config.save()
        
        state.log(f"Connected to {host}:{port}")
        return jsonify({'status': 'success'})
    else:
        state.log(f"Failed to connect to {host}:{port}")
        return jsonify({'status': 'error', 'message': f'Failed to connect to {host}:{port}'})


@app.route('/api/disconnect', methods=['POST'])
def disconnect_server():
    data = request.json
    sid = data.get('id', '')
    
    if sid in state.servers:
        if state.active_screen == sid:
            state.active_screen = 'master'
        state.servers[sid].disconnect()
        del state.servers[sid]
        state.log(f"Disconnected from {sid}")
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error', 'message': 'Server not found'})


@app.route('/api/control/enable', methods=['POST'])
def enable_control():
    if state.control_enabled:
        return jsonify({'status': 'error', 'message': 'Already enabled'})
    
    state.control_enabled = True
    state.active_screen = 'master'
    state.listener = InputListener(
        on_mouse_move=on_mouse_move,
        on_mouse_click=on_mouse_click,
        on_mouse_scroll=on_mouse_scroll,
        on_key_press=on_key_press,
        on_key_release=on_key_release
    )
    state.listener.start()
    state.log("Control enabled — move mouse to screen edge to switch")
    return jsonify({'status': 'success'})


@app.route('/api/control/disable', methods=['POST'])
def disable_control():
    if not state.control_enabled:
        return jsonify({'status': 'error', 'message': 'Already disabled'})
    
    state.control_enabled = False
    state.active_screen = 'master'
    if state.listener:
        state.listener.stop()
        state.listener = None
    state.log("Control disabled")
    return jsonify({'status': 'success'})


@app.route('/api/layout', methods=['GET'])
def get_layout():
    layout = state.get_layout()
    # Add actual server screen sizes
    for sid, server in state.servers.items():
        if sid in layout.get('servers', {}):
            layout['servers'][sid]['w'] = server.screen_w
            layout['servers'][sid]['h'] = server.screen_h
    return jsonify(layout)


@app.route('/api/layout', methods=['POST'])
def save_layout():
    data = request.json
    try:
        state.config.set('screen_layout', data)
        state.config.save()
        state.log("Screen layout saved")
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


def main():
    """Main entry point"""
    state.log(f"Master screen: {state.screen_w}x{state.screen_h}")
    print(f"Starting Master Web Interface on http://0.0.0.0:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)


if __name__ == '__main__':
    main()
