#!/bin/bash

# HardCard Smart GitHub Hub - Automatic Integration Installer
# This script integrates the smart upload system into your workflow

set -e

INSTALL_DIR="$HOME/.hardcard-hub"
BIN_DIR="$HOME/.local/bin"
HOOKS_DIR="$HOME/.hardcard-hub/hooks"
CONFIG_FILE="$HOME/.hardcard-hub/config.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     HardCard Smart GitHub Hub - Auto-Engagement Setup     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Create installation directories
echo -e "${YELLOW}Creating installation directories...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$HOOKS_DIR"
mkdir -p "$HOME/.config/git/hooks"

# Install Python package
echo -e "${YELLOW}Installing Python package...${NC}"
pip3 install --upgrade hardcard-github-hub || pip3 install -e .

# Copy core files
echo -e "${YELLOW}Installing core components...${NC}"
cp smart-upload-manager.py "$INSTALL_DIR/"
cp web-dashboard.html "$INSTALL_DIR/"

# Create configuration file
echo -e "${YELLOW}Creating configuration...${NC}"
cat > "$CONFIG_FILE" << 'EOF'
{
  "auto_detect_threshold_mb": 10,
  "auto_chunk_enabled": true,
  "network_auto_detect": true,
  "compression_enabled": true,
  "exclude_patterns": [
    "*.pyc", "*.pyo", "__pycache__",
    ".git/objects", ".git/lfs",
    "node_modules", "venv", "env",
    "*.log", "*.tmp", ".DS_Store"
  ],
  "github_token_env": "GITHUB_TOKEN",
  "max_chunk_size_mb": 25,
  "parallel_uploads": 3,
  "auto_resume": true,
  "notification_enabled": true
}
EOF

# Create the smart git wrapper
echo -e "${YELLOW}Creating git wrapper...${NC}"
cat > "$BIN_DIR/git-smart" << 'EOF'
#!/usr/bin/env python3
"""
Smart Git Wrapper - Automatically uses HardCard Hub for large uploads
"""
import os
import sys
import subprocess
import json
from pathlib import Path

CONFIG_FILE = Path.home() / '.hardcard-hub' / 'config.json'
SMART_HUB = Path.home() / '.hardcard-hub' / 'smart-upload-manager.py'

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def get_repo_size():
    """Get the size of the current repository in MB"""
    try:
        result = subprocess.run(['du', '-sm', '.'], capture_output=True, text=True)
        size_mb = int(result.stdout.split()[0])
        return size_mb
    except:
        return 0

def should_use_smart_upload(args):
    """Determine if we should use smart upload"""
    config = load_config()
    
    # Check if this is a push command
    if 'push' not in args:
        return False
    
    # Check repository size
    size_mb = get_repo_size()
    threshold = config.get('auto_detect_threshold_mb', 10)
    
    if size_mb > threshold:
        print(f"📦 Repository size: {size_mb}MB - Using HardCard Smart Upload")
        return True
    
    # Check for force flag
    if '--smart' in args or '-S' in args:
        return True
    
    return False

def run_smart_upload():
    """Run the smart upload manager"""
    config = load_config()
    
    # Get GitHub token
    token = os.environ.get(config.get('github_token_env', 'GITHUB_TOKEN'))
    if not token:
        print("❌ GitHub token not found. Set GITHUB_TOKEN environment variable.")
        return 1
    
    # Get repository info
    try:
        remote_url = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True, text=True
        ).stdout.strip()
        
        # Extract repo name from URL
        if 'github.com' in remote_url:
            repo_name = remote_url.split('github.com')[-1]
            repo_name = repo_name.strip('/:').replace('.git', '')
        else:
            print("❌ Not a GitHub repository")
            return 1
            
    except:
        print("❌ Could not determine repository")
        return 1
    
    # Run smart upload
    cmd = [
        sys.executable, str(SMART_HUB),
        'upload',
        '--source', '.',
        '--repo', repo_name,
        '--token', token
    ]
    
    print(f"🚀 Starting HardCard Smart Upload for {repo_name}")
    return subprocess.call(cmd)

def main():
    args = sys.argv[1:]
    
    if should_use_smart_upload(args):
        # Remove --smart flag if present
        args = [a for a in args if a not in ['--smart', '-S']]
        
        # First, commit any changes
        subprocess.call(['git'] + args[:args.index('push')])
        
        # Then use smart upload
        return run_smart_upload()
    else:
        # Use regular git
        return subprocess.call(['git'] + args)

if __name__ == '__main__':
    sys.exit(main())
EOF

chmod +x "$BIN_DIR/git-smart"

