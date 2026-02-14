"""
Configuration dialogs for Master and Server applications
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional
import re


class MasterConfigDialog:
    """Configuration dialog for Master application"""
    
    def __init__(self, parent, config_manager, on_save: Optional[Callable] = None):
        self.parent = parent
        self.config = config_manager
        self.on_save = on_save
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Master Settings")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_widgets()
        self._load_values()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets"""
        # Create notebook (tabs)
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Network tab
        network_frame = ttk.Frame(notebook, padding=10)
        notebook.add(network_frame, text="Network")
        
        ttk.Label(network_frame, text="Default Port:").grid(row=0, column=0, sticky="w", pady=5)
        self.port_var = tk.StringVar()
        ttk.Entry(network_frame, textvariable=self.port_var, width=15).grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(network_frame, text="Connection Timeout (seconds):").grid(row=1, column=0, sticky="w", pady=5)
        self.timeout_var = tk.StringVar()
        ttk.Entry(network_frame, textvariable=self.timeout_var, width=15).grid(row=1, column=1, sticky="w", padx=5)
        
        # Behavior tab
        behavior_frame = ttk.Frame(notebook, padding=10)
        notebook.add(behavior_frame, text="Behavior")
        
        self.auto_connect_var = tk.BooleanVar()
        ttk.Checkbutton(
            behavior_frame,
            text="Auto-connect to last server on startup",
            variable=self.auto_connect_var
        ).grid(row=0, column=0, sticky="w", pady=5)
        
        ttk.Label(behavior_frame, text="Control Hotkey:").grid(row=1, column=0, sticky="w", pady=5)
        self.hotkey_var = tk.StringVar()
        ttk.Entry(behavior_frame, textvariable=self.hotkey_var, width=20).grid(row=1, column=1, sticky="w", padx=5)
        ttk.Label(
            behavior_frame,
            text="(e.g., ctrl+shift+s)",
            font=("Arial", 9, "italic"),
            foreground="gray"
        ).grid(row=2, column=1, sticky="w", padx=5)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self._save).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right", padx=5)
    
    def _load_values(self):
        """Load values from configuration"""
        self.port_var.set(str(self.config.get('network.default_port', 9999)))
        self.timeout_var.set(str(self.config.get('network.connection_timeout', 30)))
        self.auto_connect_var.set(self.config.get('behavior.auto_connect', False))
        self.hotkey_var.set(self.config.get('behavior.control_hotkey', 'ctrl+shift+s'))
    
    def _save(self):
        """Save configuration"""
        try:
            # Validate port
            port = int(self.port_var.get())
            if not (1 <= port <= 65535):
                raise ValueError("Port must be between 1 and 65535")
            
            # Validate timeout
            timeout = int(self.timeout_var.get())
            if timeout < 1:
                raise ValueError("Timeout must be at least 1 second")
            
            # Save values
            self.config.set('network.default_port', port)
            self.config.set('network.connection_timeout', timeout)
            self.config.set('behavior.auto_connect', self.auto_connect_var.get())
            self.config.set('behavior.control_hotkey', self.hotkey_var.get())
            
            self.config.save()
            
            if self.on_save:
                self.on_save()
            
            messagebox.showinfo("Success", "Settings saved successfully!", parent=self.dialog)
            self.dialog.destroy()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e), parent=self.dialog)


class ServerConfigDialog:
    """Configuration dialog for Server application"""
    
    def __init__(self, parent, config_manager, on_save: Optional[Callable] = None):
        self.parent = parent
        self.config = config_manager
        self.on_save = on_save
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Server Settings")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_widgets()
        self._load_values()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets"""
        # Create notebook (tabs)
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Network tab
        network_frame = ttk.Frame(notebook, padding=10)
        notebook.add(network_frame, text="Network")
        
        ttk.Label(network_frame, text="Listen Port:").grid(row=0, column=0, sticky="w", pady=5)
        self.port_var = tk.StringVar()
        ttk.Entry(network_frame, textvariable=self.port_var, width=15).grid(row=0, column=1, sticky="w", padx=5)
        
        # Behavior tab
        behavior_frame = ttk.Frame(notebook, padding=10)
        notebook.add(behavior_frame, text="Behavior")
        
        self.auto_start_var = tk.BooleanVar()
        ttk.Checkbutton(
            behavior_frame,
            text="Auto-start server on application launch",
            variable=self.auto_start_var
        ).grid(row=0, column=0, sticky="w", pady=5)
        
        # Security tab
        security_frame = ttk.Frame(notebook, padding=10)
        notebook.add(security_frame, text="Security")
        
        self.whitelist_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(
            security_frame,
            text="Enable IP Whitelist",
            variable=self.whitelist_enabled_var,
            command=self._toggle_whitelist
        ).grid(row=0, column=0, sticky="w", pady=5)
        
        ttk.Label(security_frame, text="Allowed IPs (one per line):").grid(row=1, column=0, sticky="w", pady=5)
        
        whitelist_frame = ttk.Frame(security_frame)
        whitelist_frame.grid(row=2, column=0, sticky="ew", pady=5)
        
        self.whitelist_text = tk.Text(whitelist_frame, height=8, width=40)
        self.whitelist_text.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(whitelist_frame, command=self.whitelist_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.whitelist_text.config(yscrollcommand=scrollbar.set)
        
        ttk.Label(
            security_frame,
            text="Examples: 192.168.1.100, 192.168.1.0/24",
            font=("Arial", 9, "italic"),
            foreground="gray"
        ).grid(row=3, column=0, sticky="w")
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self._save).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right", padx=5)
    
    def _load_values(self):
        """Load values from configuration"""
        self.port_var.set(str(self.config.get('network.port', 9999)))
        self.auto_start_var.set(self.config.get('behavior.auto_start', False))
        self.whitelist_enabled_var.set(self.config.get('security.enable_whitelist', False))
        
        whitelist = self.config.get('security.whitelist', [])
        self.whitelist_text.delete('1.0', tk.END)
        self.whitelist_text.insert('1.0', '\n'.join(whitelist))
        
        self._toggle_whitelist()
    
    def _toggle_whitelist(self):
        """Enable/disable whitelist text based on checkbox"""
        if self.whitelist_enabled_var.get():
            self.whitelist_text.config(state='normal')
        else:
            self.whitelist_text.config(state='disabled')
    
    def _save(self):
        """Save configuration"""
        try:
            # Validate port
            port = int(self.port_var.get())
            if not (1 <= port <= 65535):
                raise ValueError("Port must be between 1 and 65535")
            
            # Parse whitelist
            whitelist = []
            if self.whitelist_enabled_var.get():
                whitelist_text = self.whitelist_text.get('1.0', tk.END).strip()
                if whitelist_text:
                    whitelist = [line.strip() for line in whitelist_text.split('\n') if line.strip()]
            
            # Save values
            old_port = self.config.get('network.port')
            self.config.set('network.port', port)
            self.config.set('behavior.auto_start', self.auto_start_var.get())
            self.config.set('security.enable_whitelist', self.whitelist_enabled_var.get())
            self.config.set('security.whitelist', whitelist)
            
            self.config.save()
            
            # Warn if port changed
            port_changed = old_port != port
            
            if self.on_save:
                self.on_save(port_changed)
            
            msg = "Settings saved successfully!"
            if port_changed:
                msg += "\n\nPort changed. Please restart the server for changes to take effect."
            
            messagebox.showinfo("Success", msg, parent=self.dialog)
            self.dialog.destroy()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e), parent=self.dialog)
