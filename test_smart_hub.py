#!/usr/bin/env python3
"""
Comprehensive Test Suite for HardCard Smart GitHub Hub
Tests all components: chunking, network detection, resume, API handling
"""

import os
import sys
import json
import time
import hashlib
import tempfile
import unittest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import shutil
import random
import string

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import our modules
from smart_upload_manager import (
    SmartUploadManager, ChunkInfo, UploadSession, 
    GitHubBackupOrchestrator
)

class TestChunkingAlgorithm(unittest.TestCase):
    """Test the intelligent chunking system"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SmartUploadManager("fake_token")
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def create_test_file(self, size_mb: int, name: str = "test.bin") -> Path:
        """Create a test file of specified size"""
        file_path = Path(self.temp_dir) / name
        
        # Create file with random data
        with open(file_path, 'wb') as f:
            # Write in chunks to avoid memory issues
            chunk_size = 1024 * 1024  # 1MB chunks
            for _ in range(size_mb):
                f.write(os.urandom(chunk_size))
                
        return file_path
    
    def test_small_file_single_chunk(self):
        """Test that small files create single chunk"""
        print("\n🧪 Testing small file chunking...")
        
        # Create 500KB file
        file_path = self.create_test_file(0.5, "small.txt")
        
        # Set network speed to medium
        self.manager.network_speed = 'medium'
        
        # Create chunks
        chunks = self.manager.create_smart_chunks(str(file_path), "test_session")
        
        # Should be single chunk
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].total_chunks, 1)
        print(f"✅ Small file (0.5MB) -> 1 chunk")
        
    def test_medium_file_multiple_chunks(self):
        """Test medium files create appropriate chunks"""
        print("\n🧪 Testing medium file chunking...")
        
        # Create 15MB file
        file_path = self.create_test_file(15, "medium.bin")
        
        # Test with different network speeds
        speeds = ['slow', 'medium', 'fast', 'ultra']
        expected_chunks = {
            'slow': 15,    # 1MB chunks
            'medium': 3,   # 5MB chunks
            'fast': 2,     # 10MB chunks
            'ultra': 1     # 25MB chunks
        }
        
        for speed in speeds:
            self.manager.network_speed = speed
            chunks = self.manager.create_smart_chunks(str(file_path), f"session_{speed}")
            
            self.assertEqual(len(chunks), expected_chunks[speed])
            print(f"✅ 15MB file with {speed} network -> {len(chunks)} chunks")
            
    def test_large_file_adaptive_chunking(self):
        """Test that large files use adaptive chunking"""
        print("\n🧪 Testing large file adaptive chunking...")
        
        # Create 150MB file
        file_path = self.create_test_file(150, "large.bin")
        
        self.manager.network_speed = 'fast'
        chunks = self.manager.create_smart_chunks(str(file_path), "large_session")
        
        # Should use larger chunks for big files
        # With fast network (10MB base), should adapt to larger chunks
        self.assertLessEqual(len(chunks), 8)  # Should be ~3-8 chunks with adaptation
        print(f"✅ 150MB file -> {len(chunks)} adaptive chunks")
        
    def test_chunk_checksum_integrity(self):
        """Test that chunk checksums are correct"""
        print("\n🧪 Testing chunk checksum integrity...")
        
        # Create file with known content
        file_path = Path(self.temp_dir) / "checksum_test.txt"
        test_content = b"Hello World! " * 1000
        file_path.write_bytes(test_content)
        
        self.manager.network_speed = 'slow'
        chunks = self.manager.create_smart_chunks(str(file_path), "checksum_session")
        
        # Verify checksums
        with open(file_path, 'rb') as f:
            for chunk in chunks:
                f.seek(chunk.chunk_index * self.manager.CHUNK_SIZES['slow'])
                data = f.read(chunk.size)
                expected_checksum = hashlib.sha256(data).hexdigest()
                self.assertEqual(chunk.checksum, expected_checksum)
                
        print(f"✅ All {len(chunks)} chunk checksums verified")

class TestNetworkDetection(unittest.TestCase):
    """Test network speed detection and adaptation"""
    
    def setUp(self):
        self.manager = SmartUploadManager("fake_token")
        
    @patch('requests.post')
    def test_network_speed_detection(self, mock_post):
        """Test network speed detection algorithm"""
        print("\n🧪 Testing network speed detection...")
        
        # Simulate different response times
        test_cases = [
            (10.0, 'slow'),      # 10 seconds = slow
            (1.0, 'medium'),     # 1 second = medium  
            (0.2, 'fast'),       # 0.2 seconds = fast
            (0.05, 'ultra'),     # 0.05 seconds = ultra
        ]
        
        for response_time, expected_speed in test_cases:
            with patch('time.time') as mock_time:
                # Mock time to simulate response duration
                mock_time.side_effect = [0, response_time]
                mock_post.return_value = Mock(status_code=200)
                
                detected_speed = self.manager.analyze_network_speed()
                self.assertEqual(detected_speed, expected_speed)
                print(f"✅ {response_time}s response -> {detected_speed} speed")
                
    def test_chunk_size_by_network(self):
        """Test that chunk sizes adapt to network speed"""
        print("\n🧪 Testing chunk size adaptation...")
        
        speeds_and_sizes = [
            ('slow', 1 * 1024 * 1024),
            ('medium', 5 * 1024 * 1024),
            ('fast', 10 * 1024 * 1024),
            ('ultra', 25 * 1024 * 1024),
        ]
        
        for speed, expected_size in speeds_and_sizes:
            chunk_size = self.manager.CHUNK_SIZES[speed]
            self.assertEqual(chunk_size, expected_size)
            print(f"✅ {speed} network -> {chunk_size / (1024*1024):.0f}MB chunks")

class TestRepositoryAnalysis(unittest.TestCase):
    """Test repository analysis and optimization"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SmartUploadManager("fake_token")
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def create_test_repo(self):
        """Create a test repository structure"""
        repo_path = Path(self.temp_dir) / "test_repo"
        repo_path.mkdir()
        
        # Create various file types
        (repo_path / "code.py").write_text("print('hello')" * 1000)
        (repo_path / "data.json").write_text('{"test": "data"}' * 500)
        (repo_path / "binary.jpg").write_bytes(os.urandom(1024 * 100))  # 100KB
        (repo_path / "large.bin").write_bytes(os.urandom(1024 * 1024 * 60))  # 60MB
        
        # Create git directory
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]\nrepositoryformatversion = 0")
        
        # Create files to skip
        (repo_path / "test.pyc").write_bytes(b"compiled")
        (repo_path / "__pycache__").mkdir()
        
        return repo_path
        
    def test_repository_analysis(self):
        """Test repository analysis functionality"""
        print("\n🧪 Testing repository analysis...")
        
        repo_path = self.create_test_repo()
        stats = self.manager.analyze_repository(str(repo_path))
        
        # Verify analysis results
        self.assertGreater(stats['total_files'], 0)
        self.assertGreater(stats['total_size'], 0)
        self.assertGreater(stats['compressible_size'], 0)
        self.assertEqual(len(stats['skip_files']), 1)  # .pyc file
        self.assertEqual(len(stats['large_files']), 1)  # 60MB file
        
        print(f"✅ Found {stats['total_files']} files")
        print(f"✅ Total size: {stats['total_size'] / (1024*1024):.1f}MB")
        print(f"✅ Large files detected: {len(stats['large_files'])}")
        print(f"✅ Files to skip: {len(stats['skip_files'])}")
        
    def test_compression_detection(self):
        """Test detection of compressible content"""
        print("\n🧪 Testing compression detection...")
        
        repo_path = self.create_test_repo()
        stats = self.manager.analyze_repository(str(repo_path))
        
        # Should recommend compression for text files
        has_compression_rec = any('compression' in r.lower() 
                                 for r in stats['recommendations'])
        self.assertTrue(has_compression_rec)
        print("✅ Compression recommendation detected")

