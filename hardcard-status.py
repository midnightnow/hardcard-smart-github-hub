#!/usr/bin/env python3
"""
HardCard Smart Hub Status Checker
Shows if the smart upload system is active and working
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'

def print_header():
    """Print status header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════════════╗{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}║          HardCard Smart Hub - System Status              ║{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚══════════════════════════════════════════════════════════╝{Colors.ENDC}")

def check_installation():
    """Check if HardCard Hub is installed"""
    checks = {
        'config_file': Path.home() / '.hardcard-hub' / 'config.json',
        'smart_wrapper': Path.home() / '.local' / 'bin' / 'git-smart',
        'pre_push_hook': Path.home() / '.config' / 'git' / 'hooks' / 'pre-push',
        'core_system': Path.home() / '.hardcard-hub' / 'smart_upload_manager.py',
        'web_dashboard': Path.home() / '.hardcard-hub' / 'web-dashboard.html'
    }
    
    print(f"\n{Colors.BOLD}📋 Installation Status:{Colors.ENDC}")
    
    all_installed = True
    for name, path in checks.items():
        status = "✅ Installed" if path.exists() else "❌ Missing"
        color = Colors.GREEN if path.exists() else Colors.RED
        print(f"  {color}{status:12}{Colors.ENDC} {name.replace('_', ' ').title()}: {path}")
        
        if not path.exists():
            all_installed = False
    
    return all_installed

def check_git_integration():
    """Check Git integration status"""
    print(f"\n{Colors.BOLD}🔗 Git Integration:{Colors.ENDC}")
    
    # Check git-smart alias
    try:
        result = subprocess.run(['git', 'config', 'alias.smart'], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  {Colors.GREEN}✅ Configured{Colors.ENDC} Git alias 'git smart' → git-smart")
        else:
            print(f"  {Colors.RED}❌ Missing{Colors.ENDC}    Git alias not configured")
    except:
        print(f"  {Colors.RED}❌ Error{Colors.ENDC}      Could not check Git configuration")
    
    # Check global hooks path
    try:
        result = subprocess.run(['git', 'config', 'core.hooksPath'], 
                               capture_output=True, text=True)
        hooks_path = result.stdout.strip()
        if hooks_path:
            print(f"  {Colors.GREEN}✅ Configured{Colors.ENDC} Global hooks: {hooks_path}")
        else:
            print(f"  {Colors.YELLOW}⚠️  Default{Colors.ENDC}    Using repository-specific hooks")
    except:
        print(f"  {Colors.RED}❌ Error{Colors.ENDC}      Could not check hooks configuration")

def check_current_repo():
    """Check if current directory is a Git repository and analyze it"""
    print(f"\n{Colors.BOLD}📁 Current Repository Analysis:{Colors.ENDC}")
    
    if not Path('.git').exists():
        print(f"  {Colors.YELLOW}ℹ️  Not in a Git repository{Colors.ENDC}")
        return
    
    # Get repository size
    try:
        result = subprocess.run(['du', '-sm', '.'], capture_output=True, text=True)
        size_mb = int(result.stdout.split()[0])
        
        if size_mb > 50:
            color = Colors.RED
            recommendation = "🚨 Use 'git-smart push' for uploads"
        elif size_mb > 10:
            color = Colors.YELLOW
            recommendation = "⚠️  Consider 'git-smart push' for reliability"
        else:
            color = Colors.GREEN
            recommendation = "✅ Regular git push should work fine"
        
        print(f"  {color}Repository size: {size_mb}MB{Colors.ENDC}")
        print(f"  {recommendation}")
        
        # Check for large files
        large_files = []
        for file_path in Path('.').rglob('*'):
            if file_path.is_file() and not '.git' in file_path.parts:
                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    if size_mb > 10:
                        large_files.append((str(file_path), size_mb))
                except:
                    pass
        
        if large_files:
            print(f"\n  {Colors.BOLD}📦 Large Files Detected:{Colors.ENDC}")
            for file_path, size_mb in large_files[:5]:  # Show top 5
                print(f"    {Colors.YELLOW}⚠️  {size_mb:6.1f}MB{Colors.ENDC} {file_path}")
            
            if len(large_files) > 5:
                print(f"    ... and {len(large_files) - 5} more")
                
    except Exception as e:
        print(f"  {Colors.RED}❌ Error analyzing repository: {e}{Colors.ENDC}")

def check_network_connectivity():
    """Check network connectivity for uploads"""
    print(f"\n{Colors.BOLD}🌐 Network Status:{Colors.ENDC}")
    
    try:
        # Test GitHub connectivity
        result = subprocess.run(['ping', '-c', '1', 'github.com'], 
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"  {Colors.GREEN}✅ Connected{Colors.ENDC}  GitHub.com is reachable")
        else:
            print(f"  {Colors.RED}❌ Failed{Colors.ENDC}     Cannot reach GitHub.com")
            
    except subprocess.TimeoutExpired:
        print(f"  {Colors.YELLOW}⚠️  Timeout{Colors.ENDC}    Network test timed out")
    except Exception as e:
        print(f"  {Colors.RED}❌ Error{Colors.ENDC}      Network test failed: {e}")
    
    # Check GitHub token
    github_token = os.environ.get('GITHUB_TOKEN')
    if github_token:
        print(f"  {Colors.GREEN}✅ Found{Colors.ENDC}      GitHub token in environment")
    else:
        print(f"  {Colors.YELLOW}⚠️  Missing{Colors.ENDC}    GITHUB_TOKEN environment variable not set")

def show_active_sessions():
    """Show any active upload sessions"""
    sessions_dir = Path.home() / '.hardcard-hub' / 'sessions'
    
    if not sessions_dir.exists():
        return
    
    session_files = list(sessions_dir.glob('*.json'))
    
    if session_files:
        print(f"\n{Colors.BOLD}📤 Active Upload Sessions:{Colors.ENDC}")
        
        for session_file in session_files[:5]:  # Show up to 5
            try:
                with open(session_file) as f:
                    session_data = json.load(f)
                
                session_id = session_data.get('session_id', 'unknown')[:12]
                repo_name = session_data.get('repo_name', 'unknown')
                progress = session_data.get('progress_percentage', 0)
                
                if progress < 100:
                    print(f"  {Colors.YELLOW}⏳ In Progress{Colors.ENDC} {session_id} → {repo_name} ({progress:.0f}%)")
                else:
                    print(f"  {Colors.GREEN}✅ Complete{Colors.ENDC}   {session_id} → {repo_name} (100%)")
                    
            except Exception as e:
                print(f"  {Colors.RED}❌ Error{Colors.ENDC}      Could not read session {session_file.name}")

def show_recommendations():
    """Show actionable recommendations"""
    print(f"\n{Colors.BOLD}💡 Quick Commands:{Colors.ENDC}")
    
    # Check if installed
    config_file = Path.home() / '.hardcard-hub' / 'config.json'
    
    if not config_file.exists():
        print(f"  {Colors.CYAN}📥 Install:{Colors.ENDC}        bash install-smart-hub.sh")
        print(f"  {Colors.CYAN}🔧 Setup:{Colors.ENDC}          export GITHUB_TOKEN='your_token_here'")
    else:
        print(f"  {Colors.CYAN}🚀 Smart Push:{Colors.ENDC}     git-smart push")
        print(f"  {Colors.CYAN}📊 Dashboard:{Colors.ENDC}      open ~/.hardcard-hub/web-dashboard.html")
        print(f"  {Colors.CYAN}📈 Monitor:{Colors.ENDC}        hardcard-hub status --session SESSION_ID")
        print(f"  {Colors.CYAN}🔄 Resume:{Colors.ENDC}         hardcard-hub resume --session SESSION_ID")

def main():
    """Main status check function"""
    print_header()
    
    # Run all checks
    is_installed = check_installation()
    check_git_integration()
    check_current_repo()
    check_network_connectivity()
    show_active_sessions()
    show_recommendations()
    
    # Overall status
    print(f"\n{Colors.BOLD}🎯 Overall Status:{Colors.ENDC}")
    
    if is_installed:
        print(f"  {Colors.GREEN}✅ HardCard Smart Hub is installed and ready!{Colors.ENDC}")
        print(f"  {Colors.GREEN}   Use 'git-smart push' for automatic chunking{Colors.ENDC}")
    else:
        print(f"  {Colors.YELLOW}⚠️  HardCard Smart Hub needs installation{Colors.ENDC}")
        print(f"  {Colors.YELLOW}   Run: bash install-smart-hub.sh{Colors.ENDC}")
    
    print()

if __name__ == "__main__":
    main()