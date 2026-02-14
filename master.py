#!/usr/bin/env python3
"""
SynergyPlus Master Application
Controls remote servers by capturing and forwarding mouse/keyboard input
"""

import os
import socket
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import logging
import platform
from datetime import datetime

from config import DEFAULT_PORT, LOG_FORMAT, LOG_LEVEL, get_master_config
from protocol import (
    send_message, receive_message, MouseMoveMessage, MouseClickMessage,
    MouseScrollMessage, KeyPressMessage, KeyReleaseMessage, HeartbeatMessage
)
from input_controller import InputListener
from config_dialog import MasterConfigDialog

# Configure logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class ServerConnection:
    """Represents a connection to a server"""
    
    def __init__(self, host: str, port: int, name: str = ""):
        self.host = host
        self.port = port
        self.name = name if name else f"{host}:{port}"
        self.socket = None
        self.connected = False
    
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
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        logger.info(f"Disconnected from {self.host}:{self.port}")
    
    def send(self, message) -> bool:
        """Send message to server"""
        if not self.connected or not self.socket:
            return False
        return send_message(self.socket, message)
    
    def __str__(self):
        return f"{self.host}:{self.port}"


class MasterGUI:
    """GUI for master application"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SynergyPlus Master")
        self.root.geometry("600x550")
        
        # Fix macOS rendering: use 'clam' theme instead of broken 'aqua'
        style = ttk.Style()
        style.theme_use('clam')
        
        # Load configuration
        self.config = get_master_config()
        
        # Server list
        self.servers = []
        self.active_server = None
        
        # Control state
        self.control_enabled = False
        self.listener = None
        
        self._create_widgets()
        self._load_saved_servers()
        
        # Force update to ensure widgets are rendered
        self.root.update_idletasks()
        
        # Schedule window to come to front after mainloop starts
        self.root.after(100, self._bring_to_front)
    
    def _create_widgets(self):
        """Create GUI widgets"""
        # Title
        title_label = tk.Label(
            self.root,
            text="SynergyPlus Master",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=10)
        
        # Connection frame
        conn_frame = ttk.LabelFrame(self.root, text="Add Server", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(conn_frame, text="Host:").grid(row=0, column=0, sticky="w")
        self.host_entry = ttk.Entry(conn_frame, width=20)
        self.host_entry.insert(0, "127.0.0.1")
        self.host_entry.grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, sticky="w")
        self.port_entry = ttk.Entry(conn_frame, width=10)
        default_port = self.config.get('network.default_port', DEFAULT_PORT)
        self.port_entry.insert(0, str(default_port))
        self.port_entry.grid(row=0, column=3, sticky="w", padx=5)
        
        ttk.Button(
            conn_frame,
            text="Connect",
            command=self.add_server
        ).grid(row=0, column=4, padx=5)
        
        # Server list frame
        server_frame = ttk.LabelFrame(self.root, text="Connected Servers", padding=10)
        server_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Treeview for servers
        self.server_tree = ttk.Treeview(
            server_frame,
            columns=("Host", "Port", "Status"),
            show="headings",
            height=6,
            selectmode="browse"
        )
        self.server_tree.heading("Host", text="Host")
        self.server_tree.heading("Port", text="Port")
        self.server_tree.heading("Status", text="Status")
        
        self.server_tree.column("Host", width=200)
        self.server_tree.column("Port", width=100)
        self.server_tree.column("Status", width=150)
        
        self.server_tree.pack(fill="both", expand=True)
        
        # Server control buttons
        server_btn_frame = ttk.Frame(server_frame)
        server_btn_frame.pack(fill="x", pady=5)
        
        ttk.Button(
            server_btn_frame,
            text="Set Active",
            command=self.set_active_server
        ).pack(side="left", padx=5)
        
        ttk.Button(
            server_btn_frame,
            text="Disconnect",
            command=self.disconnect_server
        ).pack(side="left", padx=5)
        
        ttk.Button(
            server_btn_frame,
            text="Settings",
            command=self.open_settings
        ).pack(side="right", padx=5)
        
        # Control frame
        control_frame = ttk.LabelFrame(self.root, text="Control", padding=10)
        control_frame.pack(fill="x", padx=10, pady=5)
        
        self.control_status_var = tk.StringVar(value="Disabled - No Active Server")
        ttk.Label(control_frame, textvariable=self.control_status_var).pack(side="left")
        
        self.toggle_button = ttk.Button(
            control_frame,
            text="Enable Control",
            command=self.toggle_control,
            state="disabled"
        )
        self.toggle_button.pack(side="right", padx=5)
        
        # Log frame
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, state='disabled')
        self.log_text.pack(fill="both", expand=True)
        
        # Bottom buttons
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(
            bottom_frame,
            text="Exit",
            command=self.exit_app
        ).pack(side="right")
    
    def log(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
    
    def add_server(self):
        """Add a new server connection"""
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()
        
        if not host or not port_str:
            messagebox.showerror("Error", "Please enter host and port")
            return
        
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Error", "Invalid port number")
            return
        
        # Check if already connected
        for server in self.servers:
            if server.host == host and server.port == port:
                messagebox.showwarning("Warning", "Already connected to this server")
                return
        
        # Create connection
        self.log(f"Connecting to {host}:{port}...")
        server = ServerConnection(host, port)
        
        if server.connect():
            self.servers.append(server)
            self._update_server_list()
            self.log(f"Connected to {host}:{port}")
            messagebox.showinfo("Success", f"Connected to {host}:{port}")
        else:
            self.log(f"Failed to connect to {host}:{port}")
            messagebox.showerror("Error", f"Failed to connect to {host}:{port}")
    
    def disconnect_server(self):
        """Disconnect selected server"""
        selection = self.server_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a server")
            return
        
        item = selection[0]
        index = int(item[1:], 16) - 1
        
        if 0 <= index < len(self.servers):
            server = self.servers[index]
            
            # Disable control if this is the active server
            if self.active_server == server:
                if self.control_enabled:
                    self.toggle_control()
                self.active_server = None
                self.toggle_button.config(state="disabled")
                self.control_status_var.set("Disabled - No Active Server")
            
            server.disconnect()
            self.servers.remove(server)
            self._update_server_list()
            self.log(f"Disconnected from {server}")
    
    def set_active_server(self):
        """Set selected server as active"""
        selection = self.server_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a server")
            return
        
        item = selection[0]
        index = int(item[1:], 16) - 1
        
        if 0 <= index < len(self.servers):
            # Disable control first if enabled
            if self.control_enabled:
                self.toggle_control()
            
            self.active_server = self.servers[index]
            self.toggle_button.config(state="normal")
            self.control_status_var.set(f"Disabled - Active: {self.active_server}")
            self._update_server_list()
            self.log(f"Active server set to {self.active_server}")
    
    def toggle_control(self):
        """Toggle control on/off"""
        if not self.active_server:
            messagebox.showwarning("Warning", "No active server")
            return
        
        if self.control_enabled:
            # Disable control
            self.control_enabled = False
            if self.listener:
                self.listener.stop()
                self.listener = None
            
            self.toggle_button.config(text="Enable Control")
            self.control_status_var.set(f"Disabled - Active: {self.active_server}")
            self.log("Control disabled")
        else:
            # Enable control
            self.control_enabled = True
            self.listener = InputListener(
                on_mouse_move=self._on_mouse_move,
                on_mouse_click=self._on_mouse_click,
                on_mouse_scroll=self._on_mouse_scroll,
                on_key_press=self._on_key_press,
                on_key_release=self._on_key_release
            )
            self.listener.start()
            
            self.toggle_button.config(text="Disable Control")
            self.control_status_var.set(f"ENABLED - Controlling: {self.active_server}")
            self.log(f"Control enabled for {self.active_server}")
    
    def _update_server_list(self):
        """Update the server list display"""
        # Clear tree
        for item in self.server_tree.get_children():
            self.server_tree.delete(item)
        
        # Add servers
        for server in self.servers:
            status = "Active" if server == self.active_server else "Connected"
            if not server.connected:
                status = "Disconnected"
            
            self.server_tree.insert(
                "",
                "end",
                values=(server.host, server.port, status)
            )
    
    def _on_mouse_move(self, x, y):
        """Handle mouse move event"""
        if self.control_enabled and self.active_server:
            msg = MouseMoveMessage(x, y)
            self.active_server.send(msg)
    
    def _on_mouse_click(self, button, pressed):
        """Handle mouse click event"""
        if self.control_enabled and self.active_server:
            msg = MouseClickMessage(button, pressed)
            self.active_server.send(msg)
    
    def _on_mouse_scroll(self, dx, dy):
        """Handle mouse scroll event"""
        if self.control_enabled and self.active_server:
            msg = MouseScrollMessage(dx, dy)
            self.active_server.send(msg)
    
    def _on_key_press(self, key):
        """Handle key press event"""
        if self.control_enabled and self.active_server:
            msg = KeyPressMessage(key)
            self.active_server.send(msg)
    
    def _on_key_release(self, key):
        """Handle key release event"""
        if self.control_enabled and self.active_server:
            msg = KeyReleaseMessage(key)
            self.active_server.send(msg)
    
    def open_settings(self):
        """Open settings dialog"""
        MasterConfigDialog(self.root, self.config, on_save=self._on_config_saved)
    
    def _on_config_saved(self):
        """Handle configuration saved"""
        # Update port entry with new default
        default_port = self.config.get('network.default_port', DEFAULT_PORT)
        current_port = self.port_entry.get()
        if current_port == str(DEFAULT_PORT):
            self.port_entry.delete(0, tk.END)
            self.port_entry.insert(0, str(default_port))
        self.log("Configuration saved")
    
    def _load_saved_servers(self):
        """Load saved servers from configuration"""
        saved_servers = self.config.get('servers', [])
        last_active = self.config.get('behavior.last_active_server', '')
        
        # Don't auto-connect, just add to list for manual connection
        for server_info in saved_servers:
            host = server_info.get('host')
            port = server_info.get('port')
            name = server_info.get('name', '')
            if host and port:
                # Just log that we have saved servers, don't auto-connect
                self.log(f"Saved server available: {name or f'{host}:{port}'}")
    
    def _save_servers_to_config(self):
        """Save current servers to configuration"""
        servers_list = []
        for server in self.servers:
            servers_list.append({
                'host': server.host,
                'port': server.port,
                'name': server.name
            })
        
        self.config.set('servers', servers_list)
        
        # Save last active server
        if self.active_server:
            self.config.set('behavior.last_active_server', str(self.active_server))
        
        self.config.save()
    
    def exit_app(self):
        """Exit the application"""
        if self.control_enabled:
            self.toggle_control()
        
        # Save configuration before exit
        self._save_servers_to_config()
        
        for server in self.servers:
            server.disconnect()
        
        self.root.quit()
    
    def _bring_to_front(self):
        """Bring window to front on macOS"""
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        
        if platform.system() == 'Darwin':
            try:
                import subprocess
                subprocess.Popen([
                    'osascript', '-e',
                    'tell application "System Events" to set frontmost of '
                    'the first process whose unix id is '
                    + str(os.getpid()) + ' to true'
                ])
            except Exception:
                pass
    
    def run(self):
        """Run the GUI main loop"""
        try:
            self.root.update()
        except:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.root.mainloop()


def main():
    """Main entry point"""
    gui = MasterGUI()
    gui.run()


if __name__ == '__main__':
    main()
