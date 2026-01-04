"""
Integration tests for upload functionality with mock HTTP server.

Tests end-to-end upload flow: collection -> report generation -> upload -> verification.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest


@pytest.mark.integration

from snail_core.config import Config
from snail_core.core import SnailCore
from snail_core.uploader import Uploader


class MockUploadServer(BaseHTTPRequestHandler):
    """Mock HTTP server for testing uploads."""

    def __init__(self, *args, **kwargs):
        self.requests = []
        super().__init__(*args, **kwargs)

    def do_POST(self):
        """Handle POST requests."""
        # Read request data
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            post_data = self.rfile.read(content_length)
        else:
            post_data = b''

        # Store request for verification
        request_info = {
            'method': 'POST',
            'path': self.path,
            'headers': dict(self.headers),
            'data': post_data,
        }
        self.server.requests.append(request_info)

        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        response_data = {'status': 'uploaded', 'id': 'test-upload-123'}
        self.wfile.write(json.dumps(response_data).encode())

    def log_message(self, format, *args):
        """Suppress server log messages."""
        pass


class TestUploadIntegration(unittest.TestCase):
    """Integration tests for upload functionality."""

    def setUp(self):
        """Set up test environment with mock server."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Start mock server on a random available port
        self.server = HTTPServer(('localhost', 0), MockUploadServer)
        self.server.requests = []  # Store requests for verification
        self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        # Get the actual port the server is listening on
        self.server_port = self.server.server_address[1]
        self.base_url = f'http://localhost:{self.server_port}'

    def tearDown(self):
        """Clean up test environment."""
        self.server.shutdown()
        self.server.server_close()

        # Clean up temp files
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        self.temp_dir.rmdir()

    def test_end_to_end_upload_successful(self):
        """Test successful end-to-end upload flow."""
        config = Config(
            upload_url=f'{self.base_url}/api/upload',
            upload_enabled=True,
            api_key='test-key-123',
            output_dir=str(self.temp_dir),
        )

        # Mock host_id and hostname for consistent test data
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                # Create SnailCore and run collection
                core = SnailCore(config)

                # Mock collectors for fast testing
                from snail_core.collectors.base import BaseCollector
                mock_collectors = {}
                collector_names = ["system", "hardware"]
                for name in collector_names:
                    mock_collectors[name] = self._create_mock_collector(BaseCollector, name)

                with patch("snail_core.core.get_all_collectors", return_value=mock_collectors):
                    report = core.collect(collector_names=collector_names)

                # Verify collection worked
                self.assertEqual(len(report.results), 2)
                self.assertIn("system", report.results)
                self.assertIn("hardware", report.results)

                # Upload the report
                result = core.upload(report)

                # Verify upload result
                self.assertIsInstance(result, dict)
                self.assertEqual(result['status'], 'uploaded')
                self.assertEqual(result['id'], 'test-upload-123')

                # Verify server received the request
                self.assertEqual(len(self.server.requests), 1)
                request = self.server.requests[0]

                self.assertEqual(request['method'], 'POST')
                self.assertEqual(request['path'], '/api/upload')

                # Verify headers
                headers = request['headers']
                self.assertEqual(headers['Content-Type'], 'application/json')
                self.assertEqual(headers['X-API-Key'], 'test-key-123')
                self.assertIn('User-Agent', headers)
                self.assertIn('snail-core/', headers['User-Agent'])

                # Verify payload structure
                import json
                import gzip

                data = request['data']

                # Check if data is compressed
                if request['headers'].get('Content-Encoding') == 'gzip':
                    data = gzip.decompress(data)

                payload = json.loads(data.decode())

                # Should have meta and data sections
                self.assertIn('meta', payload)
                self.assertIn('data', payload)
                self.assertIn('errors', payload)

                # Verify meta data
                meta = payload['meta']
                self.assertEqual(meta['hostname'], 'test-host')
                self.assertEqual(meta['host_id'], 'test-host-id-123')
                self.assertIn('collection_id', meta)
                self.assertIn('timestamp', meta)
                self.assertIn('snail_version', meta)

                # Verify data contains collector results
                data = payload['data']
                self.assertIn('system', data)
                self.assertIn('hardware', data)

    def test_upload_with_compression(self):
        """Test upload with compression enabled."""
        config = Config(
            upload_url=f'{self.base_url}/api/upload',
            upload_enabled=True,
            compress_output=True,
            api_key='test-key-456',
            output_dir=str(self.temp_dir),
        )

        uploader = Uploader(config)

        # Create a test report
        from snail_core.core import CollectionReport
        report = CollectionReport(
            hostname="test-host",
            host_id="test-host-id-123",
            collection_id="test-collection-456",
            timestamp="2024-01-01T00:00:00Z",
            snail_version="1.0.0",
            results={"test": {"data": "value"}},
        )

        # Upload with compression
        result = uploader.upload(report)

        # Verify upload succeeded
        self.assertEqual(result['status'], 'uploaded')

        # Verify server received compressed data
        self.assertEqual(len(self.server.requests), 1)
        request = self.server.requests[0]

        headers = request['headers']
        self.assertEqual(headers['Content-Encoding'], 'gzip')

        # Verify data is compressed (gzip)
        import gzip
        compressed_data = request['data']
        decompressed = gzip.decompress(compressed_data).decode()
        payload = json.loads(decompressed)

        self.assertIn('meta', payload)
        self.assertIn('data', payload)

    def test_upload_with_authentication(self):
        """Test upload with API key authentication."""
        config = Config(
            upload_url=f'{self.base_url}/api/upload',
            upload_enabled=True,
            api_key='secret-api-key-789',
            output_dir=str(self.temp_dir),
        )

        uploader = Uploader(config)

        # Create a test report
        from snail_core.core import CollectionReport
        report = CollectionReport(
            hostname="test-host",
            host_id="test-host-id-123",
            collection_id="test-collection-789",
            timestamp="2024-01-01T00:00:00Z",
            snail_version="1.0.0",
            results={"test": {"data": "value"}},
        )

        # Upload
        result = uploader.upload(report)

        # Verify upload succeeded
        self.assertEqual(result['status'], 'uploaded')

        # Verify API key was sent
        self.assertEqual(len(self.server.requests), 1)
        request = self.server.requests[0]

        headers = request['headers']
        self.assertEqual(headers['X-API-Key'], 'secret-api-key-789')

    def test_upload_failure_handling(self):
        """Test upload failure handling."""
        # Configure server to return error
        original_do_POST = MockUploadServer.do_POST

        def error_do_POST(self):
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {'error': 'Internal server error'}
            self.wfile.write(json.dumps(error_response).encode())
            self.server.requests.append({
                'method': 'POST',
                'path': self.path,
                'headers': dict(self.headers),
                'data': self.rfile.read(int(self.headers.get('Content-Length', 0))),
            })

        MockUploadServer.do_POST = error_do_POST

        try:
            config = Config(
                upload_url=f'{self.base_url}/api/upload',
                upload_enabled=True,
                upload_retries=2,  # Allow retries
                output_dir=str(self.temp_dir),
            )

            uploader = Uploader(config)

            # Create a test report
            from snail_core.core import CollectionReport
            report = CollectionReport(
                hostname="test-host",
                host_id="test-host-id-123",
                collection_id="test-collection-fail",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
                results={"test": {"data": "value"}},
            )

            # Upload should fail after retries
            with self.assertRaises(Exception) as context:
                uploader.upload(report)

            # Should mention upload failure
            self.assertIn("Upload failed", str(context.exception))

            # Should have made multiple attempts (upload_retries = total attempts)
            self.assertEqual(len(self.server.requests), 2)  # upload_retries=2 means 2 total attempts

        finally:
            # Restore original method
            MockUploadServer.do_POST = original_do_POST

    def test_upload_retry_on_transient_errors(self):
        """Test upload retry on transient errors."""
        # Track call count
        call_count = [0]

        original_do_POST = MockUploadServer.do_POST

        def retry_do_POST(self):
            call_count[0] += 1

            # Fail first two attempts, succeed on third
            if call_count[0] <= 2:
                self.send_response(503)  # Service Unavailable (retryable)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {'error': 'Service temporarily unavailable'}
                self.wfile.write(json.dumps(error_response).encode())
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                success_response = {'status': 'uploaded', 'id': 'retry-success-123'}
                self.wfile.write(json.dumps(success_response).encode())

            self.server.requests.append({
                'method': 'POST',
                'path': self.path,
                'headers': dict(self.headers),
                'data': self.rfile.read(int(self.headers.get('Content-Length', 0))),
            })

        MockUploadServer.do_POST = retry_do_POST

        try:
            config = Config(
                upload_url=f'{self.base_url}/api/upload',
                upload_enabled=True,
                upload_retries=3,  # Allow enough retries
                output_dir=str(self.temp_dir),
            )

            uploader = Uploader(config)

            # Create a test report
            from snail_core.core import CollectionReport
            report = CollectionReport(
                hostname="test-host",
                host_id="test-host-id-123",
                collection_id="test-collection-retry",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
                results={"test": {"data": "value"}},
            )

            # Upload should succeed after retries
            result = uploader.upload(report)

            self.assertEqual(result['status'], 'uploaded')
            self.assertEqual(result['id'], 'retry-success-123')

            # Should have made 3 attempts (initial + 2 retries)
            self.assertEqual(len(self.server.requests), 3)

        finally:
            # Restore original method
            MockUploadServer.do_POST = original_do_POST

    def _create_mock_collector(self, collector_cls, name):
        """Create a mock collector class that returns test data."""
        class MockCollector(collector_cls):
            def collect(self):
                return {
                    "collector": name,
                    "status": "success",
                    "test_data": f"data_from_{name}",
                    "timestamp": "2024-01-01T00:00:00Z",
                }
        return MockCollector
