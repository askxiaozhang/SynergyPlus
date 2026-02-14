"""
Communication protocol for SynergyPlus
Handles message serialization and deserialization
"""

import json
from enum import Enum
from typing import Dict, Any, Optional


class MessageType(Enum):
    """Message types for communication"""
    MOUSE_MOVE = 'mouse_move'
    MOUSE_CLICK = 'mouse_click'
    MOUSE_SCROLL = 'mouse_scroll'
    KEY_PRESS = 'key_press'
    KEY_RELEASE = 'key_release'
    HEARTBEAT = 'heartbeat'
    ACK = 'ack'
    SCREEN_INFO = 'screen_info'
    ENTER_SCREEN = 'enter_screen'
    LEAVE_SCREEN = 'leave_screen'
    CLIPBOARD_SYNC = 'clipboard_sync'
    FILE_TRANSFER_START = 'file_transfer_start'
    FILE_TRANSFER_CHUNK = 'file_transfer_chunk'
    FILE_TRANSFER_END = 'file_transfer_end'


class Message:
    """Protocol message wrapper"""
    
    def __init__(self, msg_type: MessageType, data: Optional[Dict[str, Any]] = None):
        self.type = msg_type
        self.data = data or {}
    
    def to_json(self) -> str:
        """Serialize message to JSON string"""
        return json.dumps({
            'type': self.type.value,
            'data': self.data
        })
    
    def to_bytes(self) -> bytes:
        """Serialize message to bytes with length prefix"""
        json_str = self.to_json()
        json_bytes = json_str.encode('utf-8')
        length = len(json_bytes)
        # 4-byte length prefix + json data
        return length.to_bytes(4, byteorder='big') + json_bytes
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Deserialize message from JSON string"""
        data = json.loads(json_str)
        msg_type = MessageType(data['type'])
        return cls(msg_type, data.get('data', {}))
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Message':
        """Deserialize message from bytes"""
        json_str = data.decode('utf-8')
        return cls.from_json(json_str)


class MouseMoveMessage(Message):
    """Mouse move message"""
    
    def __init__(self, x: int, y: int):
        super().__init__(MessageType.MOUSE_MOVE, {'x': x, 'y': y})


class MouseClickMessage(Message):
    """Mouse click message"""
    
    def __init__(self, button: str, pressed: bool):
        """
        Args:
            button: 'left', 'right', or 'middle'
            pressed: True for press, False for release
        """
        super().__init__(MessageType.MOUSE_CLICK, {
            'button': button,
            'pressed': pressed
        })


class MouseScrollMessage(Message):
    """Mouse scroll message"""
    
    def __init__(self, dx: int, dy: int):
        """
        Args:
            dx: horizontal scroll amount
            dy: vertical scroll amount
        """
        super().__init__(MessageType.MOUSE_SCROLL, {'dx': dx, 'dy': dy})


class KeyPressMessage(Message):
    """Key press message"""
    
    def __init__(self, key: str):
        super().__init__(MessageType.KEY_PRESS, {'key': key})


class KeyReleaseMessage(Message):
    """Key release message"""
    
    def __init__(self, key: str):
        super().__init__(MessageType.KEY_RELEASE, {'key': key})


class HeartbeatMessage(Message):
    """Heartbeat message to keep connection alive"""
    
    def __init__(self):
        super().__init__(MessageType.HEARTBEAT)


class AckMessage(Message):
    """Acknowledgment message"""
    
    def __init__(self):
        super().__init__(MessageType.ACK)


class ScreenInfoMessage(Message):
    """Report screen resolution to master"""
    
    def __init__(self, width: int, height: int):
        super().__init__(MessageType.SCREEN_INFO, {'width': width, 'height': height})


class EnterScreenMessage(Message):
    """Master tells server to place cursor at entry point"""
    
    def __init__(self, x: int, y: int, edge: str):
        """
        Args:
            x: entry X coordinate on the server screen
            y: entry Y coordinate on the server screen
            edge: which edge the cursor entered from ('left', 'right', 'top', 'bottom')
        """
        super().__init__(MessageType.ENTER_SCREEN, {'x': x, 'y': y, 'edge': edge})


class LeaveScreenMessage(Message):
    """Server tells master cursor has left its screen edge"""
    
    def __init__(self, edge: str, x: int, y: int):
        """
        Args:
            edge: which edge the cursor left from ('left', 'right', 'top', 'bottom')
            x: cursor X when leaving
            y: cursor Y when leaving
        """
        super().__init__(MessageType.LEAVE_SCREEN, {'edge': edge, 'x': x, 'y': y})


def receive_message(sock) -> Optional[Message]:
    """
    Receive a message from socket with length prefix
    
    Args:
        sock: socket object
        
    Returns:
        Message object or None if connection closed
    """
    # Read 4-byte length prefix
    length_data = b''
    while len(length_data) < 4:
        chunk = sock.recv(4 - len(length_data))
        if not chunk:
            return None
        length_data += chunk
    
    length = int.from_bytes(length_data, byteorder='big')
    
    # Read message data
    msg_data = b''
    while len(msg_data) < length:
        chunk = sock.recv(min(length - len(msg_data), 4096))
        if not chunk:
            return None
        msg_data += chunk
    
    return Message.from_bytes(msg_data)


def send_message(sock, message: Message) -> bool:
    """
    Send a message through socket
    
    Args:
        sock: socket object
        message: Message to send
        
    Returns:
        True if successful, False otherwise
    """
    try:
        sock.sendall(message.to_bytes())
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False


class ClipboardSyncMessage(Message):
    """Sync clipboard content between machines"""
    
    def __init__(self, content: str, content_type: str = 'text'):
        """
        Args:
            content: clipboard text content
            content_type: 'text' or 'file_ref'
        """
        super().__init__(MessageType.CLIPBOARD_SYNC, {
            'content': content,
            'content_type': content_type
        })


class FileTransferStartMessage(Message):
    """Start a file transfer"""
    
    def __init__(self, filename: str, file_size: int, transfer_id: str):
        super().__init__(MessageType.FILE_TRANSFER_START, {
            'filename': filename,
            'file_size': file_size,
            'transfer_id': transfer_id
        })


class FileTransferChunkMessage(Message):
    """Send a chunk of file data (base64 encoded)"""
    
    def __init__(self, transfer_id: str, chunk_index: int, data_b64: str):
        super().__init__(MessageType.FILE_TRANSFER_CHUNK, {
            'transfer_id': transfer_id,
            'chunk_index': chunk_index,
            'data': data_b64
        })


class FileTransferEndMessage(Message):
    """Mark file transfer as complete"""
    
    def __init__(self, transfer_id: str, total_chunks: int):
        super().__init__(MessageType.FILE_TRANSFER_END, {
            'transfer_id': transfer_id,
            'total_chunks': total_chunks
        })
