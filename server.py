#!/usr/bin/env python3
"""
SynergyPlus Server Application
Listens for connections from master and executes mouse/keyboard commands
Web Interface Version — Extended Display Mode
"""

import os
import socket
import threading
import logging
import sys
import platform
import json
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import ipaddress

from config import DEFAULT_PORT, DEFAULT_HOST, LOG_FORMAT, LOG_LEVEL, get_server_config
from protocol import (
    receive_message, send_message, MessageType, AckMessage,
    ScreenInfoMessage, LeaveScreenMessage
)
from input_controller import InputController, get_screen_size, is_at_edge

# Configure logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Flask App Setup
app = Flask(__name__)
CORS(app)

# Global State
class ServerState:
    def __init__(self):
        self.server = None
        self.logs = []
        self.log_lock = threading.Lock()
        self.config = get_server_config()
        self.client_address = None
        self.screen_w, self.screen_h = get_screen_size()

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        with self.log_lock:
            self.logs.append(entry)
            if len(self.logs) > 1000:
                self.logs.pop(0)

state = ServerState()


class Server:
    """Server for receiving and executing commands — Extended Display Mode"""
    
    def __init__(self, port: int, config):
        self.port = port
        self.config = config
        self.controller = InputController()
        
        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.active = False  # True when this screen is being controlled
        self.accept_thread = None
        self.handle_thread = None
        self.edge_thread = None
        self.last_mouse_pos = None
    
    def start(self):
        """Start the server"""
        self.running = True
        self.accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        self.accept_thread.start()
    
    def stop(self):
        """Stop the server"""
        self.running = False
        self.active = False
        
        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
            except:
                pass
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        state.client_address = None
    
    def _accept_connections(self):
        """Accept incoming connections"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((DEFAULT_HOST, self.port))
            self.server_socket.listen(1)
            
            state.log(f"Server listening on port {self.port}")
            logger.info(f"Server listening on port {self.port}")
            
            while self.running:
                try:
                    self.server_socket.settimeout(1.0)
                    client_socket, client_address = self.server_socket.accept()
                    
                    # Check IP whitelist
                    if not self._is_allowed_ip(client_address[0]):
                        logger.warning(f"Connection rejected from {client_address[0]} (not in whitelist)")
                        state.log(f"Rejected connection from {client_address[0]} (not in whitelist)")
                        client_socket.close()
                        continue
                    
                    logger.info(f"Client connected from {client_address}")
                    state.log(f"Client connected: {client_address[0]}:{client_address[1]}")
                    state.client_address = f"{client_address[0]}:{client_address[1]}"
                    
                    # Close previous client if exists
                    if self.client_socket:
                        try:
                            self.client_socket.close()
                        except:
                            pass
                    
                    self.client_socket = client_socket
                    
                    # Send screen info to master
                    screen_msg = ScreenInfoMessage(state.screen_w, state.screen_h)
                    send_message(client_socket, screen_msg)
                    state.log(f"Sent screen info: {state.screen_w}x{state.screen_h}")
                    
                    # Handle client in a new thread
                    self.handle_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address),
                        daemon=True
                    )
                    self.handle_thread.start()
                    
                except socket.timeout:
                    continue
                except OSError:
                    break
                except Exception as e:
                    if self.running:
                        logger.error(f"Error accepting connection: {e}")
                    break
        except Exception as e:
            logger.error(f"Error starting server socket: {e}")
            state.log(f"Error: {e}")
        finally:
            state.log("Server socket closed")

    def _handle_client(self, client_socket, client_address):
        """Handle client connection"""
        try:
            while self.running:
                message = receive_message(client_socket)
                
                if not message:
                    logger.info("Client disconnected")
                    break
                
                self._process_message(message)
                
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
            
            self.active = False
            if self.client_socket == client_socket:
                self.client_socket = None
                state.client_address = None
                state.log(f"Client disconnected: {client_address[0]}:{client_address[1]}")
    
    def _start_edge_monitor(self, entry_edge: str):
        """Monitor cursor position for edge detection while active.
        
        Args:
            entry_edge: the edge the cursor entered from — ignored until cursor moves away
        """
        def monitor():
            # Map entry edge to the OPPOSITE edge (that's where cursor appears)
            # e.g. if master sent cursor to the right, cursor enters server from 'left'
            opposite = {'left': 'left', 'right': 'right', 'top': 'top', 'bottom': 'bottom'}
            suppress_edge = entry_edge  # Don't trigger on this edge initially
            cleared = False  # Has cursor moved away from entry edge?
            
            while self.active and self.running:
                try:
                    x, y = self.controller.get_mouse_position()
                    edge = is_at_edge(x, y, state.screen_w, state.screen_h)
                    
                    # Track when cursor moves away from the entry edge
                    if not cleared:
                        if edge != suppress_edge:
                            cleared = True
                        else:
                            # Still at entry edge, skip
                            time.sleep(0.01)
                            continue
                    
                    if edge and self.client_socket:
                        leave_msg = LeaveScreenMessage(edge, int(x), int(y))
                        send_message(self.client_socket, leave_msg)
                        self.active = False
                        state.log(f"Cursor left at edge: {edge}")
                        break
                except Exception as e:
                    logger.error(f"Edge monitor error: {e}")
                    break
                
                time.sleep(0.01)  # 100Hz polling
        
        self.edge_thread = threading.Thread(target=monitor, daemon=True)
        self.edge_thread.start()
    
    def _process_message(self, message):
        """Process received message"""
        try:
            msg_type = message.type
            data = message.data
            
            if msg_type == MessageType.ENTER_SCREEN:
                # Master is sending control to us
                entry_edge = data.get('edge', 'left')
                entry_x = data.get('x', state.screen_w // 2)
                entry_y = data.get('y', state.screen_h // 2)
                
                # Offset cursor 20px inside the screen so edge monitor doesn't trigger immediately
                margin = 20
                if entry_x <= margin:
                    entry_x = margin
                elif entry_x >= state.screen_w - margin:
                    entry_x = state.screen_w - margin
                if entry_y <= margin:
                    entry_y = margin
                elif entry_y >= state.screen_h - margin:
                    entry_y = state.screen_h - margin
                
                self.controller.move_mouse(entry_x, entry_y)
                self.active = True
                state.log(f"Screen entered at ({entry_x}, {entry_y}) from edge: {entry_edge}")
                self._start_edge_monitor(entry_edge)
            
            elif msg_type == MessageType.MOUSE_MOVE:
                if self.active:
                    self.controller.move_mouse(data['x'], data['y'])
            
            elif msg_type == MessageType.MOUSE_CLICK:
                if self.active:
                    self.controller.click_mouse(data['button'], data['pressed'])
            
            elif msg_type == MessageType.MOUSE_SCROLL:
                if self.active:
                    self.controller.scroll_mouse(data['dx'], data['dy'])
            
            elif msg_type == MessageType.KEY_PRESS:
                if self.active:
                    self.controller.press_key(data['key'])
            
            elif msg_type == MessageType.KEY_RELEASE:
                if self.active:
                    self.controller.release_key(data['key'])
            
            elif msg_type == MessageType.HEARTBEAT:
                if self.client_socket:
                    send_message(self.client_socket, AckMessage())
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _is_allowed_ip(self, client_ip: str) -> bool:
        """Check if client IP is allowed based on whitelist"""
        if not self.config.get('security.enable_whitelist', False):
            return True
        
        whitelist = self.config.get('security.whitelist', [])
        if not whitelist:
            return True
        
        try:
            client_addr = ipaddress.ip_address(client_ip)
            
            for allowed in whitelist:
                try:
                    if '/' in allowed:
                        network = ipaddress.ip_network(allowed, strict=False)
                        if client_addr in network:
                            return True
                    else:
                        if client_addr == ipaddress.ip_address(allowed):
                            return True
                except ValueError:
                    logger.warning(f"Invalid whitelist entry: {allowed}")
                    continue
            
            return False
        except ValueError:
            logger.error(f"Invalid client IP: {client_ip}")
            return False


# Routes
@app.route('/')
def index():
    port = state.config.get('network.port', DEFAULT_PORT)
    return render_template('index.html', port=port, host=DEFAULT_HOST)

@app.route('/api/status')
def get_status():
    running = state.server is not None and state.server.running
    port = state.config.get('network.port', DEFAULT_PORT)
    active = state.server.active if state.server else False
    
    return jsonify({
        'running': running,
        'active': active,
        'client_connected': state.client_address is not None,
        'client_address': state.client_address,
        'port': port,
        'screen': {'w': state.screen_w, 'h': state.screen_h}
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

@app.route('/api/start', methods=['POST'])
def start_server():
    if state.server and state.server.running:
        return jsonify({'status': 'error', 'message': 'Server already running'})
    
    try:
        port = state.config.get('network.port', DEFAULT_PORT)
        state.server = Server(port, state.config)
        state.server.start()
        state.log(f"Server started on port {port}")
        return jsonify({'status': 'success'})
    except Exception as e:
        state.log(f"Error starting server: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/stop', methods=['POST'])
def stop_server():
    if not state.server or not state.server.running:
        return jsonify({'status': 'error', 'message': 'Server not running'})
    
    try:
        state.server.stop()
        state.server = None
        state.log("Server stopped")
        return jsonify({'status': 'success'})
    except Exception as e:
        state.log(f"Error stopping server: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json
    try:
        port = data.get('network.port')
        whitelist = data.get('security.whitelist')
        
        if port:
            state.config.set('network.port', int(port))
        if whitelist is not None:
            state.config.set('security.whitelist', whitelist)
            state.config.set('security.enable_whitelist', len(whitelist) > 0)
            
        state.config.save()
        state.log("Configuration saved")
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

def main():
    """Main entry point"""
    if state.config.get('behavior.auto_start', False):
        try:
            port = state.config.get('network.port', DEFAULT_PORT)
            state.server = Server(port, state.config)
            state.server.start()
            state.log(f"Auto-started server on port {port}")
        except Exception as e:
            state.log(f"Error auto-starting server: {e}")
            
    print("Starting Web Interface on http://0.0.0.0:5003")
    app.run(host='0.0.0.0', port=5003, debug=False)

if __name__ == '__main__':
    main()
