#!/usr/bin/env python3
"""
HardCard Smart GitHub Upload Manager
Intelligent chunking and upload system for large repositories and desktop backups
Prevents timeouts, handles interruptions, and provides optimal transfer speeds
"""

import os
import sys
import json
import time
import hashlib
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import zipfile
import tarfile
import base64
from tqdm import tqdm
import requests
from github import Github, GithubException, RateLimitExceededException
import git
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('upload_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ChunkInfo:
    """Information about a file chunk"""
    chunk_id: str
    file_path: str
    chunk_index: int
    total_chunks: int
    size: int
    checksum: str
    uploaded: bool = False
    upload_time: Optional[float] = None
    retry_count: int = 0

@dataclass
class UploadSession:
    """Manages an upload session"""
    session_id: str
    repo_name: str
    source_path: str
    total_size: int
    chunks: List[ChunkInfo]
    start_time: datetime
    completed: bool = False
    progress_percentage: float = 0.0
    
class SmartUploadManager:
    """Intelligent upload manager with chunking and optimization"""
    
    # Optimal chunk sizes based on network conditions
    CHUNK_SIZES = {
        'slow': 1 * 1024 * 1024,      # 1MB for slow connections
        'medium': 5 * 1024 * 1024,     # 5MB for medium connections
        'fast': 10 * 1024 * 1024,      # 10MB for fast connections
        'ultra': 25 * 1024 * 1024      # 25MB for ultra-fast connections
    }
    
    # File type optimizations
    COMPRESSIBLE_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json', '.xml', '.yml', '.yaml'}
    SKIP_EXTENSIONS = {'.pyc', '.pyo', '.pyd', '.so', '.dylib', '.dll', '.exe'}
    BINARY_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.avi', '.zip', '.tar', '.gz'}
    
    def __init__(self, github_token: str, max_retries: int = 3):
        """Initialize the upload manager"""
        self.github_token = github_token
        self.github = Github(github_token)
        self.max_retries = max_retries
        self.sessions: Dict[str, UploadSession] = {}
        self.network_speed = 'medium'  # Default, will be auto-detected
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    def analyze_network_speed(self) -> str:
        """Detect network speed for optimal chunk sizing"""
        try:
            # Test upload speed with a small file
            test_size = 1024 * 100  # 100KB test
            test_data = os.urandom(test_size)
            
            start_time = time.time()
            response = requests.post(
                'https://httpbin.org/post',
                data=test_data,
                timeout=10
            )
            elapsed = time.time() - start_time
            
            # Calculate speed in MB/s
            speed_mbps = (test_size / elapsed) / (1024 * 1024)
            
            if speed_mbps < 1:
                return 'slow'
            elif speed_mbps < 5:
                return 'medium'
            elif speed_mbps < 20:
                return 'fast'
            else:
                return 'ultra'
                
        except Exception as e:
            logger.warning(f"Network speed detection failed: {e}, using medium")
            return 'medium'
    
    def analyze_repository(self, repo_path: str) -> Dict[str, Any]:
        """Analyze repository for optimization opportunities"""
        stats = {
            'total_files': 0,
            'total_size': 0,
            'compressible_size': 0,
            'binary_size': 0,
            'skip_files': [],
            'large_files': [],
            'git_objects_size': 0,
            'recommendations': []
        }
        
        repo_path = Path(repo_path)
        
        # Check if it's a git repository
        try:
            repo = git.Repo(repo_path)
            git_dir = repo_path / '.git'
            if git_dir.exists():
                stats['git_objects_size'] = sum(
                    f.stat().st_size for f in git_dir.rglob('*') if f.is_file()
                )
        except:
            pass
        
        # Analyze files
        for file_path in repo_path.rglob('*'):
            if file_path.is_file():
                try:
                    size = file_path.stat().st_size
                    stats['total_files'] += 1
                    stats['total_size'] += size
                    
                    # Check file type
                    ext = file_path.suffix.lower()
                    
                    if ext in self.SKIP_EXTENSIONS:
                        stats['skip_files'].append(str(file_path))
                    elif ext in self.COMPRESSIBLE_EXTENSIONS:
                        stats['compressible_size'] += size
                    elif ext in self.BINARY_EXTENSIONS:
                        stats['binary_size'] += size
                    
                    # Track large files
                    if size > 50 * 1024 * 1024:  # Files larger than 50MB
                        stats['large_files'].append({
                            'path': str(file_path),
                            'size': size
                        })
                        
                except Exception as e:
                    logger.warning(f"Error analyzing {file_path}: {e}")
        
        # Generate recommendations
        if stats['git_objects_size'] > stats['total_size'] * 0.5:
            stats['recommendations'].append("Consider running 'git gc' to optimize repository size")
        
        if stats['compressible_size'] > stats['total_size'] * 0.3:
            stats['recommendations'].append("Repository has significant compressible content - will use compression")
        
        if len(stats['large_files']) > 0:
            stats['recommendations'].append(f"Found {len(stats['large_files'])} large files - will use adaptive chunking")
        
        return stats
    
    def create_smart_chunks(self, file_path: str, session_id: str) -> List[ChunkInfo]:
        """Create optimized chunks for a file"""
        file_path = Path(file_path)
        file_size = file_path.stat().st_size
        
        # Determine chunk size based on file size and network speed
        chunk_size = self.CHUNK_SIZES[self.network_speed]
        
        # Adaptive chunking for large files
        if file_size > 100 * 1024 * 1024:  # Files > 100MB
            chunk_size = min(chunk_size * 2, 50 * 1024 * 1024)  # Max 50MB chunks
        
        chunks = []
        num_chunks = (file_size + chunk_size - 1) // chunk_size
        
        with open(file_path, 'rb') as f:
            for i in range(num_chunks):
                chunk_data = f.read(chunk_size)
                chunk_checksum = hashlib.sha256(chunk_data).hexdigest()
                
                chunk_info = ChunkInfo(
                    chunk_id=f"{session_id}_{file_path.name}_{i}",
                    file_path=str(file_path),
                    chunk_index=i,
                    total_chunks=num_chunks,
                    size=len(chunk_data),
                    checksum=chunk_checksum
                )
                chunks.append(chunk_info)
        
        return chunks
    
    def compress_directory(self, source_path: str, output_path: str, 
                          exclude_patterns: List[str] = None) -> str:
        """Compress directory with smart filtering"""
        source_path = Path(source_path)
        output_path = Path(output_path)
        
        # Default exclusions
        default_exclude = [
            '*.pyc', '*.pyo', '__pycache__',
            '.git/objects', '.git/lfs',
            'node_modules', 'venv', 'env',
            '*.log', '*.tmp', '.DS_Store'
        ]
        
        exclude_patterns = (exclude_patterns or []) + default_exclude
        
        # Create tar.gz with compression
        archive_path = output_path / f"{source_path.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"
        
        with tarfile.open(archive_path, 'w:gz') as tar:
            for item in source_path.rglob('*'):
                # Check exclusions
                should_exclude = False
                for pattern in exclude_patterns:
                    if item.match(pattern):
                        should_exclude = True
                        break
                
                if not should_exclude and item.is_file():
                    arcname = item.relative_to(source_path.parent)
                    tar.add(item, arcname=arcname)
                    
        return str(archive_path)
    
    async def upload_chunk_to_github(self, chunk: ChunkInfo, repo_name: str) -> bool:
        """Upload a single chunk to GitHub with retry logic"""
        for attempt in range(self.max_retries):
            try:
                repo = self.github.get_repo(repo_name)
                
                # Read chunk data
                with open(chunk.file_path, 'rb') as f:
                    f.seek(chunk.chunk_index * self.CHUNK_SIZES[self.network_speed])
                    chunk_data = f.read(chunk.size)
                
                # Encode for GitHub
                content = base64.b64encode(chunk_data).decode('utf-8')
                
                # Create unique path for chunk
                chunk_path = f".uploads/{chunk.chunk_id}"
                
                # Upload to GitHub
                repo.create_file(
                    path=chunk_path,
                    message=f"Upload chunk {chunk.chunk_index + 1}/{chunk.total_chunks}",
                    content=content,
                    branch="uploads"
                )
                
                chunk.uploaded = True
                chunk.upload_time = time.time()
                logger.info(f"Successfully uploaded chunk {chunk.chunk_id}")
                return True
                
            except RateLimitExceededException:
                # Handle rate limiting
                reset_time = self.github.get_rate_limit().core.reset
                wait_time = (reset_time - datetime.utcnow()).total_seconds()
                logger.warning(f"Rate limited, waiting {wait_time} seconds")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error uploading chunk {chunk.chunk_id}: {e}")
                chunk.retry_count += 1
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
        return False
    
    async def parallel_upload(self, session: UploadSession, max_concurrent: int = 3):
        """Upload chunks in parallel with rate limiting"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def upload_with_semaphore(chunk):
            async with semaphore:
                return await self.upload_chunk_to_github(chunk, session.repo_name)
        
        # Filter chunks that need uploading
        pending_chunks = [c for c in session.chunks if not c.uploaded]
        
        # Create progress bar
        with tqdm(total=len(pending_chunks), desc="Uploading chunks") as pbar:
            tasks = []
            for chunk in pending_chunks:
                task = asyncio.create_task(upload_with_semaphore(chunk))
                tasks.append((chunk, task))
            
            for chunk, task in tasks:
                success = await task
                if success:
                    pbar.update(1)
                    
                # Update session progress
                uploaded_count = sum(1 for c in session.chunks if c.uploaded)
                session.progress_percentage = (uploaded_count / len(session.chunks)) * 100
    
    def create_upload_session(self, source_path: str, repo_name: str) -> UploadSession:
        """Create a new upload session"""
        session_id = hashlib.sha256(f"{source_path}_{datetime.now()}".encode()).hexdigest()[:16]
        
        # Analyze source
        if Path(source_path).is_dir():
            stats = self.analyze_repository(source_path)
            logger.info(f"Repository analysis: {stats['recommendations']}")
            
            # Compress if beneficial
            if stats['compressible_size'] > 10 * 1024 * 1024:  # > 10MB compressible
                logger.info("Compressing repository for optimal transfer...")
                compressed_path = self.compress_directory(source_path, Path.cwd())
                source_path = compressed_path
        
        # Create chunks
        chunks = []
        if Path(source_path).is_file():
            chunks = self.create_smart_chunks(source_path, session_id)
        else:
            # Create chunks for all files in directory
            for file_path in Path(source_path).rglob('*'):
                if file_path.is_file():
                    chunks.extend(self.create_smart_chunks(str(file_path), session_id))
        
        session = UploadSession(
            session_id=session_id,
            repo_name=repo_name,
            source_path=source_path,
            total_size=sum(c.size for c in chunks),
            chunks=chunks,
            start_time=datetime.now()
        )
        
        self.sessions[session_id] = session
        
        # Save session for recovery
        self.save_session(session)
        
        return session
    
    def save_session(self, session: UploadSession):
        """Save session state for recovery"""
        session_file = Path(f".upload_sessions/{session.session_id}.json")
        session_file.parent.mkdir(exist_ok=True)
        
        with open(session_file, 'w') as f:
            # Convert to dict for JSON serialization
            session_dict = asdict(session)
            session_dict['start_time'] = session.start_time.isoformat()
            json.dump(session_dict, f, indent=2)
    
    def load_session(self, session_id: str) -> Optional[UploadSession]:
        """Load a previous session for resuming"""
        session_file = Path(f".upload_sessions/{session_id}.json")
        
        if not session_file.exists():
            return None
        
        with open(session_file, 'r') as f:
            session_dict = json.load(f)
            
        # Convert back to UploadSession
        session_dict['start_time'] = datetime.fromisoformat(session_dict['start_time'])
        session_dict['chunks'] = [ChunkInfo(**c) for c in session_dict['chunks']]
        
        return UploadSession(**session_dict)
    
    async def resume_upload(self, session_id: str) -> bool:
        """Resume an interrupted upload"""
        session = self.load_session(session_id)
        
        if not session:
            logger.error(f"Session {session_id} not found")
            return False
        
        logger.info(f"Resuming upload session {session_id}")
        logger.info(f"Progress: {session.progress_percentage:.1f}% complete")
        
        # Re-detect network speed
        self.network_speed = self.analyze_network_speed()
        logger.info(f"Network speed: {self.network_speed}")
        
        # Continue upload
        await self.parallel_upload(session)
        
        # Check if complete
        if all(c.uploaded for c in session.chunks):
            session.completed = True
            logger.info(f"Upload session {session_id} completed successfully!")
            return True
        
        return False
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get detailed status of an upload session"""
        session = self.sessions.get(session_id) or self.load_session(session_id)
        
        if not session:
            return {'error': 'Session not found'}
        
        uploaded_chunks = sum(1 for c in session.chunks if c.uploaded)
        failed_chunks = sum(1 for c in session.chunks if c.retry_count >= self.max_retries)
        
        elapsed_time = (datetime.now() - session.start_time).total_seconds()
        uploaded_size = sum(c.size for c in session.chunks if c.uploaded)
        
        # Calculate ETA
        if uploaded_size > 0 and elapsed_time > 0:
            upload_speed = uploaded_size / elapsed_time
            remaining_size = session.total_size - uploaded_size
            eta_seconds = remaining_size / upload_speed if upload_speed > 0 else 0
        else:
            eta_seconds = 0
        
        return {
            'session_id': session.session_id,
            'repo_name': session.repo_name,
            'source_path': session.source_path,
            'total_chunks': len(session.chunks),
            'uploaded_chunks': uploaded_chunks,
            'failed_chunks': failed_chunks,
            'progress_percentage': session.progress_percentage,
            'total_size_mb': session.total_size / (1024 * 1024),
            'uploaded_size_mb': uploaded_size / (1024 * 1024),
            'elapsed_time': str(timedelta(seconds=int(elapsed_time))),
            'eta': str(timedelta(seconds=int(eta_seconds))),
            'completed': session.completed
        }

class GitHubBackupOrchestrator:
    """High-level orchestrator for complete GitHub backup solutions"""
    
    def __init__(self, github_token: str):
        self.upload_manager = SmartUploadManager(github_token)
        self.github = Github(github_token)
        
    async def backup_desktop_to_github(self, desktop_path: str = None, 
                                       repo_name: str = "desktop-backup") -> str:
        """Backup entire desktop or specific folders to GitHub"""
        desktop_path = desktop_path or str(Path.home() / "Desktop")
        
        logger.info(f"Starting desktop backup from {desktop_path}")
        
        # Create or get repository
        try:
            repo = self.github.get_repo(f"{self.github.user.login}/{repo_name}")
        except:
            logger.info(f"Creating repository {repo_name}")
            repo = self.github.user.create_repo(
                name=repo_name,
                private=True,
                description="Automated desktop backup by HardCard Smart Upload Manager"
            )
        
        # Detect network speed
        self.upload_manager.network_speed = self.upload_manager.analyze_network_speed()
        logger.info(f"Detected network speed: {self.upload_manager.network_speed}")
        
        # Create upload session
        session = self.upload_manager.create_upload_session(desktop_path, repo.full_name)
        
        logger.info(f"Created upload session: {session.session_id}")
        logger.info(f"Total chunks to upload: {len(session.chunks)}")
        
        # Start upload
        await self.upload_manager.parallel_upload(session)
        
        return session.session_id
    
    async def sync_local_repos_to_github(self, local_repos_path: str) -> List[str]:
        """Sync all local repositories to GitHub"""
        local_repos_path = Path(local_repos_path)
        session_ids = []
        
        for repo_dir in local_repos_path.iterdir():
            if repo_dir.is_dir() and (repo_dir / '.git').exists():
                logger.info(f"Syncing repository: {repo_dir.name}")
                
                # Create GitHub repo if doesn't exist
                repo_name = repo_dir.name
                try:
                    github_repo = self.github.get_repo(f"{self.github.user.login}/{repo_name}")
                except:
                    github_repo = self.github.user.create_repo(
                        name=repo_name,
                        private=True,
                        description=f"Synced from local repository by HardCard"
                    )
                
                # Create upload session
                session = self.upload_manager.create_upload_session(
                    str(repo_dir), 
                    github_repo.full_name
                )
                session_ids.append(session.session_id)
                
                # Upload
                await self.upload_manager.parallel_upload(session)
        
        return session_ids

# CLI Interface
async def main():
    """Command-line interface for the upload manager"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="HardCard Smart GitHub Upload Manager - Never lose data to timeouts again!"
    )
    parser.add_argument('action', choices=['upload', 'resume', 'status', 'backup', 'analyze'],
                       help='Action to perform')
    parser.add_argument('--source', help='Source path to upload')
    parser.add_argument('--repo', help='GitHub repository name')
    parser.add_argument('--token', help='GitHub token (or set GITHUB_TOKEN env var)')
    parser.add_argument('--session', help='Session ID for resume/status')
    
    args = parser.parse_args()
    
    # Get GitHub token
    github_token = args.token or os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("Error: GitHub token required (--token or GITHUB_TOKEN env var)")
        sys.exit(1)
    
    # Initialize manager
    manager = SmartUploadManager(github_token)
    orchestrator = GitHubBackupOrchestrator(github_token)
    
    if args.action == 'analyze':
        if not args.source:
            print("Error: --source required for analyze")
            sys.exit(1)
        
        stats = manager.analyze_repository(args.source)
        print("\n📊 Repository Analysis:")
        print(f"Total files: {stats['total_files']}")
        print(f"Total size: {stats['total_size'] / (1024*1024):.2f} MB")
        print(f"Compressible: {stats['compressible_size'] / (1024*1024):.2f} MB")
        print(f"Binary files: {stats['binary_size'] / (1024*1024):.2f} MB")
        print(f"Large files: {len(stats['large_files'])}")
        
        if stats['recommendations']:
            print("\n💡 Recommendations:")
            for rec in stats['recommendations']:
                print(f"  • {rec}")
    
    elif args.action == 'upload':
        if not args.source or not args.repo:
            print("Error: --source and --repo required for upload")
            sys.exit(1)
        
        # Detect network speed
        print("🌐 Testing network speed...")
        manager.network_speed = manager.analyze_network_speed()
        print(f"Network speed: {manager.network_speed}")
        
        # Create session
        session = manager.create_upload_session(args.source, args.repo)
        print(f"\n📤 Upload session created: {session.session_id}")
        print(f"Total chunks: {len(session.chunks)}")
        print(f"Total size: {session.total_size / (1024*1024):.2f} MB")
        
        # Start upload
        await manager.parallel_upload(session)
        
        # Final status
        status = manager.get_session_status(session.session_id)
        print(f"\n✅ Upload completed!")
        print(f"Uploaded: {status['uploaded_chunks']}/{status['total_chunks']} chunks")
        print(f"Time elapsed: {status['elapsed_time']}")
    
    elif args.action == 'resume':
        if not args.session:
            print("Error: --session required for resume")
            sys.exit(1)
        
        success = await manager.resume_upload(args.session)
        if success:
            print("✅ Upload resumed and completed successfully!")
        else:
            print("⚠️ Upload resumed but not yet complete")
    
    elif args.action == 'status':
        if not args.session:
            print("Error: --session required for status")
            sys.exit(1)
        
        status = manager.get_session_status(args.session)
        
        if 'error' in status:
            print(f"Error: {status['error']}")
        else:
            print(f"\n📊 Upload Status for {status['session_id']}:")
            print(f"Repository: {status['repo_name']}")
            print(f"Progress: {status['progress_percentage']:.1f}%")
            print(f"Chunks: {status['uploaded_chunks']}/{status['total_chunks']}")
            print(f"Size: {status['uploaded_size_mb']:.2f}/{status['total_size_mb']:.2f} MB")
            print(f"Time elapsed: {status['elapsed_time']}")
            print(f"ETA: {status['eta']}")
            print(f"Status: {'✅ Complete' if status['completed'] else '⏳ In Progress'}")
    
    elif args.action == 'backup':
        session_id = await orchestrator.backup_desktop_to_github(args.source)
        print(f"✅ Desktop backup started with session ID: {session_id}")

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║     HardCard Smart GitHub Upload Manager                  ║
║     Never lose data to timeouts again!                    ║
║                                                            ║
║     • Intelligent chunking prevents timeouts              ║
║     • Automatic resume on failure                         ║
║     • Network-aware optimization                          ║
║     • Parallel uploads with rate limiting                 ║
║                                                            ║
║     Powered by HardCard.AI - Free for everyone            ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())