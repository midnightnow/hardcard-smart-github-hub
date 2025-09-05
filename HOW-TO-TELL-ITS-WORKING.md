# 🔍 How to Tell if HardCard Smart Hub is Working

## 📊 Quick Status Check

Run this command anytime to see if Smart Hub is active:

```bash
python3 hardcard-status.py
```

**Expected Output When Working:**
```
╔══════════════════════════════════════════════════════════╗
║          HardCard Smart Hub - System Status              ║
╚══════════════════════════════════════════════════════════╝

📋 Installation Status:
  ✅ Installed   Config File: /Users/you/.hardcard-hub/config.json
  ✅ Installed   Smart Wrapper: /Users/you/.local/bin/git-smart
  ✅ Installed   Pre Push Hook: /Users/you/.config/git/hooks/pre-push
  ✅ Installed   Core System: /Users/you/.hardcard-hub/smart_upload_manager.py

🎯 Overall Status:
  ✅ HardCard Smart Hub is installed and ready!
   Use 'git-smart push' for automatic chunking
```

## 🚨 Visual Indicators When It Engages

### 1. **Automatic Git Hook Detection**
When you try to push large files with regular `git push`, you'll see:

```
🔍 Pre-push hook activated!
⚠️ Large files detected that may cause timeout!
Files larger than 10MB:
  • models/neural_network.pkl (15MB)
  • data/training_set.csv (12MB)

💡 Recommendation: Use 'git-smart push' instead
```

### 2. **Smart Upload Activation Banner**
When smart upload engages, you'll see this banner:

```
============================================================
🔥 HARDCARD SMART HUB ACTIVATED
============================================================
📍 🚨 Large files detected - Smart Upload engaged!
⏰ 14:23:45
------------------------------------------------------------
✅ Intelligent chunking enabled
✅ Automatic resume on failure
✅ Network-aware optimization
✅ Progress tracking active
============================================================
```

### 3. **Real-time Progress Bar**
During upload, you'll see live progress:

```
🚀 [████████████████░░░░░░░░] 65.2% | 12.3 MB/s | ETA: 2m | Chunks: 13/20
```

### 4. **System Notifications**
On macOS/Linux/Windows, you'll get system notifications:

- **Title**: "HardCard Smart Hub"
- **Message**: "Smart Upload engaged! Optimizing your upload..."

## 🎯 How to Trigger Smart Upload

### Method 1: Use `git-smart` command
```bash
git add .
git commit -m "Large files"
git-smart push  # This will ALWAYS use smart upload
```

### Method 2: Let Git hooks detect automatically
```bash
git push  # Hook will detect large files and suggest git-smart
```

### Method 3: Direct upload command
```bash
hardcard-hub upload --source /path/to/repo --repo username/repo-name
```

### Method 4: Force with --smart flag
```bash
git push --smart  # Forces smart upload even for small repos
```

## 📁 Directory Detection

Smart Hub automatically activates when you `cd` into large repositories:

```bash
cd /path/to/large-repo
# Output: 💡 Large repository detected (150MB). Use 'git-smart' for uploads.
```

## 🔄 Session Management

### See Active Sessions
```bash
python3 hardcard-status.py
```

Will show:
```
📤 Active Upload Sessions:
  ⏳ In Progress abc123456789 → username/large-repo (73%)
  ✅ Complete   def987654321 → username/small-repo (100%)
```

### Resume Interrupted Upload
```bash
hardcard-hub resume --session abc123456789
```

## 🌐 Web Dashboard

Open the visual dashboard:
```bash
open ~/.hardcard-hub/web-dashboard.html
```

**Shows:**
- Live upload progress
- Network speed graphs  
- Session history
- Performance metrics

## 🎛️ Background Monitoring

Start the background monitor to watch for Git operations:

```bash
python3 smart-indicator.py
```

**Output:**
```
🔍 HardCard Smart Hub monitoring started...
💡 Monitoring for Git operations requiring smart upload
⏹️  Press Ctrl+C to stop
```

This will automatically detect and notify when large pushes are attempted.

## ⚙️ Configuration Check

Your config file at `~/.hardcard-hub/config.json` should contain:

```json
{
  "auto_detect_threshold_mb": 10,
  "auto_chunk_enabled": true,
  "network_auto_detect": true,
  "compression_enabled": true,
  "notification_enabled": true
}
```

## 🚦 Traffic Light System

| Status | Meaning | Action |
|--------|---------|--------|
| 🟢 **Green** | All systems working, Smart Hub ready | Use `git-smart push` for large repos |
| 🟡 **Yellow** | Partially installed or missing token | Run installation or set `GITHUB_TOKEN` |
| 🔴 **Red** | Not installed or major issues | Run `bash install-smart-hub.sh` |

## 🧪 Test That It's Working

### Quick Test:
1. Create a large file: `dd if=/dev/zero of=large-file.bin bs=1024 count=15000`
2. Add to git: `git add large-file.bin`  
3. Try to push: `git push`
4. **Expected**: Hook warns about large file, suggests `git-smart push`
5. Use smart push: `git-smart push`
6. **Expected**: See activation banner and progress bar

### Full Demo:
```bash
python3 demo_usage.py
```

This runs all 5 scenarios showing exactly how Smart Hub engages.

---

## ❓ Troubleshooting

**Not seeing any indicators?**
1. Run `python3 hardcard-status.py` to check installation
2. Make sure you're in a Git repository
3. Try with a file >10MB
4. Check that `GITHUB_TOKEN` is set

**Want more verbose output?**
Set environment variable: `export HARDCARD_VERBOSE=1`

**Need help?**
- Check logs: `~/.hardcard-hub/upload_manager.log`
- View sessions: `ls ~/.hardcard-hub/sessions/`
- Test connectivity: `ping github.com`

---

**🎯 Bottom Line**: If you see the activation banner and progress bar, Smart Hub is working! If not, run the status checker to diagnose.