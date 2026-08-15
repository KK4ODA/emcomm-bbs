"""
Welfare Board - File Watcher Module
Monitors directory for new welfare check-in files
"""

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import time


class WelfareFileHandler(FileSystemEventHandler):
    """Handle new welfare check-in files"""
    
    def __init__(self, callback):
        """
        Initialize file handler
        
        Args:
            callback: Function to call when new file detected
                      callback(filepath)
        """
        self.callback = callback
        self.processing = set()  # Track files being processed
        
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
        
        filepath = Path(event.src_path)
        
        # Only process .txt files
        if filepath.suffix.lower() != '.txt':
            return
        
        # Ignore VarAC temporary files (start with $$)
        if filepath.name.startswith('$$'):
            return
        
        # Ignore error logs
        if '.error.' in filepath.name:
            return
        
        # Avoid processing the same file multiple times
        if str(filepath) in self.processing:
            return
        
        # Wait a moment for file to be fully written
        time.sleep(0.5)
        
        # Mark as processing
        self.processing.add(str(filepath))
        
        try:
            # Call the callback
            self.callback(filepath)
        finally:
            # Remove from processing set after a delay
            time.sleep(1)
            self.processing.discard(str(filepath))
    
    def on_modified(self, event):
        """Handle file modification events"""
        # Treat modifications like new files for simplicity
        # (some file transfer methods trigger modify instead of create)
        if event.is_directory:
            return
        
        filepath = Path(event.src_path)
        
        if filepath.suffix.lower() != '.txt':
            return
        
        # Only process if not already processing
        if str(filepath) not in self.processing:
            self.on_created(event)


class WelfareFileWatcher:
    """Watch directory for new welfare check-in files"""
    
    def __init__(self, watch_dir, callback):
        """
        Initialize file watcher
        
        Args:
            watch_dir: Directory to monitor
            callback: Function to call when new file arrives
        """
        self.watch_dir = Path(watch_dir)
        self.callback = callback
        self.observer = None
        self.handler = None
        
        # Ensure directory exists
        self.watch_dir.mkdir(parents=True, exist_ok=True)
    
    def start(self):
        """Start watching for files"""
        if self.observer and self.observer.is_alive():
            return  # Already running
        
        self.handler = WelfareFileHandler(self.callback)
        self.observer = Observer()
        self.observer.schedule(self.handler, str(self.watch_dir), recursive=False)
        self.observer.start()
        
        print(f"Started watching: {self.watch_dir}")
    
    def stop(self):
        """Stop watching for files"""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=5)
            print("Stopped file watcher")
    
    def is_running(self):
        """Check if watcher is running"""
        return self.observer and self.observer.is_alive()


if __name__ == '__main__':
    # Test the file watcher
    import tempfile
    import shutil
    
    # Create temp directory
    test_dir = Path(tempfile.mkdtemp())
    print(f"Test directory: {test_dir}")
    
    # Define callback
    def on_new_file(filepath):
        print(f"New file detected: {filepath.name}")
        print(f"  Size: {filepath.stat().st_size} bytes")
        print(f"  Content preview:")
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()[:5]
                for line in lines:
                    print(f"    {line.rstrip()}")
        except Exception as e:
            print(f"    Error reading: {e}")
    
    # Start watcher
    watcher = WelfareFileWatcher(test_dir, on_new_file)
    watcher.start()
    
    print("\nWatcher is running. Creating test files...")
    print("Press Ctrl+C to stop\n")
    
    try:
        # Create test files
        for i in range(3):
            time.sleep(2)
            test_file = test_dir / f"test_welfare_{i}.txt"
            test_file.write_text(f"CALLSIGN: KD8XX{i}\nNAME: Test User {i}\n")
            print(f"Created: {test_file.name}")
        
        # Keep running
        print("\nWaiting for more files... (Ctrl+C to stop)")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping watcher...")
        watcher.stop()
        
    finally:
        # Cleanup
        shutil.rmtree(test_dir)
        print(f"Cleaned up test directory")
