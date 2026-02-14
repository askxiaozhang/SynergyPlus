"""
Input controller for mouse and keyboard control using pynput
"""

from pynput import mouse, keyboard
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController
import logging

logger = logging.getLogger(__name__)


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


class InputListener:
    """Listener for mouse and keyboard input"""
    
    def __init__(self, on_mouse_move=None, on_mouse_click=None, 
                 on_mouse_scroll=None, on_key_press=None, on_key_release=None):
        self.on_mouse_move = on_mouse_move
        self.on_mouse_click = on_mouse_click
        self.on_mouse_scroll = on_mouse_scroll
        self.on_key_press = on_key_press
        self.on_key_release = on_key_release
        
        self.mouse_listener = None
        self.keyboard_listener = None
    
    def start(self):
        """Start listening for input events"""
        # Mouse listener
        self.mouse_listener = mouse.Listener(
            on_move=self._handle_mouse_move,
            on_click=self._handle_mouse_click,
            on_scroll=self._handle_mouse_scroll
        )
        
        # Keyboard listener
        self.keyboard_listener = keyboard.Listener(
            on_press=self._handle_key_press,
            on_release=self._handle_key_release
        )
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
        logger.info("Input listener started")
    
    def stop(self):
        """Stop listening for input events"""
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
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
