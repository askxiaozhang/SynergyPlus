#!/usr/bin/env python3
"""
SynergyPlus Server Application
Listens for connections from master and executes mouse/keyboard commands
Web Interface Version
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
from protocol import receive_message, send_message, MessageType, AckMessage
from input_controller import InputController

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

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        with self.log_lock:
            self.logs.append(entry)
            # Keep logs valid size
            if len(self.logs) > 1000:
                self.logs.pop(0)

state = ServerState()

class Server:
    """Server for receiving and executing commands"""
    
    def __init__(self, port: int, config):
        self.port = port
        self.config = config
        self.controller = InputController()
        
        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.accept_thread = None
        self.handle_thread = None
    
    def start(self):
        """Start the server"""
        self.running = True
        self.accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        self.accept_thread.start()
    
    def stop(self):
        """Stop the server"""
        self.running = False
        
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
                    # Socket closed
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
            
            if self.client_socket == client_socket:
                self.client_socket = None
                state.client_address = None
                state.log(f"Client disconnected: {client_address[0]}:{client_address[1]}")
    
    def _process_message(self, message):
        """Process received message"""
        try:
            msg_type = message.type
            data = message.data
            
            if msg_type == MessageType.MOUSE_MOVE:
                self.controller.move_mouse(data['x'], data['y'])
            
            elif msg_type == MessageType.MOUSE_CLICK:
                self.controller.click_mouse(data['button'], data['pressed'])
            
            elif msg_type == MessageType.MOUSE_SCROLL:
                self.controller.scroll_mouse(data['dx'], data['dy'])
            
            elif msg_type == MessageType.KEY_PRESS:
                self.controller.press_key(data['key'])
            
            elif msg_type == MessageType.KEY_RELEASE:
                self.controller.release_key(data['key'])
            
            elif msg_type == MessageType.HEARTBEAT:
                # Respond to heartbeat
                if self.client_socket:
                    send_message(self.client_socket, AckMessage())
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _is_allowed_ip(self, client_ip: str) -> bool:
        """Check if client IP is allowed based on whitelist"""
        # If whitelist is disabled, allow all
        if not self.config.get('security.enable_whitelist', False):
            return True
        
        whitelist = self.config.get('security.whitelist', [])
        if not whitelist:
            return True
        
        try:
            client_addr = ipaddress.ip_address(client_ip)
            
            for allowed in whitelist:
                try:
                    # Check if it's a network (CIDR notation)
                    if '/' in allowed:
                        network = ipaddress.ip_network(allowed, strict=False)
                        if client_addr in network:
                            return True
                    # Check if it's a single IP
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
    
    return jsonify({
        'running': running,
        'client_connected': state.client_address is not None,
        'client_address': state.client_address,
        'port': port
    })

@app.route('/api/logs')
def get_logs():
    cursor = request.args.get('cursor', 0, type=int)
    with state.log_lock:
        if cursor < 0: cursor = 0
        if cursor >= len(state.logs):
            return jsonify({'logs': [], 'cursor': len(state.logs)})
            
        new_logs = state.logs[cursor:]
        return jsonify({
            'logs': new_logs,
            'cursor': len(state.logs)
        })

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
    # Auto-start logic
    if state.config.get('behavior.auto_start', False):
        try:
            port = state.config.get('network.port', DEFAULT_PORT)
            state.server = Server(port, state.config)
            state.server.start()
            state.log(f"Auto-started server on port {port}")
        except Exception as e:
            state.log(f"Error auto-starting server: {e}")
            
    print("Starting Web Interface on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5003, debug=False)

if __name__ == '__main__':
    main()
