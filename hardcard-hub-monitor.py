#!/usr/bin/env python3
"""
HardCard Hub Monitor - Background service that watches for GitHub operations
Automatically engages smart chunking when needed
"""

import os
import sys
import time
import json
import psutil
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / '.hardcard-hub' / 'monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('HardCardMonitor')

class GitOperationMonitor(FileSystemEventHandler):
    """Monitors file system for Git operations"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.monitored_repos: Set[Path] = set()
        self.active_operations: Dict[str, Dict] = {}
        self.threshold_mb = config.get('auto_detect_threshold_mb', 10)
        
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
            
        path = Path(event.src_path)
        
        # Check if this is a git operation
        if '.git' in path.parts:
            self.check_git_operation(path)
            
    def check_git_operation(self, path: Path):
        """Check if a git operation needs smart upload"""
        try:
            # Find the repository root
            repo_root = self.find_repo_root(path)
            if not repo_root:
                return
                
            # Check if this repo is being pushed
            if self.is_push_operation(repo_root):
                # Check repository size
                size_mb = self.get_repo_size(repo_root)
                
                if size_mb > self.threshold_mb:
                    self.notify_smart_upload_needed(repo_root, size_mb)
                    
        except Exception as e:
            logger.error(f"Error checking git operation: {e}")
    
    def find_repo_root(self, path: Path) -> Optional[Path]:
        """Find the root of a git repository"""
        current = path.parent if path.is_file() else path
        
        while current != current.parent:
            if (current / '.git').exists():
                return current
            current = current.parent
            
        return None
    
    def is_push_operation(self, repo_root: Path) -> bool:
        """Check if a push operation is in progress"""
        # Check for push-related git files
        git_dir = repo_root / '.git'
        
        indicators = [
            git_dir / 'PUSH_HEAD',
            git_dir / 'ORIG_HEAD',
        ]
        
        for indicator in indicators:
            if indicator.exists():
                # Check if file was recently modified (within last 5 seconds)
                mtime = indicator.stat().st_mtime
                if time.time() - mtime < 5:
                    return True
                    
        return False
    
    def get_repo_size(self, repo_root: Path) -> int:
        """Get repository size in MB"""
        try:
            result = subprocess.run(
                ['du', '-sm', str(repo_root)],
                capture_output=True, text=True
            )
            size_mb = int(result.stdout.split()[0])
            return size_mb
        except:
            return 0
    
    def notify_smart_upload_needed(self, repo_root: Path, size_mb: int):
        """Notify user that smart upload should be used"""
        repo_name = repo_root.name
        
        # Don't notify repeatedly for the same repo
        if repo_root in self.monitored_repos:
            return
            
        self.monitored_repos.add(repo_root)
        
        # Show system notification (macOS)
        notification = f"Large repository detected ({size_mb}MB). Use 'git-smart push' for reliable upload."
        
        try:
            subprocess.run([
                'osascript', '-e',
                f'display notification "{notification}" with title "HardCard Smart Hub" subtitle "{repo_name}"'
            ])
        except:
            logger.info(f"Smart upload recommended for {repo_name} ({size_mb}MB)")

class ProcessMonitor:
    """Monitors system processes for git/gh operations"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.monitoring = False
        self.monitored_pids: Set[int] = set()
        
    def start(self):
        """Start monitoring processes"""
        self.monitoring = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        
    def stop(self):
        """Stop monitoring"""
        self.monitoring = False
        
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                self.check_processes()
                time.sleep(2)  # Check every 2 seconds
            except Exception as e:
                logger.error(f"Process monitoring error: {e}")
                
    def check_processes(self):
        """Check running processes for git operations"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                info = proc.info
                
                # Skip if already monitored
                if info['pid'] in self.monitored_pids:
                    continue
                    
                # Check for git push operations
                if info['name'] in ['git', 'git-remote-https', 'git-remote-http']:
                    cmdline = info.get('cmdline', [])
                    
                    if any('push' in arg for arg in cmdline):
                        self.handle_git_push(proc, cmdline)
                        
                # Check for gh CLI operations
                elif info['name'] == 'gh':
                    cmdline = info.get('cmdline', [])
                    
                    if any(cmd in cmdline for cmd in ['repo', 'release', 'gist']):
                        self.handle_gh_operation(proc, cmdline)
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
    def handle_git_push(self, proc, cmdline: List[str]):
        """Handle detected git push operation"""
        self.monitored_pids.add(proc.pid)
        
        # Get working directory
        try:
            cwd = proc.cwd()
            repo_size = self.get_directory_size(cwd)
            
            if repo_size > self.config.get('auto_detect_threshold_mb', 10):
                logger.info(f"Large git push detected: {cwd} ({repo_size}MB)")
                self.suggest_smart_upload(cwd, repo_size)
                
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
            
    def handle_gh_operation(self, proc, cmdline: List[str]):
        """Handle detected gh CLI operation"""
        self.monitored_pids.add(proc.pid)
        logger.info(f"GitHub CLI operation detected: {' '.join(cmdline)}")
        
    def get_directory_size(self, path: str) -> int:
        """Get directory size in MB"""
        try:
            result = subprocess.run(
                ['du', '-sm', path],
                capture_output=True, text=True
            )
            return int(result.stdout.split()[0])
        except:
            return 0
            
    def suggest_smart_upload(self, repo_path: str, size_mb: int):
        """Suggest using smart upload"""
        # Create a file that git-smart can detect
        flag_file = Path(repo_path) / '.git' / 'hardcard-smart-suggested'
        flag_file.write_text(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'size_mb': size_mb,
            'suggested': True
        }))

class HardCardHubService:
    """Main service coordinator"""
    
    def __init__(self):
        self.config = self.load_config()
        self.file_monitor = GitOperationMonitor(self.config)
        self.process_monitor = ProcessMonitor(self.config)
        self.observer = Observer()
        self.running = False
        
    def load_config(self) -> Dict:
        """Load service configuration"""
        config_path = Path.home() / '.hardcard-hub' / 'config.json'
        
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
                
        return {
            'auto_detect_threshold_mb': 10,
            'monitor_paths': [
                str(Path.home() / 'Documents'),
                str(Path.home() / 'Desktop'),
                str(Path.home() / 'repos'),
                str(Path.home() / 'projects'),
            ],
            'process_monitoring': True,
            'file_monitoring': True
        }
        
    def start(self):
        """Start the monitoring service"""
        logger.info("Starting HardCard Hub Monitor Service")
        self.running = True
        
        # Start file monitoring
        if self.config.get('file_monitoring', True):
            for path in self.config.get('monitor_paths', []):
                if Path(path).exists():
                    self.observer.schedule(self.file_monitor, path, recursive=True)
                    logger.info(f"Monitoring path: {path}")
                    
            self.observer.start()
            
        # Start process monitoring
        if self.config.get('process_monitoring', True):
            self.process_monitor.start()
            logger.info("Process monitoring started")
            
        # Register signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        logger.info("HardCard Hub Monitor is running")
        
        # Keep service running
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
            
    def stop(self):
        """Stop the monitoring service"""
        logger.info("Stopping HardCard Hub Monitor Service")
        self.running = False
        
        self.observer.stop()
        self.observer.join()
        
        self.process_monitor.stop()
        
        logger.info("Service stopped")
        
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self.stop()
        sys.exit(0)

def create_launch_agent():
    """Create macOS launch agent for automatic startup"""
    plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hardcard.hub.monitor</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{script_path}</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>StandardOutPath</key>
    <string>{log_path}/monitor.stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>{log_path}/monitor.stderr.log</string>
    
    <key>WorkingDirectory</key>
    <string>{working_dir}</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
    """.format(
        script_path=Path(__file__).resolve(),
        log_path=Path.home() / '.hardcard-hub',
        working_dir=Path.home() / '.hardcard-hub'
    )
    
    launch_agent_path = Path.home() / 'Library' / 'LaunchAgents' / 'com.hardcard.hub.monitor.plist'
    launch_agent_path.parent.mkdir(parents=True, exist_ok=True)
    launch_agent_path.write_text(plist_content)
    
    print(f"✅ Launch agent created at {launch_agent_path}")
    print("To start the service now: launchctl load ~/Library/LaunchAgents/com.hardcard.hub.monitor.plist")
    print("To start at login: Already configured (RunAtLoad=true)")
    
def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="HardCard Hub Monitor Service")
    parser.add_argument('--install', action='store_true', help='Install as system service')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    if args.install:
        create_launch_agent()
        print("✅ HardCard Hub Monitor installed as service")
        return
        
    # Run the service
    service = HardCardHubService()
    
    if args.daemon:
        # Daemonize
        import daemon
        with daemon.DaemonContext():
            service.start()
    else:
        service.start()

if __name__ == '__main__':
    main()