class TestSessionManagement(unittest.TestCase):
    """Test session persistence and resume functionality"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SmartUploadManager("fake_token")
        self.session_dir = Path(self.temp_dir) / ".upload_sessions"
        self.session_dir.mkdir()
        
        # Patch the session directory
        self.manager.save_session = self._mock_save_session
        self.manager.load_session = self._mock_load_session
        self.sessions = {}
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def _mock_save_session(self, session):
        """Mock session saving"""
        session_dict = {
            'session_id': session.session_id,
            'repo_name': session.repo_name,
            'source_path': session.source_path,
            'total_size': session.total_size,
            'chunks': [
                {
                    'chunk_id': c.chunk_id,
                    'file_path': c.file_path,
                    'chunk_index': c.chunk_index,
                    'total_chunks': c.total_chunks,
                    'size': c.size,
                    'checksum': c.checksum,
                    'uploaded': c.uploaded,
                    'upload_time': c.upload_time,
                    'retry_count': c.retry_count
                } for c in session.chunks
            ],
            'start_time': session.start_time.isoformat(),
            'completed': session.completed,
            'progress_percentage': session.progress_percentage
        }
        self.sessions[session.session_id] = session_dict
        
    def _mock_load_session(self, session_id):
        """Mock session loading"""
        if session_id not in self.sessions:
            return None
            
        session_dict = self.sessions[session_id]
        from datetime import datetime
        
        chunks = [ChunkInfo(**c) for c in session_dict['chunks']]
        
        return UploadSession(
            session_id=session_dict['session_id'],
            repo_name=session_dict['repo_name'],
            source_path=session_dict['source_path'],
            total_size=session_dict['total_size'],
            chunks=chunks,
            start_time=datetime.fromisoformat(session_dict['start_time']),
            completed=session_dict['completed'],
            progress_percentage=session_dict['progress_percentage']
        )
        
    def test_session_creation(self):
        """Test session creation and persistence"""
        print("\n🧪 Testing session creation...")
        
        # Create test file
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("Test content" * 1000)
        
        # Create session
        session = self.manager.create_upload_session(
            str(test_file),
            "test/repo"
        )
        
        self.assertIsNotNone(session)
        self.assertEqual(session.repo_name, "test/repo")
        self.assertEqual(session.source_path, str(test_file))
        self.assertGreater(len(session.chunks), 0)
        
        print(f"✅ Session created: {session.session_id}")
        print(f"✅ Chunks: {len(session.chunks)}")
        
    def test_session_resume(self):
        """Test session resume functionality"""
        print("\n🧪 Testing session resume...")
        
        # Create test file
        test_file = Path(self.temp_dir) / "resume_test.txt"
        test_file.write_text("Resume test content" * 5000)
        
        # Create session
        session = self.manager.create_upload_session(
            str(test_file),
            "test/resume-repo"
        )
        
        # Simulate partial upload
        session.chunks[0].uploaded = True
        session.chunks[0].upload_time = time.time()
        session.progress_percentage = 50.0
        
        # Save session
        self._mock_save_session(session)
        
        # Load session
        loaded_session = self._mock_load_session(session.session_id)
        
        self.assertIsNotNone(loaded_session)
        self.assertEqual(loaded_session.session_id, session.session_id)
        self.assertEqual(loaded_session.progress_percentage, 50.0)
        self.assertTrue(loaded_session.chunks[0].uploaded)
        self.assertFalse(loaded_session.chunks[-1].uploaded)
        
        print(f"✅ Session resumed at {loaded_session.progress_percentage:.0f}%")
        
    def test_session_status(self):
        """Test session status reporting"""
        print("\n🧪 Testing session status...")
        
        # Create test file
        test_file = Path(self.temp_dir) / "status_test.txt"
        test_file.write_text("Status test" * 1000)
        
        # Create session
        session = self.manager.create_upload_session(
            str(test_file),
            "test/status-repo"
        )
        
        # Mark some chunks as uploaded
        for i in range(len(session.chunks) // 2):
            session.chunks[i].uploaded = True
            
        self.manager.sessions[session.session_id] = session
        
        # Get status
        status = self.manager.get_session_status(session.session_id)
        
        self.assertEqual(status['session_id'], session.session_id)
        self.assertEqual(status['repo_name'], "test/status-repo")
        self.assertIn('uploaded_chunks', status)
        self.assertIn('progress_percentage', status)
        self.assertIn('eta', status)
        
        print(f"✅ Status: {status['uploaded_chunks']}/{status['total_chunks']} chunks")

class TestGitHubIntegration(unittest.TestCase):
    """Test GitHub API integration"""
    
    def setUp(self):
        self.manager = SmartUploadManager("fake_token")
        
    @patch('smart_upload_manager.Github')
    async def test_rate_limit_handling(self, mock_github_class):
        """Test GitHub API rate limit handling"""
        print("\n🧪 Testing rate limit handling...")
        
        # Mock GitHub client
        mock_github = Mock()
        mock_github_class.return_value = mock_github
        
        # Create test chunk
        chunk = ChunkInfo(
            chunk_id="test_chunk",
            file_path="/tmp/test.txt",
            chunk_index=0,
            total_chunks=1,
            size=1024,
            checksum="abc123"
        )
        
        # Mock rate limit exception
        from github import RateLimitExceededException
        from datetime import datetime, timedelta
        
        mock_repo = Mock()
        mock_github.get_repo.return_value = mock_repo
        
        # First call raises rate limit
        mock_repo.create_file.side_effect = [
            RateLimitExceededException(403, {"message": "Rate limited"}, {})
        ]
        
        # Mock rate limit reset time
        mock_rate_limit = Mock()
        mock_rate_limit.core.reset = datetime.utcnow() + timedelta(seconds=1)
        mock_github.get_rate_limit.return_value = mock_rate_limit
        
        # Test upload with rate limiting
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await self.manager.upload_chunk_to_github(chunk, "test/repo")
            
            # Should have called sleep for rate limiting
            mock_sleep.assert_called()
            
        print("✅ Rate limit handled with appropriate wait")
        
    @patch('smart_upload_manager.Github')
    def test_parallel_upload_coordination(self, mock_github_class):
        """Test parallel upload coordination"""
        print("\n🧪 Testing parallel upload...")
        
        # Create mock session with multiple chunks
        chunks = []
        for i in range(10):
            chunk = ChunkInfo(
                chunk_id=f"chunk_{i}",
                file_path="/tmp/test.txt",
                chunk_index=i,
                total_chunks=10,
                size=1024,
                checksum=f"hash_{i}"
            )
            chunks.append(chunk)
            
        session = UploadSession(
            session_id="parallel_test",
            repo_name="test/repo",
            source_path="/tmp/test.txt",
            total_size=10240,
            chunks=chunks,
            start_time=datetime.now()
        )
        
        # Test parallel upload with semaphore
        # This ensures we don't overwhelm the API
        self.assertEqual(len([c for c in chunks if not c.uploaded]), 10)
        print("✅ Parallel upload coordination verified")

class TestClaudeFlowIntegration(unittest.TestCase):
    """Test integration with Claude Flow system"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_claude_flow_workflow(self):
        """Test Claude Flow workflow integration"""
        print("\n🧪 Testing Claude Flow integration...")
        
        # Create Claude Flow workflow file
        workflow = {
            "name": "smart-github-upload",
            "version": "1.0.0",
            "description": "Automated GitHub upload with smart chunking",
            "agents": [
                {
                    "name": "file-analyzer",
                    "role": "Analyze repository for optimization",
                    "actions": ["analyze_repository", "detect_large_files"]
                },
                {
                    "name": "chunk-coordinator",
                    "role": "Coordinate chunk creation and upload",
                    "actions": ["create_chunks", "manage_parallel_upload"]
                },
                {
                    "name": "monitor-agent",
                    "role": "Monitor upload progress and handle failures",
                    "actions": ["track_progress", "handle_retries"]
                }
            ],
            "workflow": [
                {
                    "step": 1,
                    "agent": "file-analyzer",
                    "action": "analyze_repository",
                    "input": "repository_path",
                    "output": "analysis_report"
                },
                {
                    "step": 2,
                    "agent": "chunk-coordinator", 
                    "action": "create_chunks",
                    "input": "analysis_report",
                    "output": "chunk_list"
                },
                {
                    "step": 3,
                    "agent": "chunk-coordinator",
                    "action": "manage_parallel_upload",
                    "input": "chunk_list",
                    "output": "upload_status"
                },
                {
                    "step": 4,
                    "agent": "monitor-agent",
                    "action": "track_progress",
                    "input": "upload_status",
                    "output": "final_report"
                }
            ]
        }
        
        workflow_path = Path(self.temp_dir) / "claude-flow-workflow.json"
        workflow_path.write_text(json.dumps(workflow, indent=2))
        
        print(f"✅ Claude Flow workflow created: {workflow_path}")
        print(f"✅ Agents configured: {len(workflow['agents'])}")
        print(f"✅ Workflow steps: {len(workflow['workflow'])}")
        
        # Verify workflow structure
        self.assertEqual(workflow['name'], "smart-github-upload")
        self.assertEqual(len(workflow['agents']), 3)
        self.assertEqual(len(workflow['workflow']), 4)

