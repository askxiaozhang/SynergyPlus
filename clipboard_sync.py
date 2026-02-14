"""
Clipboard synchronization module for SynergyPlus.
Monitors clipboard changes and syncs between master and server.
Supports text and file clipboard content.
"""

import os
import time
import base64
import uuid
import platform
import threading
import logging
import subprocess

from protocol import (
    ClipboardSyncMessage, FileTransferStartMessage,
    FileTransferChunkMessage, FileTransferEndMessage,
    MessageType
)

logger = logging.getLogger(__name__)

# File transfer chunk size (64KB)
CHUNK_SIZE = 65536

# Default max file size for transfer (100MB)
DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024


def get_clipboard_text():
    """Get text content from system clipboard"""
    system = platform.system()
    try:
        if system == 'Darwin':
            result = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=2)
            return result.stdout if result.returncode == 0 else ''
        elif system == 'Linux':
            result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'],
                                    capture_output=True, text=True, timeout=2)
            return result.stdout if result.returncode == 0 else ''
        elif system == 'Windows':
            import ctypes
            # Use win32 API
            CF_UNICODETEXT = 13
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if user32.OpenClipboard(0):
                try:
                    handle = user32.GetClipboardData(CF_UNICODETEXT)
                    if handle:
                        kernel32.GlobalLock.restype = ctypes.c_wchar_p
                        text = kernel32.GlobalLock(handle)
                        kernel32.GlobalUnlock(handle)
                        return text or ''
                finally:
                    user32.CloseClipboard()
    except Exception as e:
        logger.debug(f"Clipboard read error: {e}")
    return ''


def set_clipboard_text(text: str):
    """Set text content to system clipboard"""
    system = platform.system()
    try:
        if system == 'Darwin':
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(text.encode('utf-8'))
        elif system == 'Linux':
            process = subprocess.Popen(['xclip', '-selection', 'clipboard'],
                                       stdin=subprocess.PIPE)
            process.communicate(text.encode('utf-8'))
        elif system == 'Windows':
            import ctypes
            CF_UNICODETEXT = 13
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if user32.OpenClipboard(0):
                try:
                    user32.EmptyClipboard()
                    data = text.encode('utf-16-le') + b'\x00\x00'
                    h = kernel32.GlobalAlloc(0x0042, len(data))
                    p = kernel32.GlobalLock(h)
                    ctypes.memmove(p, data, len(data))
                    kernel32.GlobalUnlock(h)
                    user32.SetClipboardData(CF_UNICODETEXT, h)
                finally:
                    user32.CloseClipboard()
    except Exception as e:
        logger.error(f"Clipboard write error: {e}")


def get_clipboard_files():
    """Get file paths from clipboard (macOS/Linux)"""
    system = platform.system()
    try:
        if system == 'Darwin':
            # Use osascript to check for file clipboard
            script = '''
            try
                set theFiles to (the clipboard as «class furl») as text
                return theFiles
            on error
                return ""
            end try
            '''
            result = subprocess.run(['osascript', '-e', script],
                                    capture_output=True, text=True, timeout=3)
            if result.returncode == 0 and result.stdout.strip():
                # macOS returns "Macintosh HD:Users:..." format
                path = result.stdout.strip()
                # Convert HFS path to POSIX
                result2 = subprocess.run(
                    ['osascript', '-e', f'POSIX path of "{path}"'],
                    capture_output=True, text=True, timeout=2
                )
                if result2.returncode == 0 and result2.stdout.strip():
                    fpath = result2.stdout.strip()
                    if os.path.exists(fpath):
                        return [fpath]
    except Exception as e:
        logger.debug(f"Clipboard file check error: {e}")
    return []


