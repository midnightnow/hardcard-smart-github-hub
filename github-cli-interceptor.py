#!/usr/bin/env python3
"""
GitHub CLI Interceptor - Seamlessly integrates smart chunking with gh CLI
Intercepts gh commands and uses smart upload for large operations
"""

import os
import sys
import subprocess
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import argparse
import re

class GitHubCLIInterceptor:
    """Intercepts GitHub CLI commands and applies smart chunking when needed"""
    
    def __init__(self):
        self.config_path = Path.home() / '.hardcard-hub' / 'config.json'
        self.smart_hub_path = Path.home() / '.hardcard-hub' / 'smart-upload-manager.py'
        self.config = self.load_config()
        self.original_gh = self.find_original_gh()
        
    def load_config(self) -> Dict:
        """Load configuration"""
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)
        return {
            'auto_detect_threshold_mb': 10,
            'auto_chunk_enabled': True
        }
    
    def find_original_gh(self) -> Optional[str]:
        """Find the original gh CLI binary"""
        # Look for gh in standard locations
        paths = [
            '/usr/local/bin/gh',
            '/opt/homebrew/bin/gh',
            '/usr/bin/gh',
            shutil.which('gh.original'),  # If we renamed it
        ]
        
        for path in paths:
            if path and Path(path).exists() and path != sys.argv[0]:
                return path
        
        return None
    
    def parse_gh_command(self, args: List[str]) -> Tuple[str, Dict]:
        """Parse gh command to understand what's being done"""
        if not args:
            return 'help', {}
        
        command_type = args[0] if args else 'help'
        params = {}
        
        # Detect repo creation with clone
        if command_type == 'repo' and len(args) > 1:
            if args[1] == 'clone' and len(args) > 2:
                params['action'] = 'clone'
                params['repo'] = args[2]
                params['size_check_needed'] = True
                
            elif args[1] == 'create':
                params['action'] = 'create'
                params['needs_upload'] = self.check_current_dir_size()
                
        # Detect release uploads
        elif command_type == 'release' and len(args) > 1:
            if args[1] == 'upload':
                params['action'] = 'release_upload'
                params['files'] = self.extract_files_from_args(args[2:])
                params['large_files'] = self.check_large_files(params['files'])
                
        # Detect gist creation with large files
        elif command_type == 'gist' and len(args) > 1:
            if args[1] == 'create':
                params['action'] = 'gist_create'
                params['files'] = self.extract_files_from_args(args[2:])
                params['large_files'] = self.check_large_files(params['files'])
        
        # Detect pr creation with large diffs
        elif command_type == 'pr' and len(args) > 1:
            if args[1] == 'create':
                params['action'] = 'pr_create'
                params['diff_size'] = self.get_git_diff_size()
                
        return command_type, params
    
    def check_current_dir_size(self) -> bool:
        """Check if current directory is large enough to need smart upload"""
        try:
            result = subprocess.run(['du', '-sm', '.'], capture_output=True, text=True)
            size_mb = int(result.stdout.split()[0])
            threshold = self.config.get('auto_detect_threshold_mb', 10)
            return size_mb > threshold
        except:
            return False
    
    def extract_files_from_args(self, args: List[str]) -> List[str]:
        """Extract file paths from command arguments"""
        files = []
        for arg in args:
            if not arg.startswith('-') and Path(arg).exists():
                files.append(arg)
        return files
    
    def check_large_files(self, files: List[str]) -> List[Tuple[str, int]]:
        """Check for large files that need chunking"""
        large_files = []
        threshold_mb = self.config.get('auto_detect_threshold_mb', 10)
        
        for file_path in files:
            try:
                size_mb = Path(file_path).stat().st_size / (1024 * 1024)
                if size_mb > threshold_mb:
                    large_files.append((file_path, size_mb))
            except:
                pass
                
        return large_files
    
    def get_git_diff_size(self) -> int:
        """Get the size of the current git diff in MB"""
        try:
            result = subprocess.run(
                ['git', 'diff', '--cached', '--stat'],
                capture_output=True, text=True
            )
            # Parse the stat output for total size
            lines = result.stdout.strip().split('\n')
            if lines:
                # Look for the summary line
                for line in reversed(lines):
                    if 'changed' in line or 'insertion' in line:
                        # Extract numbers from the line
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            # Rough estimate: assume each change is ~80 bytes
                            total_changes = sum(int(n) for n in numbers)
                            size_mb = (total_changes * 80) / (1024 * 1024)
                            return int(size_mb)
        except:
            pass
        return 0
    
    def should_use_smart_upload(self, command_type: str, params: Dict) -> bool:
        """Determine if smart upload should be used"""
        if not self.config.get('auto_chunk_enabled', True):
            return False
        
        # Check various conditions
        if params.get('needs_upload'):
            return True
        
        if params.get('large_files'):
            return True
            
        if params.get('diff_size', 0) > self.config.get('auto_detect_threshold_mb', 10):
            return True
            
        return False
    
    def notify_user(self, message: str, level: str = 'info'):
        """Show notification to user"""
        icons = {
            'info': '💡',
            'warning': '⚠️',
            'success': '✅',
            'error': '❌'
        }
        
        colors = {
            'info': '\033[0;34m',
            'warning': '\033[1;33m',
            'success': '\033[0;32m',
            'error': '\033[0;31m'
        }
        
        reset = '\033[0m'
        icon = icons.get(level, '📌')
        color = colors.get(level, '')
        
        print(f"{color}{icon} {message}{reset}")
    
    def run_smart_upload_workflow(self, command_type: str, params: Dict, original_args: List[str]) -> int:
        """Execute smart upload workflow"""
        self.notify_user("Large content detected - Using HardCard Smart Upload", "info")
        
        if command_type == 'repo' and params.get('action') == 'create':
            # Create repo first, then smart upload
            result = subprocess.call([self.original_gh] + original_args)
            if result != 0:
                return result
            
            # Get repo name
            repo_name = self.get_current_repo_name()
            if repo_name:
                self.notify_user(f"Uploading repository contents with smart chunking...", "info")
                return self.run_smart_upload(repo_name)
                
        elif command_type == 'release' and params.get('large_files'):
            # Handle large release assets
            self.notify_user(f"Uploading {len(params['large_files'])} large files with chunking", "info")
            
            # Upload normal files with gh
            normal_files = [f for f in params.get('files', []) 
                          if f not in [lf[0] for lf in params['large_files']]]
            
            if normal_files:
                subprocess.call([self.original_gh] + original_args[:2] + normal_files)
            
            # Upload large files with smart chunking
            for file_path, size_mb in params['large_files']:
                self.notify_user(f"Uploading {file_path} ({size_mb:.1f}MB) with smart chunking", "info")
                # Implement release asset chunking here
                
        return 0
    
    def get_current_repo_name(self) -> Optional[str]:
        """Get the current repository name"""
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True, text=True
            )
            url = result.stdout.strip()
            if 'github.com' in url:
                # Extract owner/repo from URL
                match = re.search(r'github\.com[:/]([^/]+/[^/\.]+)', url)
                if match:
                    return match.group(1).replace('.git', '')
        except:
            pass
        return None
    
    def run_smart_upload(self, repo_name: str) -> int:
        """Run the smart upload manager"""
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            self.notify_user("GITHUB_TOKEN not set - falling back to regular upload", "warning")
            return 1
        
        cmd = [
            sys.executable, str(self.smart_hub_path),
            'upload',
            '--source', '.',
            '--repo', repo_name,
            '--token', token
        ]
        
        return subprocess.call(cmd)
    
    def run(self, args: List[str]) -> int:
        """Main interceptor logic"""
        # Parse the command
        command_type, params = self.parse_gh_command(args)
        
        # Check if smart upload should be used
        if self.should_use_smart_upload(command_type, params):
            return self.run_smart_upload_workflow(command_type, params, args)
        
        # Otherwise, pass through to original gh
        if self.original_gh:
            return subprocess.call([self.original_gh] + args)
        else:
            self.notify_user("Original gh CLI not found", "error")
            return 1

def install_interceptor():
    """Install the interceptor as the default gh command"""
    print("Installing GitHub CLI interceptor...")
    
    # Find current gh location
    gh_path = shutil.which('gh')
    if not gh_path:
        print("❌ GitHub CLI (gh) not found. Please install it first.")
        return False
    
    # Backup original gh
    gh_backup = gh_path + '.original'
    if not Path(gh_backup).exists():
        shutil.copy2(gh_path, gh_backup)
        print(f"✅ Backed up original gh to {gh_backup}")
    
    # Install interceptor
    interceptor_path = Path(__file__).resolve()
    shutil.copy2(interceptor_path, gh_path)
    os.chmod(gh_path, 0o755)
    
    print(f"✅ Interceptor installed at {gh_path}")
    print("💡 All gh commands will now use smart chunking for large uploads")
    
    return True

def main():
    """Main entry point"""
    # Check if this is an installation request
    if len(sys.argv) > 1 and sys.argv[1] == '--install':
        return 0 if install_interceptor() else 1
    
    # Otherwise, run as interceptor
    interceptor = GitHubCLIInterceptor()
    return interceptor.run(sys.argv[1:])

if __name__ == '__main__':
    sys.exit(main())