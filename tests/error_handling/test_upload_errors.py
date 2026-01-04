"""
Error handling tests for upload failures and error scenarios.

Tests that upload operations handle various failure scenarios gracefully.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

import pytest

from snail_core.config import Config
from snail_core.core import CollectionReport, SnailCore
from snail_core.uploader import Uploader, UploadError


@pytest.mark.integration
class TestUploadErrors(unittest.TestCase):
    """Test upload error handling scenarios."""

    def setUp(self):
        """Set up test configuration."""
        self.config = Config(
            upload_enabled=True,
            upload_url="https://test.example.com/api/upload",
            api_key="test-key-123",
            upload_retries=3,
            upload_timeout=5,
            compress_output=False,
        )
        self.uploader = Uploader(self.config)

        # Create a mock report
        self.report = CollectionReport(
            hostname="test-host",
            host_id="test-host-id",
            collection_id="test-collection-id",
            timestamp="2024-01-01T00:00:00Z",
            snail_version="1.0.0",
        )

    def test_network_connection_error(self):
        """Test handling of network connection errors."""
        with patch.object(
            self.uploader.session,
            "post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with self.assertRaises(UploadError) as cm:
                self.uploader.upload(self.report)

            error_msg = str(cm.exception)
            self.assertIn("Upload failed after", error_msg)
            self.assertIn("Connection error", error_msg)

    def test_timeout_error(self):
        """Test handling of request timeout errors."""
        with patch.object(
            self.uploader.session,
            "post",
            side_effect=requests.exceptions.Timeout("Request timed out"),
        ):
            with self.assertRaises(UploadError) as cm:
                self.uploader.upload(self.report)

            error_msg = str(cm.exception)
            self.assertIn("Upload failed after", error_msg)
            self.assertIn("Request timed out", error_msg)

    def test_authentication_failure_401(self):
        """Test handling of 401 Unauthorized errors."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.ok = False

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            with self.assertRaises(UploadError) as cm:
                self.uploader.upload(self.report)

            error_msg = str(cm.exception)
            self.assertIn("Upload failed after 1 attempts", error_msg)
            self.assertIn("HTTP 401", error_msg)

    def test_authentication_failure_403(self):
        """Test handling of 403 Forbidden errors."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.ok = False

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            with self.assertRaises(UploadError) as cm:
                self.uploader.upload(self.report)

            error_msg = str(cm.exception)
            self.assertIn("Upload failed after 1 attempts", error_msg)
            self.assertIn("HTTP 403", error_msg)

    def test_server_error_500(self):
        """Test handling of 500 Internal Server Error (retryable)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.ok = False

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            with self.assertRaises(UploadError) as cm:
                self.uploader.upload(self.report)

            error_msg = str(cm.exception)
            self.assertIn("Upload failed after 3 attempts", error_msg)  # Should retry 3 times
            self.assertIn("HTTP 500", error_msg)

    def test_server_error_502(self):
        """Test handling of 502 Bad Gateway (retryable)."""
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.text = "Bad Gateway"
        mock_response.ok = False

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            with self.assertRaises(UploadError) as cm:
                self.uploader.upload(self.report)

            error_msg = str(cm.exception)
            self.assertIn("Upload failed after 3 attempts", error_msg)
            self.assertIn("HTTP 502", error_msg)

    def test_bad_request_400_no_retry(self):
        """Test handling of 400 Bad Request (non-retryable)."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.ok = False

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            with self.assertRaises(UploadError) as cm:
                self.uploader.upload(self.report)

            error_msg = str(cm.exception)
            self.assertIn("Upload failed after 1 attempts", error_msg)  # No retry
            self.assertIn("HTTP 400", error_msg)

    def test_not_found_404_no_retry(self):
        """Test handling of 404 Not Found (non-retryable)."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.ok = False

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            with self.assertRaises(UploadError) as cm:
                self.uploader.upload(self.report)

            error_msg = str(cm.exception)
            self.assertIn("Upload failed after 1 attempts", error_msg)  # No retry
            self.assertIn("HTTP 404", error_msg)

    def test_ssl_tls_error(self):
        """Test handling of SSL/TLS certificate errors."""
        with patch.object(
            self.uploader.session,
            "post",
            side_effect=requests.exceptions.SSLError("SSL: CERTIFICATE_VERIFY_FAILED"),
        ):
            with self.assertRaises(UploadError) as cm:
                self.uploader.upload(self.report)

            error_msg = str(cm.exception)
            self.assertIn("Upload failed after", error_msg)
            self.assertIn("SSL", error_msg)

    def test_invalid_url_error(self):
        """Test handling of invalid URL errors."""
        uploader = Uploader(Config(upload_url="not-a-valid-url", api_key="test"))

        with self.assertRaises(UploadError):
            uploader.upload(self.report)

    def test_missing_upload_url(self):
        """Test handling when no upload URL is configured."""
        uploader = Uploader(Config(api_key="test"))

        with self.assertRaises(ValueError) as cm:
            uploader.upload(self.report)

        self.assertIn("No upload URL configured", str(cm.exception))

    def test_request_exception_handling(self):
        """Test handling of general request exceptions."""
        with patch.object(
            self.uploader.session,
            "post",
            side_effect=requests.exceptions.RequestException("Network is unreachable"),
        ):
            with self.assertRaises(UploadError) as cm:
                self.uploader.upload(self.report)

            error_msg = str(cm.exception)
            self.assertIn("Upload failed after", error_msg)
            self.assertIn("Request error", error_msg)

    def test_successful_upload_after_retries(self):
        """Test successful upload after some retries."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            mock_response = MagicMock()
            if call_count < 3:  # Fail first 2 attempts
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"
                mock_response.ok = False
            else:  # Succeed on 3rd attempt
                mock_response.status_code = 200
                mock_response.text = '{"status": "ok"}'
                mock_response.ok = True
                mock_response.json.return_value = {"status": "ok"}

            return mock_response

        with patch.object(self.uploader.session, "post", side_effect=mock_post):
            result = self.uploader.upload(self.report)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(call_count, 3)  # Should have made 3 attempts

    def test_upload_with_compression(self):
        """Test upload with compression enabled."""
        config = Config(
            upload_enabled=True,
            upload_url="https://test.example.com/api/upload",
            api_key="test-key-123",
            compress_output=True,
        )
        uploader = Uploader(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_response.ok = True
        mock_response.json.return_value = {"status": "ok"}

        with patch.object(uploader.session, "post", return_value=mock_response) as mock_post:
            result = uploader.upload(self.report)

            # Check that compression headers were sent
            call_args = mock_post.call_args
            headers = call_args[1]["headers"]
            self.assertEqual(headers.get("Content-Encoding"), "gzip")

            self.assertEqual(result["status"], "ok")

    def test_snailcore_upload_error_handling(self):
        """Test that SnailCore handles upload errors gracefully."""
        core = SnailCore(self.config)

        # Mock successful collection
        with patch.object(core, "collect", return_value=self.report):
            # Mock uploader to fail
            with patch.object(core, "uploader") as mock_uploader:
                mock_uploader.upload.side_effect = UploadError(
                    "Upload failed after 3 attempts: Connection error"
                )

                report, upload_response = core.collect_and_upload()

                # Report should contain the upload error
                self.assertTrue(len(report.errors) > 0)
                error_found = any("Upload failed" in error for error in report.errors)
                self.assertTrue(error_found)

                # Upload response should be None
                self.assertIsNone(upload_response)