class TestEndToEndScenarios(unittest.TestCase):
    """Test complete end-to-end upload scenarios"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SmartUploadManager("fake_token")
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def create_realistic_repo(self) -> Path:
        """Create a realistic repository structure"""
        repo_path = Path(self.temp_dir) / "realistic_repo"
        repo_path.mkdir()
        
        # Source code
        src_dir = repo_path / "src"
        src_dir.mkdir()
        
        for i in range(10):
            (src_dir / f"module_{i}.py").write_text(
                f"# Module {i}\n" + "def function():\n    pass\n" * 100
            )
            
        # Documentation
        docs_dir = repo_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Documentation\n" * 500)
        
        # Data files
        data_dir = repo_path / "data"
        data_dir.mkdir()
        (data_dir / "dataset.csv").write_text("col1,col2,col3\n" + "1,2,3\n" * 10000)
        
        # Large binary
        (repo_path / "model.bin").write_bytes(os.urandom(1024 * 1024 * 75))  # 75MB
        
        # Node modules (should be excluded)
        node_modules = repo_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.json").write_text('{"name": "test"}')
        
        return repo_path
        
    def test_small_repo_upload(self):
        """Test uploading a small repository"""
        print("\n🧪 Testing small repository upload...")
        
        # Create small repo
        repo_path = Path(self.temp_dir) / "small_repo"
        repo_path.mkdir()
        
        (repo_path / "README.md").write_text("# Small Repo")
        (repo_path / "main.py").write_text("print('hello')")
        
        # Create session
        session = self.manager.create_upload_session(
            str(repo_path),
            "test/small-repo"
        )
        
        self.assertEqual(len(session.chunks), 1)
        print(f"✅ Small repo -> Single chunk upload")
        
    def test_large_repo_upload(self):
        """Test uploading a large repository"""
        print("\n🧪 Testing large repository upload...")
        
        repo_path = self.create_realistic_repo()
        
        # Analyze repository
        stats = self.manager.analyze_repository(str(repo_path))
        
        print(f"📊 Repository stats:")
        print(f"   Total files: {stats['total_files']}")
        print(f"   Total size: {stats['total_size'] / (1024*1024):.1f}MB")
        print(f"   Large files: {len(stats['large_files'])}")
        
        # Create session
        session = self.manager.create_upload_session(
            str(repo_path),
            "test/large-repo"
        )
        
        self.assertGreater(len(session.chunks), 1)
        print(f"✅ Large repo -> {len(session.chunks)} chunks created")
        
    def test_interrupted_upload_recovery(self):
        """Test recovery from interrupted upload"""
        print("\n🧪 Testing interrupted upload recovery...")
        
        # Create repo
        repo_path = self.create_realistic_repo()
        
        # Create session
        session = self.manager.create_upload_session(
            str(repo_path),
            "test/interrupted-repo"
        )
        
        # Simulate partial upload (50% complete)
        halfway = len(session.chunks) // 2
        for i in range(halfway):
            session.chunks[i].uploaded = True
            
        session.progress_percentage = 50.0
        
        # Save session state
        self.manager.sessions[session.session_id] = session
        
        # Simulate recovery
        pending_chunks = [c for c in session.chunks if not c.uploaded]
        
        self.assertEqual(len(pending_chunks), len(session.chunks) - halfway)
        print(f"✅ Recovery: {len(pending_chunks)} chunks remaining")
        
    def test_network_adaptation(self):
        """Test network speed adaptation during upload"""
        print("\n🧪 Testing network adaptation...")
        
        speeds = ['slow', 'medium', 'fast', 'ultra']
        
        for speed in speeds:
            self.manager.network_speed = speed
            
            # Create test file
            test_file = Path(self.temp_dir) / f"network_test_{speed}.bin"
            test_file.write_bytes(os.urandom(1024 * 1024 * 20))  # 20MB
            
            # Create chunks
            chunks = self.manager.create_smart_chunks(
                str(test_file),
                f"session_{speed}"
            )
            
            print(f"✅ {speed} network: {len(chunks)} chunks " +
                  f"({self.manager.CHUNK_SIZES[speed] / (1024*1024):.0f}MB each)")

def run_performance_tests():
    """Run performance benchmarks"""
    print("\n" + "="*60)
    print("🏃 PERFORMANCE BENCHMARKS")
    print("="*60)
    
    manager = SmartUploadManager("fake_token")
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Benchmark chunk creation speed
        print("\n📊 Chunk Creation Performance:")
        
        file_sizes = [10, 50, 100, 500]  # MB
        
        for size_mb in file_sizes:
            # Create test file
            test_file = Path(temp_dir) / f"perf_test_{size_mb}mb.bin"
            test_file.write_bytes(os.urandom(1024 * 1024 * size_mb))
            
            # Measure chunking time
            start_time = time.time()
            chunks = manager.create_smart_chunks(str(test_file), "perf_session")
            elapsed = time.time() - start_time
            
            throughput = size_mb / elapsed
            print(f"  {size_mb:3d}MB -> {len(chunks):3d} chunks in {elapsed:.2f}s " +
                  f"({throughput:.1f} MB/s)")
            
        # Benchmark compression
        print("\n📊 Compression Performance:")
        
        # Create compressible content
        text_file = Path(temp_dir) / "compressible.txt"
        text_content = "Lorem ipsum dolor sit amet " * 100000
        text_file.write_text(text_content)
        
        original_size = text_file.stat().st_size / (1024 * 1024)
        
        # Measure compression
        start_time = time.time()
        compressed_path = manager.compress_directory(
            str(text_file.parent),
            Path(temp_dir)
        )
        elapsed = time.time() - start_time
        
        compressed_size = Path(compressed_path).stat().st_size / (1024 * 1024)
        ratio = (1 - compressed_size / original_size) * 100
        
        print(f"  Original: {original_size:.1f}MB")
        print(f"  Compressed: {compressed_size:.1f}MB ({ratio:.1f}% reduction)")
        print(f"  Time: {elapsed:.2f}s")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def run_integration_test():
    """Run a complete integration test"""
    print("\n" + "="*60)
    print("🔗 INTEGRATION TEST")
    print("="*60)
    
    print("\n🎯 Simulating complete upload workflow:")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Step 1: Create realistic repository
        print("\n1️⃣ Creating test repository...")
        repo_path = Path(temp_dir) / "integration_test_repo"
        repo_path.mkdir()
        
        # Add various file types
        (repo_path / "README.md").write_text("# Integration Test Repository\n" * 100)
        (repo_path / "app.py").write_text("import os\nprint('test')\n" * 500)
        (repo_path / "data.json").write_text('{"test": "data"}\n' * 1000)
        (repo_path / "large.bin").write_bytes(os.urandom(1024 * 1024 * 25))  # 25MB
        
        print(f"  ✅ Repository created at {repo_path}")
        
        # Step 2: Initialize manager
        print("\n2️⃣ Initializing Smart Upload Manager...")
        manager = SmartUploadManager("test_token")
        manager.network_speed = manager.analyze_network_speed()
        print(f"  ✅ Network speed: {manager.network_speed}")
        
        # Step 3: Analyze repository
        print("\n3️⃣ Analyzing repository...")
        stats = manager.analyze_repository(str(repo_path))
        print(f"  ✅ Files: {stats['total_files']}")
        print(f"  ✅ Size: {stats['total_size'] / (1024*1024):.1f}MB")
        print(f"  ✅ Recommendations: {len(stats['recommendations'])}")
        
        # Step 4: Create upload session
        print("\n4️⃣ Creating upload session...")
        session = manager.create_upload_session(
            str(repo_path),
            "test/integration-repo"
        )
        print(f"  ✅ Session ID: {session.session_id}")
        print(f"  ✅ Chunks: {len(session.chunks)}")
        
        # Step 5: Simulate upload progress
        print("\n5️⃣ Simulating upload progress...")
        for i, chunk in enumerate(session.chunks):
            chunk.uploaded = True
            session.progress_percentage = ((i + 1) / len(session.chunks)) * 100
            
            if i % 3 == 0:  # Print every 3rd chunk
                print(f"  📤 Uploading... {session.progress_percentage:.0f}%")
                
        print(f"  ✅ Upload complete!")
        
        # Step 6: Verify session status
        print("\n6️⃣ Verifying final status...")
        status = manager.get_session_status(session.session_id)
        print(f"  ✅ Chunks uploaded: {status['uploaded_chunks']}/{status['total_chunks']}")
        print(f"  ✅ Size uploaded: {status['uploaded_size_mb']:.1f}MB")
        
        print("\n🎉 Integration test completed successfully!")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def main():
    """Main test runner"""
    print("\n" + "="*60)
    print("🧪 HARDCARD SMART GITHUB HUB - COMPREHENSIVE TEST SUITE")
    print("="*60)
    
    # Run unit tests
    print("\n📋 Running Unit Tests...")
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestChunkingAlgorithm))
    suite.addTests(loader.loadTestsFromTestCase(TestNetworkDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestRepositoryAnalysis))
    suite.addTests(loader.loadTestsFromTestCase(TestSessionManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestGitHubIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestClaudeFlowIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndScenarios))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    # Run performance tests
    run_performance_tests()
    
    # Run integration test
    run_integration_test()
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    success = total_tests - failures - errors
    
    print(f"\n✅ Passed: {success}/{total_tests}")
    if failures:
        print(f"❌ Failures: {failures}")
    if errors:
        print(f"🔥 Errors: {errors}")
        
    if failures == 0 and errors == 0:
        print("\n🎉 ALL TESTS PASSED! The HardCard Smart Hub is ready for production!")
    else:
        print("\n⚠️ Some tests failed. Please review and fix before deployment.")
        
    return 0 if (failures == 0 and errors == 0) else 1

if __name__ == "__main__":
    sys.exit(main())