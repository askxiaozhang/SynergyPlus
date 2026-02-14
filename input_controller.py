"""
Input controller for mouse and keyboard control using pynput
"""

import platform
import subprocess
import threading
from pynput import mouse, keyboard
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController
import logging

logger = logging.getLogger(__name__)

EDGE_THRESHOLD = 2  # pixels from edge to trigger screen switch


class InputController:
    """Controller for mouse and keyboard input"""
    
    def __init__(self):
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
    
    def move_mouse(self, x: int, y: int):
        """
        Move mouse to absolute position
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        try:
            self.mouse.position = (x, y)
            logger.debug(f"Mouse moved to ({x}, {y})")
        except Exception as e:
            logger.error(f"Error moving mouse: {e}")
    
    def move_mouse_relative(self, dx: int, dy: int):
        """
        Move mouse by relative delta
        
        Args:
            dx: horizontal delta
            dy: vertical delta
        """
        try:
            current_x, current_y = self.mouse.position
            self.mouse.position = (current_x + dx, current_y + dy)
        except Exception as e:
            logger.error(f"Error moving mouse relative: {e}")
    
    def get_mouse_position(self):
        """Get current mouse position"""
        return self.mouse.position
    
    def click_mouse(self, button: str, pressed: bool):
        """
        Click mouse button
        
        Args:
            button: 'left', 'right', or 'middle'
            pressed: True to press, False to release
        """
        try:
            button_map = {
                'left': Button.left,
                'right': Button.right,
                'middle': Button.middle
            }
            
            btn = button_map.get(button, Button.left)
            
            if pressed:
                self.mouse.press(btn)
                logger.debug(f"Mouse button {button} pressed")
            else:
                self.mouse.release(btn)
                logger.debug(f"Mouse button {button} released")
        except Exception as e:
            logger.error(f"Error clicking mouse: {e}")
    
    def scroll_mouse(self, dx: int, dy: int):
        """
        Scroll mouse wheel
        
        Args:
            dx: horizontal scroll amount
            dy: vertical scroll amount
        """
        try:
            self.mouse.scroll(dx, dy)
            logger.debug(f"Mouse scrolled ({dx}, {dy})")
        except Exception as e:
            logger.error(f"Error scrolling mouse: {e}")
    
    def press_key(self, key_str: str):
        """
        Press a key
        
        Args:
            key_str: key string (e.g., 'a', 'shift', 'ctrl')
        """
        try:
            key = self._parse_key(key_str)
            self.keyboard.press(key)
            logger.debug(f"Key {key_str} pressed")
        except Exception as e:
            logger.error(f"Error pressing key: {e}")
    
    def release_key(self, key_str: str):
        """
        Release a key
        
        Args:
            key_str: key string (e.g., 'a', 'shift', 'ctrl')
        """
        try:
            key = self._parse_key(key_str)
            self.keyboard.release(key)
            logger.debug(f"Key {key_str} released")
        except Exception as e:
            logger.error(f"Error releasing key: {e}")
    
    def _parse_key(self, key_str: str):
        """
        Parse key string to pynput key object
        
        Args:
            key_str: key string
            
        Returns:
            pynput Key or KeyCode object
        """
        # Special keys mapping
        special_keys = {
            'shift': Key.shift,
            'ctrl': Key.ctrl,
            'alt': Key.alt,
            'cmd': Key.cmd,
            'enter': Key.enter,
            'space': Key.space,
            'tab': Key.tab,
            'esc': Key.esc,
            'backspace': Key.backspace,
            'delete': Key.delete,
            'up': Key.up,
            'down': Key.down,
            'left': Key.left,
            'right': Key.right,
            'home': Key.home,
            'end': Key.end,
            'page_up': Key.page_up,
            'page_down': Key.page_down,
            'f1': Key.f1,
            'f2': Key.f2,
            'f3': Key.f3,
            'f4': Key.f4,
            'f5': Key.f5,
            'f6': Key.f6,
            'f7': Key.f7,
            'f8': Key.f8,
            'f9': Key.f9,
            'f10': Key.f10,
            'f11': Key.f11,
            'f12': Key.f12,
        }
        
        key_lower = key_str.lower()
        if key_lower in special_keys:
            return special_keys[key_lower]
        else:
            # Regular character key
            return key_str if len(key_str) == 1 else key_str


def get_screen_size():
    """
    Get the primary screen resolution.
    
    Returns:
        (width, height) tuple
    """
    import re
    system = platform.system()
    
    if system == 'Darwin':  # macOS
        # Method 1: Quartz (most reliable)
        try:
            from Quartz import CGDisplayBounds, CGMainDisplayID
            main = CGMainDisplayID()
            bounds = CGDisplayBounds(main)
            w, h = int(bounds.size.width), int(bounds.size.height)
            if w > 0 and h > 0:
                logger.info(f"Screen size (Quartz): {w}x{h}")
                return (w, h)
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Quartz failed: {e}")
        
        # Method 2: AppKit
        try:
            from AppKit import NSScreen
            frame = NSScreen.mainScreen().frame()
            w, h = int(frame.size.width), int(frame.size.height)
            if w > 0 and h > 0:
                logger.info(f"Screen size (AppKit): {w}x{h}")
                return (w, h)
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"AppKit failed: {e}")
        
        # Method 3: system_profiler
        try:
            output = subprocess.check_output(
                ['system_profiler', 'SPDisplaysDataType'],
                text=True, timeout=5
            )
            # Handle various formats: "Resolution: 1920 x 1080" or "3024 x 1964"
            match = re.search(r'Resolution:\s*(\d+)\s*x\s*(\d+)', output)
            if match:
                w, h = int(match.group(1)), int(match.group(2))
                logger.info(f"Screen size (system_profiler): {w}x{h}")
                return (w, h)
        except Exception as e:
            logger.warning(f"system_profiler failed: {e}")
    
    elif system == 'Linux':
        try:
            output = subprocess.check_output(
                ['xrandr', '--current'],
                text=True, timeout=5
            )
            for line in output.split('\n'):
                if '*' in line:
                    parts = line.strip().split()
                    res = parts[0].split('x')
                    w, h = int(res[0]), int(res[1])
                    logger.info(f"Screen size (xrandr): {w}x{h}")
                    return (w, h)
        except Exception as e:
            logger.warning(f"xrandr failed: {e}")
    
    logger.warning("Could not detect screen size, using default 1920x1080")
    return (1920, 1080)


def is_at_edge(x, y, screen_w, screen_h, threshold=EDGE_THRESHOLD):
    """
    Check if cursor is at a screen edge.
    
    Args:
        x, y: cursor position
        screen_w, screen_h: screen dimensions
        threshold: pixel distance from edge
    
    Returns:
        'left', 'right', 'top', 'bottom', or None
    """
    if x <= threshold:
        return 'left'
    if x >= screen_w - threshold - 1:
        return 'right'
    if y <= threshold:
        return 'top'
    if y >= screen_h - threshold - 1:
        return 'bottom'
    return None


class InputListener:
    """Listener for mouse and keyboard input"""
    
    def __init__(self, on_mouse_move=None, on_mouse_click=None, 
                 on_mouse_scroll=None, on_key_press=None, on_key_release=None,
                 suppress=False):
        self.on_mouse_move = on_mouse_move
        self.on_mouse_click = on_mouse_click
        self.on_mouse_scroll = on_mouse_scroll
        self.on_key_press = on_key_press
        self.on_key_release = on_key_release
        self.suppress = suppress
        
        self.mouse_listener = None
        self.keyboard_listener = None
        self._lock = threading.Lock()
    
    def start(self):
        """Start listening for input events"""
        with self._lock:
            self._start_listeners()
    
    def _start_listeners(self):
        """Internal: create and start listeners with current suppress setting"""
        # Mouse listener
        self.mouse_listener = mouse.Listener(
            on_move=self._handle_mouse_move,
            on_click=self._handle_mouse_click,
            on_scroll=self._handle_mouse_scroll,
            suppress=self.suppress
        )
        
        # Keyboard listener
        self.keyboard_listener = keyboard.Listener(
            on_press=self._handle_key_press,
            on_release=self._handle_key_release,
            suppress=self.suppress
        )
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
        logger.info(f"Input listener started (suppress={self.suppress})")
    
    def _stop_listeners(self):
        """Internal: stop current listeners"""
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except:
                pass
            self.mouse_listener = None
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except:
                pass
            self.keyboard_listener = None
    
    def set_suppress(self, suppress: bool):
        """Change suppress mode by restarting listeners"""
        if suppress == self.suppress:
            return
        with self._lock:
            self.suppress = suppress
            self._stop_listeners()
            self._start_listeners()
            logger.info(f"Input listener suppress changed to {suppress}")
    
    def stop(self):
        """Stop listening for input events"""
        with self._lock:
            self._stop_listeners()
        logger.info("Input listener stopped")
    
    def _handle_mouse_move(self, x, y):
        """Handle mouse move event"""
        if self.on_mouse_move:
            self.on_mouse_move(x, y)
    
    def _handle_mouse_click(self, x, y, button, pressed):
        """Handle mouse click event"""
        if self.on_mouse_click:
            button_name = button.name  # 'left', 'right', 'middle'
            self.on_mouse_click(button_name, pressed)
    
    def _handle_mouse_scroll(self, x, y, dx, dy):
        """Handle mouse scroll event"""
        if self.on_mouse_scroll:
            self.on_mouse_scroll(dx, dy)
    
    def _handle_key_press(self, key):
        """Handle key press event"""
        if self.on_key_press:
            key_str = self._key_to_string(key)
            self.on_key_press(key_str)
    
    def _handle_key_release(self, key):
        """Handle key release event"""
        if self.on_key_release:
            key_str = self._key_to_string(key)
            self.on_key_release(key_str)
    
    def _key_to_string(self, key) -> str:
        """
        Convert pynput key to string
        
        Args:
            key: pynput Key or KeyCode object
            
        Returns:
            string representation of the key
        """
        try:
            # For special keys
            if hasattr(key, 'name'):
                return key.name.lower()
            # For character keys
            elif hasattr(key, 'char'):
                return key.char if key.char else ''
            else:
                return str(key)
        except Exception:
            return ''
