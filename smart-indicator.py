#!/usr/bin/env python3
"""
HardCard Smart Hub Visual Indicator
Shows visual feedback when smart upload is engaged
"""

import os
import sys
import time
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime

class SmartIndicator:
    """Visual indicator for smart upload status"""
    
    def __init__(self):
        self.active = False
        self.session_info = None
        
    def show_engagement_banner(self, trigger_reason="large_files_detected"):
        """Show that smart upload has been engaged"""
        banner_messages = {
            "large_files_detected": "🚨 Large files detected - Smart Upload engaged!",
            "network_timeout": "🌐 Network issues detected - Smart Upload engaged!",
            "manual_activation": "🚀 Smart Upload manually activated!",
            "git_hook_triggered": "🔍 Git hook triggered - Smart Upload engaged!",
            "resume_session": "🔄 Resuming previous upload session..."
        }
        
        message = banner_messages.get(trigger_reason, "🚀 Smart Upload engaged!")
        
        print("\n" + "="*60)
        print(f"🔥 HARDCARD SMART HUB ACTIVATED")
        print("="*60)
        print(f"📍 {message}")
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
        print("-"*60)
        print("✅ Intelligent chunking enabled")
        print("✅ Automatic resume on failure")
        print("✅ Network-aware optimization")
        print("✅ Progress tracking active")
        print("="*60)
        print()
        
    def show_progress_update(self, progress_data):
        """Show real-time progress update"""
        progress = progress_data.get('percentage', 0)
        speed = progress_data.get('speed_mbps', 0)
        eta = progress_data.get('eta_minutes', 0)
        chunks = progress_data.get('chunks', {})
        
        # Progress bar
        bar_width = 40
        filled = int(bar_width * progress / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        print(f"\r🚀 [{bar}] {progress:5.1f}% | {speed:5.1f} MB/s | ETA: {eta:3.0f}m | Chunks: {chunks.get('uploaded', 0)}/{chunks.get('total', 0)}", end="", flush=True)
        
        if progress >= 100:
            print("\n🎉 Upload completed successfully!")
            
    def show_network_adaptation(self, old_speed, new_speed, reason):
        """Show network speed adaptation"""
        print(f"\n🌐 Network adaptation: {old_speed.upper()} → {new_speed.upper()}")
        print(f"   Reason: {reason}")
        print(f"   Adjusting chunk sizes and parallelism...")
        
    def show_chunk_failure_recovery(self, chunk_id, retry_count):
        """Show chunk failure and recovery"""
        print(f"\n🔄 Chunk {chunk_id} failed, retrying ({retry_count}/3)...")
        
    def show_rate_limit_wait(self, wait_seconds):
        """Show rate limit waiting period"""
        print(f"\n⏳ GitHub rate limit reached, waiting {wait_seconds}s...")
        
        # Countdown timer
        for i in range(wait_seconds, 0, -1):
            print(f"\r   Resuming in {i:3d}s...", end="", flush=True)
            time.sleep(1)
        print("\r   ✅ Rate limit cleared, resuming...     ")
        
    def show_session_saved(self, session_id):
        """Show that session has been saved for recovery"""
        print(f"\n💾 Session saved: {session_id}")
        print(f"   Resume with: hardcard-hub resume --session {session_id}")

def create_notification_system():
    """Create system notifications for different platforms"""
    
    def notify_macos(title, message, sound=True):
        """Send macOS notification"""
        cmd = ['osascript', '-e', f'display notification "{message}" with title "{title}"']
        if sound:
            cmd.extend(['-e', 'beep'])
        try:
            subprocess.run(cmd, check=True)
        except:
            pass
    
    def notify_linux(title, message):
        """Send Linux notification"""
        try:
            subprocess.run(['notify-send', title, message], check=True)
        except:
            pass
    
    def notify_windows(title, message):
        """Send Windows notification"""
        try:
            import plyer
            plyer.notification.notify(title=title, message=message, timeout=5)
        except:
            pass
    
    # Detect platform and return appropriate function
    if sys.platform == 'darwin':
        return notify_macos
    elif sys.platform.startswith('linux'):
        return notify_linux
    elif sys.platform == 'win32':
        return notify_windows
    else:
        return lambda title, msg: print(f"{title}: {msg}")

class SmartUploadNotifier:
    """Handles all notifications and visual feedback"""
    
    def __init__(self):
        self.indicator = SmartIndicator()
        self.notify = create_notification_system()
        self.monitoring = False
        
    def start_monitoring(self):
        """Start monitoring for upload activities"""
        self.monitoring = True
        
        # Monitor thread
        def monitor_loop():
            while self.monitoring:
                self.check_for_uploads()
                time.sleep(2)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
    def check_for_uploads(self):
        """Check for active uploads and show status"""
        sessions_dir = Path.home() / '.hardcard-hub' / 'sessions'
        
        if not sessions_dir.exists():
            return
            
        # Check for active sessions
        for session_file in sessions_dir.glob('*.json'):
            try:
                with open(session_file) as f:
                    session_data = json.load(f)
                
                if not session_data.get('completed', True):
                    # Active session found
                    self.show_active_session(session_data)
                    
            except Exception:
                continue
    
    def show_active_session(self, session_data):
        """Show status of active session"""
        session_id = session_data.get('session_id', 'unknown')
        progress = session_data.get('progress_percentage', 0)
        repo_name = session_data.get('repo_name', 'unknown')
        
        # Update console
        print(f"\r🚀 Active: {repo_name} [{progress:5.1f}%] Session: {session_id[:8]}", end="", flush=True)
        
    def engage_smart_upload(self, trigger="large_files", details=None):
        """Main engagement function - shows all visual feedback"""
        
        # Show banner
        self.indicator.show_engagement_banner(trigger)
        
        # Send system notification
        self.notify(
            "HardCard Smart Hub", 
            f"Smart Upload engaged! {details or 'Optimizing your upload...'}"
        )
        
        # Start visual monitoring
        if not self.monitoring:
            self.start_monitoring()

def demo_engagement():
    """Demonstrate the engagement system"""
    notifier = SmartUploadNotifier()
    
    print("🧪 Demonstrating Smart Hub engagement system...")
    
    # Simulate different engagement scenarios
    scenarios = [
        ("large_files_detected", "Repository contains 50MB+ files"),
        ("git_hook_triggered", "Pre-push hook detected large content"),
        ("network_timeout", "Connection timeout detected"),
        ("resume_session", "Resuming interrupted session abc123")
    ]
    
    for trigger, details in scenarios:
        print(f"\n📋 Scenario: {trigger}")
        notifier.engage_smart_upload(trigger, details)
        
        # Simulate progress
        for progress in range(0, 101, 20):
            progress_data = {
                'percentage': progress,
                'speed_mbps': 15.5,
                'eta_minutes': (100 - progress) / 10,
                'chunks': {'uploaded': progress // 10, 'total': 10}
            }
            notifier.indicator.show_progress_update(progress_data)
            time.sleep(0.5)
        
        if trigger != scenarios[-1][0]:  # Don't wait after last scenario
            print("\n\n⏳ Next scenario in 3 seconds...")
            time.sleep(3)
    
    print("\n\n✅ Demo complete!")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo_engagement()
    else:
        # Start monitoring mode
        notifier = SmartUploadNotifier()
        notifier.start_monitoring()
        
        print("🔍 HardCard Smart Hub monitoring started...")
        print("💡 Monitoring for Git operations requiring smart upload")
        print("⏹️  Press Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")
            notifier.monitoring = False