# Create global git hooks
echo -e "${YELLOW}Installing Git hooks...${NC}"

# Pre-push hook to detect large files
cat > "$HOME/.config/git/hooks/pre-push" << 'EOF'
#!/bin/bash
# HardCard Smart Hub - Pre-push Hook
# Warns about large files and suggests using smart upload

THRESHOLD_MB=10
LARGE_FILES=0

# Check for large files
while read local_ref local_sha remote_ref remote_sha; do
    if [ "$local_sha" != "0000000000000000000000000000000000000000" ]; then
        for file in $(git diff --name-only "$remote_sha" "$local_sha" 2>/dev/null); do
            if [ -f "$file" ]; then
                size=$(du -m "$file" 2>/dev/null | cut -f1)
                if [ "$size" -gt "$THRESHOLD_MB" ]; then
                    echo "⚠️  Large file detected: $file (${size}MB)"
                    LARGE_FILES=$((LARGE_FILES + 1))
                fi
            fi
        done
    fi
done

if [ "$LARGE_FILES" -gt 0 ]; then
    echo ""
    echo "🚨 Found $LARGE_FILES large file(s) that may cause timeouts!"
    echo "💡 Recommendation: Use 'git-smart push' for automatic chunking"
    echo ""
    echo "Install: curl -sSL https://hardcard.ai/smart-hub | bash"
    echo "Or abort this push (Ctrl+C) and run: git-smart push"
    echo ""
    read -p "Continue with regular push? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
EOF

chmod +x "$HOME/.config/git/hooks/pre-push"

# Create shell aliases
echo -e "${YELLOW}Creating shell aliases...${NC}"

# For bash
if [ -f "$HOME/.bashrc" ]; then
    grep -q "HardCard Smart Hub" "$HOME/.bashrc" || cat >> "$HOME/.bashrc" << 'EOF'

# HardCard Smart Hub aliases
alias gsp='git-smart push'
alias gspu='git-smart push -u origin main'
alias hardcard-upload='python3 ~/.hardcard-hub/smart-upload-manager.py'
alias hardcard-dashboard='open ~/.hardcard-hub/web-dashboard.html'

# Auto-detect large repos on cd
cd() {
    builtin cd "$@"
    if [ -d .git ]; then
        size=$(du -sm . 2>/dev/null | cut -f1)
        if [ "$size" -gt 50 ]; then
            echo "💡 Large repository detected (${size}MB). Use 'git-smart' for uploads."
        fi
    fi
}
EOF
fi

# For zsh
if [ -f "$HOME/.zshrc" ]; then
    grep -q "HardCard Smart Hub" "$HOME/.zshrc" || cat >> "$HOME/.zshrc" << 'EOF'

# HardCard Smart Hub aliases
alias gsp='git-smart push'
alias gspu='git-smart push -u origin main'
alias hardcard-upload='python3 ~/.hardcard-hub/smart-upload-manager.py'
alias hardcard-dashboard='open ~/.hardcard-hub/web-dashboard.html'

# Auto-detect large repos on cd
cd() {
    builtin cd "$@"
    if [ -d .git ]; then
        size=$(du -sm . 2>/dev/null | cut -f1)
        if [ "$size" -gt 50 ]; then
            echo "💡 Large repository detected (${size}MB). Use 'git-smart' for uploads."
        fi
    fi
}
EOF
fi

# Add to PATH
echo -e "${YELLOW}Updating PATH...${NC}"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$HOME/.bashrc"
    echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$HOME/.zshrc"
fi

# Create git config alias
git config --global alias.smart '!git-smart'
git config --global core.hooksPath "$HOME/.config/git/hooks"

# Success message
echo ""
echo -e "${GREEN}✅ HardCard Smart Hub successfully installed!${NC}"
echo ""
echo -e "${BLUE}Available commands:${NC}"
echo "  git-smart push       - Smart push with automatic chunking"
echo "  gsp                  - Alias for git-smart push"
echo "  hardcard-upload      - Direct access to upload manager"
echo "  hardcard-dashboard   - Open monitoring dashboard"
echo ""
echo -e "${BLUE}Features enabled:${NC}"
echo "  ✓ Automatic large file detection"
echo "  ✓ Pre-push warnings and recommendations"
echo "  ✓ Smart chunking for files >10MB"
echo "  ✓ Auto-resume on failures"
echo "  ✓ Network speed optimization"
echo ""
echo -e "${YELLOW}Restart your terminal or run: source ~/.bashrc${NC}"
echo ""
echo -e "${GREEN}🚀 Never lose an upload to timeouts again!${NC}"