class ClipboardMonitor:
    """
    Monitors clipboard changes and calls a callback when content changes.
    """
    
    def __init__(self, on_text_change=None, on_file_change=None, poll_interval=0.5):
        self.on_text_change = on_text_change
        self.on_file_change = on_file_change
        self.poll_interval = poll_interval
        self.running = False
        self.thread = None
        self.last_text = ''
        self._skip_next = False  # skip change triggered by our own set_clipboard
    
    def start(self):
        """Start monitoring clipboard"""
        self.running = True
        self.last_text = get_clipboard_text()
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("Clipboard monitor started")
    
    def stop(self):
        """Stop monitoring clipboard"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Clipboard monitor stopped")
    
    def skip_next_change(self):
        """Skip the next detected change (used after we paste content ourselves)"""
        self._skip_next = True
    
    def _monitor_loop(self):
        while self.running:
            try:
                current_text = get_clipboard_text()
                
                if current_text and current_text != self.last_text:
                    self.last_text = current_text
                    
                    if self._skip_next:
                        self._skip_next = False
                    else:
                        # Check if clipboard contains files
                        files = get_clipboard_files()
                        if files and self.on_file_change:
                            self.on_file_change(files)
                        elif self.on_text_change:
                            self.on_text_change(current_text)
            except Exception as e:
                logger.debug(f"Clipboard monitor error: {e}")
            
            time.sleep(self.poll_interval)


class FileTransferManager:
    """Handles sending and receiving file transfers"""
    
    def __init__(self, save_dir=None, max_file_size=DEFAULT_MAX_FILE_SIZE):
        self.save_dir = save_dir or os.path.join(os.path.expanduser('~'), 'SynergyPlus_Files')
        self.max_file_size = max_file_size
        self.pending_transfers = {}  # transfer_id -> {filename, size, chunks: {}}
        os.makedirs(self.save_dir, exist_ok=True)
    
    def send_file(self, filepath: str, send_func) -> bool:
        """
        Send a file via the provided send function.
        
        Args:
            filepath: path to the file
            send_func: callable(message) that sends a protocol message
        
        Returns:
            True if transfer started, False if file too large
        """
        if not os.path.isfile(filepath):
            logger.error(f"File not found: {filepath}")
            return False
        
        file_size = os.path.getsize(filepath)
        if file_size > self.max_file_size:
            logger.warning(f"File too large: {file_size} > {self.max_file_size}")
            return False
        
        transfer_id = str(uuid.uuid4())[:8]
        filename = os.path.basename(filepath)
        
        # Send start message
        send_func(FileTransferStartMessage(filename, file_size, transfer_id))
        
        # Send chunks
        chunk_index = 0
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                data_b64 = base64.b64encode(chunk).decode('ascii')
                send_func(FileTransferChunkMessage(transfer_id, chunk_index, data_b64))
                chunk_index += 1
        
        # Send end message
        send_func(FileTransferEndMessage(transfer_id, chunk_index))
        logger.info(f"File sent: {filename} ({file_size} bytes, {chunk_index} chunks)")
        return True
    
    def handle_transfer_start(self, data: dict):
        """Handle FILE_TRANSFER_START message"""
        transfer_id = data['transfer_id']
        filename = data['filename']
        file_size = data['file_size']
        
        if file_size > self.max_file_size:
            logger.warning(f"Incoming file too large: {file_size}, rejecting")
            return
        
        self.pending_transfers[transfer_id] = {
            'filename': filename,
            'size': file_size,
            'chunks': {}
        }
        logger.info(f"Receiving file: {filename} ({file_size} bytes)")
    
    def handle_transfer_chunk(self, data: dict):
        """Handle FILE_TRANSFER_CHUNK message"""
        transfer_id = data['transfer_id']
        if transfer_id not in self.pending_transfers:
            return
        
        chunk_index = data['chunk_index']
        chunk_data = base64.b64decode(data['data'])
        self.pending_transfers[transfer_id]['chunks'][chunk_index] = chunk_data
    
    def handle_transfer_end(self, data: dict) -> str:
        """
        Handle FILE_TRANSFER_END message. Assembles and saves the file.
        
        Returns:
            Path to saved file, or empty string on failure
        """
        transfer_id = data['transfer_id']
        total_chunks = data['total_chunks']
        
        if transfer_id not in self.pending_transfers:
            return ''
        
        transfer = self.pending_transfers.pop(transfer_id)
        filename = transfer['filename']
        
        # Assemble file
        save_path = os.path.join(self.save_dir, filename)
        # Don't overwrite — add suffix if exists
        base, ext = os.path.splitext(save_path)
        counter = 1
        while os.path.exists(save_path):
            save_path = f"{base}_{counter}{ext}"
            counter += 1
        
        try:
            with open(save_path, 'wb') as f:
                for i in range(total_chunks):
                    if i in transfer['chunks']:
                        f.write(transfer['chunks'][i])
                    else:
                        logger.error(f"Missing chunk {i} for {filename}")
                        return ''
            
            logger.info(f"File saved: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return ''
