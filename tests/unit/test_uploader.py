"""
Unit tests for Uploader class.

Tests upload functionality, retry logic, authentication, and compression.
"""

from __future__ import annotations

import gzip
import json
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import requests

from snail_core.config import Config
from snail_core.core import CollectionReport
from snail_core.uploader import Uploader, UploadResult


class TestUploadResult(unittest.TestCase):
    """Test UploadResult dataclass."""

    def test_upload_result_creation(self):
        """Test UploadResult creation with all fields."""
        result = UploadResult(
            success=True,
            status_code=200,
            response_data={"status": "ok"},
            error=None,
            attempts=1,
            duration_ms=150.5,
        )

        assert result.success is True
        assert result.status_code == 200
        assert result.response_data == {"status": "ok"}
        assert result.error is None
        assert result.attempts == 1
        assert result.duration_ms == 150.5

    def test_upload_result_defaults(self):
        """Test UploadResult with default values."""
        result = UploadResult(success=False)
        assert result.success is False
        assert result.status_code is None
        assert result.response_data is None
        assert result.error is None
        assert result.attempts == 1
        assert result.duration_ms == 0.0


class TestUploaderInitialization(unittest.TestCase):
    """Test Uploader class initialization."""

    def test_init_with_api_key(self):
        """Test initialization with API key sets X-API-Key header."""
        config = Config(api_key="test-key-123", upload_url="https://test.com/api")
        uploader = Uploader(config)

        assert "X-API-Key" in uploader.session.headers
        assert uploader.session.headers["X-API-Key"] == "test-key-123"

    def test_init_without_api_key(self):
        """Test initialization without API key doesn't set header."""
        config = Config(api_key=None, upload_url="https://test.com/api")
        uploader = Uploader(config)

        assert "X-API-Key" not in uploader.session.headers

    def test_init_with_client_cert(self):
        """Test initialization with client certificate."""
        config = Config(
            upload_url="https://test.com/api",
            auth_cert_path="/path/to/cert.pem",
            auth_key_path="/path/to/key.pem",
        )
        uploader = Uploader(config)

        assert uploader.session.cert == ("/path/to/cert.pem", "/path/to/key.pem")

    def test_init_without_client_cert(self):
        """Test initialization without client certificate."""
        config = Config(upload_url="https://test.com/api")
        uploader = Uploader(config)

        assert uploader.session.cert is None

    def test_init_default_headers(self):
        """Test that default headers are set correctly."""
        config = Config(upload_url="https://test.com/api")
        uploader = Uploader(config)

        assert "User-Agent" in uploader.session.headers
        assert "snail-core/" in uploader.session.headers["User-Agent"]
        assert uploader.session.headers["Content-Type"] == "application/json"
        assert uploader.session.headers["Accept"] == "application/json"

    def test_get_version(self):
        """Test version detection."""
        config = Config(upload_url="https://test.com/api")
        uploader = Uploader(config)

        version = uploader._get_version()
        assert isinstance(version, str)
        assert len(version) > 0


