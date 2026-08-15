#!/usr/bin/env python3
"""
Amateur Radio Welfare Board System
Main GUI Application
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from pathlib import Path
import json
import shutil
from datetime import datetime
import webbrowser
import sys

# Import our modules
from parser import WelfareParser
from validator import WelfareValidator
from aggregator import WelfareAggregator
from output_generator import OutputGenerator
from file_watcher import WelfareFileWatcher


class WelfareBoardApp:
    """Main application for Welfare Board system"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Amateur Radio Welfare Board")
        self.root.geometry("900x700")
        
        # Load configuration
        self.config_file = Path('settings.json')
        self.load_config()
        
        # Initialize components
        self.parser = WelfareParser()
        self.validator = WelfareValidator(self.config)
        self.aggregator = WelfareAggregator(self.config)
        self.output_generator = OutputGenerator(self.config)
        self.file_watcher = None
        
        # State
        self.is_running = False
        
        # Setup GUI
        self.setup_gui()
        
        # Ensure directories exist
        self.create_directories()
        
        # Log startup
        self.log("Welfare Board System initialized")
        self.log(f"Monitoring: {self.config['directories']['input']}")
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                # Use default config
                self.config = {
                    'directories': {
                        'input': 'data/input',
                        'archive': 'data/archive',
                        'output': 'data/output',
                        'error': 'data/error'
                    },
                    'time_windows': [
                        {'name': 'Morning Net', 'start': '08:00', 'end': '10:00'},
                        {'name': 'Evening Net', 'start': '19:00', 'end': '21:00'}
                    ],
                    'output': {
                        'generate_text': True,
                        'generate_html': True,
                        'generate_csv': True,
                        'html_auto_refresh': 30
                    },
                    'validation': {
                        'require_callsign': True,
                        'require_name': True,
                        'require_location': True,
                        'require_status': True,
                        'valid_statuses': ['SAFE', 'NEED ASSISTANCE', 'TRAFFIC']
                    },
                    'logging': {
                        'level': 'INFO',
                        'max_file_size_mb': 10,
                        'backup_count': 5
                    }
                }
                self.save_config()
        except Exception as e:
            messagebox.showerror("Configuration Error", f"Error loading config: {e}")
            sys.exit(1)
    
    def save_config(self):
        """Save configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.log(f"Error saving config: {e}")
    
    def create_directories(self):
        """Create necessary directories"""
        for dir_type, dir_path in self.config['directories'].items():
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def setup_gui(self):
        """Setup the GUI"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="📡 Amateur Radio Welfare Board 📡",
            font=('Helvetica', 16, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="System Status", padding="10")
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        status_frame.columnconfigure(1, weight=1)
        
        ttk.Label(status_frame, text="Monitoring:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.monitor_label = ttk.Label(status_frame, text=self.config['directories']['input'], foreground="blue")
        self.monitor_label.grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(status_frame, text="Current Window:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.window_label = ttk.Label(status_frame, text="None", foreground="gray")
        self.window_label.grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        
        ttk.Label(status_frame, text="Check-ins:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.checkin_label = ttk.Label(status_frame, text="0", foreground="green")
        self.checkin_label.grid(row=2, column=1, sticky=tk.W, pady=(5, 0))
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, pady=(0, 10))
        
        self.start_button = ttk.Button(
            button_frame,
            text="▶ Start Monitoring",
            command=self.start_monitoring,
            width=20
        )
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="⏹ Stop",
            command=self.stop_monitoring,
            state=tk.DISABLED,
            width=15
        )
        self.stop_button.grid(row=0, column=1, padx=5)
        
        ttk.Button(
            button_frame,
            text="📁 Configure",
            command=self.open_settings,
            width=15
        )        .grid(row=0, column=2, padx=5)
        
        ttk.Button(
            button_frame,
            text="🌐 View Board",
            command=self.view_html_board,
            width=15
        ).grid(row=0, column=3, padx=5)
        
        ttk.Button(
            button_frame,
            text="📄 Template",
            command=self.open_template,
            width=15
        ).grid(row=0, column=4, padx=5)
        
        # Log window
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="5")
        log_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=100, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Update current window periodically
        self.update_current_window()
    
    def start_monitoring(self):
        """Start monitoring for welfare check-ins"""
        try:
            if self.is_running:
                return
            
            input_dir = Path(self.config['directories']['input'])
            
            if not input_dir.exists():
                messagebox.showerror("Error", f"Input directory does not exist: {input_dir}")
                return
            
            # Start file watcher
            self.file_watcher = WelfareFileWatcher(input_dir, self.process_new_file)
            self.file_watcher.start()
            
            self.is_running = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            
            self.log("✓ Started monitoring for welfare check-ins")
            self.log(f"  Watching: {input_dir}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start monitoring: {e}")
            self.log(f"✗ Error starting: {e}")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        if self.file_watcher:
            self.file_watcher.stop()
            self.file_watcher = None
        
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.log("⏹ Stopped monitoring")
    
    def process_new_file(self, filepath):
        """Process a newly received welfare check-in file"""
        try:
            self.log(f"📥 New file: {filepath.name}")
            
            # Parse file
            parsed_data = self.parser.parse_file(filepath)
            if not parsed_data:
                self.log(f"  ✗ Failed to parse file")
                self.move_to_error(filepath, "Parse failed")
                return
            
            # Validate
            is_valid, errors = self.validator.validate(parsed_data)
            if not is_valid:
                self.log(f"  ✗ Validation failed:")
                for error in errors:
                    self.log(f"    • {error}")
                self.move_to_error(filepath, f"Validation: {'; '.join(errors)}")
                return
            
            self.log(f"  ✓ Valid check-in from {parsed_data.get('callsign') or parsed_data.get('name', 'Unknown')}")
            
            # Add to aggregator
            success, message, window_info = self.aggregator.add_checkin(parsed_data)
            
            if not success:
                self.log(f"  ⚠ {message}")
                if "Duplicate" in message:
                    self.move_to_archive(filepath)
                else:
                    self.move_to_error(filepath, message)
                return
            
            self.log(f"  ✓ Added to {window_info['name']}")
            
            # Generate outputs
            checkins = self.aggregator.get_window_checkins(window_info['key'])
            generated = self.output_generator.generate_all(window_info, checkins)
            
            if generated:
                self.log(f"  ✓ Generated {len(generated)} output files")
            
            # Move to archive
            self.move_to_archive(filepath)
            
            # Update display
            self.update_checkin_count()
            
        except Exception as e:
            self.log(f"  ✗ Error processing file: {e}")
            self.move_to_error(filepath, str(e))
    
    def move_to_archive(self, filepath):
        """Move processed file to archive"""
        try:
            archive_dir = Path(self.config['directories']['archive'])
            dest = archive_dir / filepath.name
            
            # Add timestamp if file exists
            if dest.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                dest = archive_dir / f"{filepath.stem}_{timestamp}{filepath.suffix}"
            
            shutil.move(str(filepath), str(dest))
            self.log(f"  📦 Archived: {dest.name}")
        except Exception as e:
            self.log(f"  ⚠ Archive failed: {e}")
    
    def move_to_error(self, filepath, reason):
        """Move invalid file to error directory"""
        try:
            error_dir = Path(self.config['directories']['error'])
            dest = error_dir / filepath.name
            
            # Add timestamp if file exists
            if dest.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                dest = error_dir / f"{filepath.stem}_{timestamp}{filepath.suffix}"
            
            shutil.move(str(filepath), str(dest))
            
            # Write error log
            error_log = dest.with_suffix('.error.txt')
            error_log.write_text(f"Error: {reason}\nTime: {datetime.now()}\n")
            
            self.log(f"  ⚠ Moved to error folder: {reason}")
        except Exception as e:
            self.log(f"  ✗ Error move failed: {e}")
    
    def update_current_window(self):
        """Update current time window display"""
        window_info = self.aggregator.get_current_window()
        
        if window_info:
            self.window_label.config(
                text=f"{window_info['name']} ({window_info['start']}-{window_info['end']})",
                foreground="green"
            )
        else:
            self.window_label.config(text="No active window", foreground="gray")
        
        # Schedule next update
        self.root.after(60000, self.update_current_window)  # Every minute
    
    def update_checkin_count(self):
        """Update check-in counter"""
        window_info = self.aggregator.get_current_window()
        if window_info:
            count = self.aggregator.get_window_count(window_info['key'])
            self.checkin_label.config(text=str(count))
    
    def view_html_board(self):
        """Open HTML welfare board in browser"""
        html_file = Path(self.config['directories']['output']) / 'welfare_board.html'
        
        if html_file.exists():
            webbrowser.open(html_file.as_uri())
            self.log("🌐 Opened welfare board in browser")
        else:
            messagebox.showinfo("Info", "No welfare board generated yet. Start monitoring to collect check-ins.")
    
    def open_template(self):
        """Open template file for editing"""
        template_file = Path('welfare_checkin_template.txt')
        
        if not template_file.exists():
            # Create default template
            template_content = """CALLSIGN: (or leave blank if not a licensed ham)

NAME: 

LOCATION: 

STATUS: (SAFE / NEED ASSISTANCE / TRAFFIC)

POWER: (ON / OFF / GENERATOR)

CONTACT: (Phone# for SMS or Email to notify family)

MESSAGE:

"""
            template_file.write_text(template_content)
        
        # Open in default text editor
        if sys.platform == 'win32':
            import os
            os.startfile(template_file)
        elif sys.platform == 'darwin':
            import subprocess
            subprocess.call(['open', template_file])
        else:
            import subprocess
            subprocess.call(['xdg-open', template_file])
        
        self.log("📄 Opened template file")
    
    def open_settings(self):
        """Open settings dialog"""
        SettingsDialog(self.root, self.config, self.save_config, self.log)
    
    def log(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        self.log_text.update()


class SettingsDialog:
    """Settings configuration dialog"""
    
    def __init__(self, parent, config, save_callback, log_callback):
        self.config = config
        self.save_callback = save_callback
        self.log_callback = log_callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Welfare Board Settings")
        self.dialog.geometry("600x500")
        
        # Create notebook
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Directories tab
        dir_frame = ttk.Frame(notebook, padding=10)
        notebook.add(dir_frame, text="Directories")
        self.setup_directories_tab(dir_frame)
        
        # Time Windows tab
        windows_frame = ttk.Frame(notebook, padding=10)
        notebook.add(windows_frame, text="Time Windows")
        self.setup_windows_tab(windows_frame)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)
    
    def setup_directories_tab(self, parent):
        """Setup directories configuration"""
        dirs = self.config['directories']
        self.dir_entries = {}
        
        for i, (dir_type, dir_path) in enumerate(dirs.items()):
            ttk.Label(parent, text=f"{dir_type.title()}:").grid(row=i, column=0, sticky=tk.W, pady=5)
            
            entry = ttk.Entry(parent, width=40)
            entry.insert(0, dir_path)
            entry.grid(row=i, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 5))
            
            ttk.Button(
                parent,
                text="Browse",
                command=lambda e=entry: self.browse_directory(e)
            ).grid(row=i, column=2, pady=5)
            
            self.dir_entries[dir_type] = entry
        
        parent.columnconfigure(1, weight=1)
    
    def setup_windows_tab(self, parent):
        """Setup time windows configuration"""
        ttk.Label(
            parent,
            text="Configure time windows for welfare nets:",
            font=('Helvetica', 10, 'bold')
        ).pack(anchor=tk.W, pady=(0, 10))
        
        # TODO: Add time window editor
        # For now, show current windows
        windows = self.config.get('time_windows', [])
        for window in windows:
            window_text = f"{window['name']}: {window['start']} - {window['end']}"
            ttk.Label(parent, text=window_text).pack(anchor=tk.W, pady=2)
    
    def browse_directory(self, entry):
        """Browse for directory"""
        directory = filedialog.askdirectory(initialdir=entry.get())
        if directory:
            entry.delete(0, tk.END)
            entry.insert(0, directory)
    
    def save(self):
        """Save settings"""
        # Update directories
        for dir_type, entry in self.dir_entries.items():
            self.config['directories'][dir_type] = entry.get()
        
        # Save config
        self.save_callback()
        self.log_callback("✓ Settings saved")
        
        self.dialog.destroy()


def main():
    """Main entry point"""
    root = tk.Tk()
    app = WelfareBoardApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