class TestUploaderUpload(unittest.TestCase):
    """Test Uploader.upload() method."""

    def create_test_report(self):
        """Create a test CollectionReport."""
        return CollectionReport(
            hostname="test-host",
            host_id="test-host-id",
            collection_id=str(uuid4()),
            timestamp="2024-01-01T00:00:00Z",
            snail_version="1.0.0",
            results={"test": {"data": "value"}},
        )

    def test_upload_successful(self):
        """Test successful upload."""
        config = Config(upload_url="https://test.com/api", api_key="test-key")
        uploader = Uploader(config)
        report = self.create_test_report()

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "uploaded", "id": "123"}

        with patch.object(uploader.session, "post", return_value=mock_response):
            result = uploader.upload(report)

        assert result == {"status": "uploaded", "id": "123"}

    def test_upload_with_compression(self):
        """Test upload with compression enabled."""
        config = Config(
            upload_url="https://test.com/api",
            api_key="test-key",
            compress_output=True,
        )
        uploader = Uploader(config)
        report = self.create_test_report()

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "compressed"}

        with patch.object(uploader.session, "post") as mock_post:
            mock_post.return_value = mock_response
            uploader.upload(report)

            # Verify post was called with compressed data
            call_args = mock_post.call_args
            data = call_args[1]["data"]

            # Data should be compressed (gzip)
            assert isinstance(data, bytes)
            # Verify it's valid gzip by decompressing
            decompressed = gzip.decompress(data)
            json_data = json.loads(decompressed.decode())
            assert "meta" in json_data
            assert "data" in json_data

            # Verify compression header was set
            headers = call_args[1]["headers"]
            assert headers["Content-Encoding"] == "gzip"

    def test_upload_without_compression(self):
        """Test upload with compression disabled."""
        config = Config(
            upload_url="https://test.com/api",
            api_key="test-key",
            compress_output=False,
        )
        uploader = Uploader(config)
        report = self.create_test_report()

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "uncompressed"}

        with patch.object(uploader.session, "post") as mock_post:
            mock_post.return_value = mock_response
            uploader.upload(report)

            # Verify post was called with uncompressed JSON string
            call_args = mock_post.call_args
            data = call_args[1]["data"]

            # Data should be JSON string, not bytes
            assert isinstance(data, bytes)
            json_str = data.decode()
            json_data = json.loads(json_str)
            assert "meta" in json_data

            # Verify no compression header
            headers = call_args[1]["headers"]
            assert "Content-Encoding" not in headers

    def test_upload_custom_endpoint(self):
        """Test upload with custom endpoint override."""
        config = Config(upload_url="https://default.com/api", api_key="test-key")
        uploader = Uploader(config)
        report = self.create_test_report()

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "custom"}

        with patch.object(uploader.session, "post") as mock_post:
            mock_post.return_value = mock_response
            uploader.upload(report, endpoint="https://custom.com/upload")

            # Verify the custom endpoint was used
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://custom.com/upload"

    def test_upload_missing_url_raises(self):
        """Test upload without URL raises ValueError."""
        config = Config(upload_url=None)
        uploader = Uploader(config)
        report = self.create_test_report()

        with self.assertRaises(ValueError) as context:
            uploader.upload(report)
        self.assertIn("No upload URL configured", str(context.exception))

    def test_upload_payload_structure(self):
        """Test that upload payload has correct structure."""
        config = Config(upload_url="https://test.com/api", api_key="test-key")
        uploader = Uploader(config)
        report = self.create_test_report()

        with patch.object(uploader.session, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {}
            mock_post.return_value = mock_response

            uploader.upload(report)

            # Check the payload structure
            call_args = mock_post.call_args
            data = call_args[1]["data"]

            if config.compress_output:
                # Decompress if compressed
                data = gzip.decompress(data)
                json_str = data.decode()
            else:
                json_str = data.decode()

            payload = json.loads(json_str)

            # Verify payload structure
            assert "meta" in payload
            assert "data" in payload
            assert "errors" in payload

            # Verify meta contains required fields
            meta = payload["meta"]
            assert "hostname" in meta
            assert "host_id" in meta
            assert "collection_id" in meta
            assert "timestamp" in meta
            assert "snail_version" in meta


class TestUploaderRetryLogic(unittest.TestCase):
    """Test Uploader retry logic."""

    def create_test_report(self):
        """Create a test CollectionReport."""
        return CollectionReport(
            hostname="test-host",
            host_id="test-host-id",
            collection_id=str(uuid4()),
            timestamp="2024-01-01T00:00:00Z",
            snail_version="1.0.0",
            results={"test": {"data": "value"}},
        )

    def test_retry_on_500_error(self):
        """Test retry on 500 server error."""
        config = Config(upload_url="https://test.com/api", upload_retries=2)
        uploader = Uploader(config)
        report = self.create_test_report()

        # First call returns 500, second call succeeds
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                response = MagicMock()
                response.ok = False
                response.status_code = 500
                response.text = "Internal Server Error"
                return response
            else:
                response = MagicMock()
                response.ok = True
                response.status_code = 200
                response.json.return_value = {"status": "ok"}
                return response

        with patch.object(uploader.session, "post", side_effect=mock_post):
            result = uploader.upload(report)

        assert result == {"status": "ok"}
        assert call_count == 2  # Should have retried once

    def test_no_retry_on_400_error(self):
        """Test no retry on 400 client error."""
        config = Config(upload_url="https://test.com/api", upload_retries=3)
        uploader = Uploader(config)
        report = self.create_test_report()

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.ok = False
            response.status_code = 400
            response.text = "Bad Request"
            return response

        with patch.object(uploader.session, "post", side_effect=mock_post):
            with self.assertRaises(Exception):  # UploadError from upload method
                uploader.upload(report)

        self.assertEqual(call_count, 1)  # Should not retry

    def test_retry_on_connection_error(self):
        """Test retry on connection error."""
        config = Config(upload_url="https://test.com/api", upload_retries=2)
        uploader = Uploader(config)
        report = self.create_test_report()

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise requests.exceptions.ConnectionError("Connection failed")
            else:
                response = MagicMock()
                response.ok = True
                response.status_code = 200
                response.json.return_value = {"status": "ok"}
                return response

        with patch.object(uploader.session, "post", side_effect=mock_post):
            result = uploader.upload(report)

        assert result == {"status": "ok"}
        assert call_count == 2  # Should have retried

    def test_retry_on_timeout(self):
        """Test retry on timeout."""
        config = Config(upload_url="https://test.com/api", upload_retries=2)
        uploader = Uploader(config)
        report = self.create_test_report()

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise requests.exceptions.Timeout("Request timed out")
            else:
                response = MagicMock()
                response.ok = True
                response.status_code = 200
                response.json.return_value = {"status": "ok"}
                return response

        with patch.object(uploader.session, "post", side_effect=mock_post):
            result = uploader.upload(report)

        assert result == {"status": "ok"}
        assert call_count == 2  # Should have retried

    def test_max_retries_exceeded(self):
        """Test that max retries are respected."""
        config = Config(upload_url="https://test.com/api", upload_retries=2)
        uploader = Uploader(config)
        report = self.create_test_report()

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise requests.exceptions.ConnectionError("Connection failed")

        with patch.object(uploader.session, "post", side_effect=mock_post):
            with self.assertRaises(Exception):  # UploadError
                uploader.upload(report)

        self.assertEqual(call_count, 2)  # upload_retries = total attempts

    def test_exponential_backoff(self):
        """Test that exponential backoff is implemented."""
        config = Config(
            upload_url="https://test.com/api", upload_retries=3
        )  # Need 3 attempts to succeed on 3rd
        uploader = Uploader(config)
        report = self.create_test_report()

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first two attempts, succeed on third
                raise requests.exceptions.ConnectionError("Connection failed")
            else:
                response = MagicMock()
                response.ok = True
                response.status_code = 200
                response.json.return_value = {"status": "ok"}
                return response

        with patch.object(uploader.session, "post", side_effect=mock_post):
            with patch("time.sleep") as mock_sleep:
                result = uploader.upload(report)

                # Should have succeeded after retries
                self.assertEqual(result, {"status": "ok"})
                # Should have slept for backoff periods (2 sleeps: between attempt 1-2 and 2-3)
                self.assertEqual(mock_sleep.call_count, 2)


class TestUploaderConnectionTest(unittest.TestCase):
    """Test Uploader.test_connection() method."""

    def test_connection_test_successful(self):
        """Test successful connection test."""
        config = Config(upload_url="https://test.com/api/v1/upload")
        uploader = Uploader(config)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(uploader.session, "head", return_value=mock_response):
            result = uploader.test_connection()
            assert result is True

    def test_connection_test_server_error(self):
        """Test connection test with server error."""
        config = Config(upload_url="https://test.com/api/v1/upload")
        uploader = Uploader(config)

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(uploader.session, "head", return_value=mock_response):
            result = uploader.test_connection()
            assert result is False

    def test_connection_test_connection_error(self):
        """Test connection test with connection error."""
        config = Config(upload_url="https://test.com/api/v1/upload")
        uploader = Uploader(config)

        with patch.object(
            uploader.session,
            "head",
            side_effect=requests.exceptions.ConnectionError(),
        ):
            result = uploader.test_connection()
            assert result is False

    def test_connection_test_missing_url(self):
        """Test connection test without upload URL."""
        config = Config(upload_url=None)
        uploader = Uploader(config)

        result = uploader.test_connection()
        assert result is False

    def test_connection_test_url_parsing(self):
        """Test that connection test uses correct base URL."""
        config = Config(upload_url="https://test.com/api/v1/upload")
        uploader = Uploader(config)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(uploader.session, "head") as mock_head:
            mock_head.return_value = mock_response
            result = uploader.test_connection()

            # Should use base URL (without /upload path)
            call_args = mock_head.call_args
            called_url = call_args[0][0]
            assert "api/v1" in called_url
            assert "/upload" not in called_url
            assert result is True
