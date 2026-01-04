"""
Error handling tests for upload retry logic.

Tests that upload retry logic works correctly for different error scenarios.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest
import requests

from snail_core.config import Config
from snail_core.uploader import Uploader, UploadResult


@pytest.mark.integration
class TestUploadRetries(unittest.TestCase):
    """Test upload retry logic and exponential backoff."""

    def setUp(self):
        """Set up test configuration."""
        self.config = Config(
            upload_enabled=True,
            upload_url="https://test.example.com/api/upload",
            api_key="test-key-123",
            upload_retries=3,
            upload_timeout=5,
        )
        self.uploader = Uploader(self.config)

    def test_retry_on_500_errors(self):
        """Test that 500 errors trigger retries."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.ok = False

            return mock_response

        with patch.object(self.uploader.session, "post", side_effect=mock_post):
            result = self.uploader._upload_with_retry("https://test.example.com", b"{}", {})

            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 3)  # Should exhaust all retries
            self.assertEqual(call_count, 3)

    def test_retry_on_connection_errors(self):
        """Test that connection errors trigger retries."""

        def mock_post(*args, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused")

        with patch.object(self.uploader.session, "post", side_effect=mock_post):
            result = self.uploader._upload_with_retry("https://test.example.com", b"{}", {})

            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 3)
            self.assertIn("Connection error", result.error)

    def test_retry_on_timeout_errors(self):
        """Test that timeout errors trigger retries."""

        def mock_post(*args, **kwargs):
            raise requests.exceptions.Timeout("Request timed out")

        with patch.object(self.uploader.session, "post", side_effect=mock_post):
            result = self.uploader._upload_with_retry("https://test.example.com", b"{}", {})

            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 3)
            self.assertIn("Request timed out", result.error)

    def test_no_retry_on_400_errors(self):
        """Test that 400 errors do not trigger retries."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.ok = False

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            result = self.uploader._upload_with_retry("https://test.example.com", b"{}", {})

            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 1)  # Should not retry
            self.assertEqual(result.status_code, 400)

    def test_no_retry_on_401_errors(self):
        """Test that 401 errors do not trigger retries."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.ok = False

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            result = self.uploader._upload_with_retry("https://test.example.com", b"{}", {})

            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 1)
            self.assertEqual(result.status_code, 401)

    def test_no_retry_on_403_errors(self):
        """Test that 403 errors do not trigger retries."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.ok = False

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            result = self.uploader._upload_with_retry("https://test.example.com", b"{}", {})

            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 1)
            self.assertEqual(result.status_code, 403)

    def test_no_retry_on_404_errors(self):
        """Test that 404 errors do not trigger retries."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.ok = False

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            result = self.uploader._upload_with_retry("https://test.example.com", b"{}", {})

            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 1)
            self.assertEqual(result.status_code, 404)

    def test_exponential_backoff_timing(self):
        """Test that exponential backoff timing is correct."""
        sleep_calls = []

        def mock_sleep(seconds):
            sleep_calls.append(seconds)

        def mock_post(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.ok = False
            return mock_response

        with patch.object(self.uploader.session, "post", side_effect=mock_post):
            with patch("time.sleep", side_effect=mock_sleep):
                self.uploader._upload_with_retry("https://test.example.com", b"{}", {})

                # Should have slept 2 times (between attempts 1-2 and 2-3)
                self.assertEqual(len(sleep_calls), 2)

                # First backoff should be 2^1 = 2 seconds
                self.assertEqual(sleep_calls[0], 2)

                # Second backoff should be 2^2 = 4 seconds
                self.assertEqual(sleep_calls[1], 4)

    def test_maximum_retry_attempts(self):
        """Test that maximum retry attempts are respected."""
        config = Config(upload_retries=5)  # More retries
        uploader = Uploader(config)

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.ok = False
            return mock_response

        with patch.object(uploader.session, "post", side_effect=mock_post):
            result = uploader._upload_with_retry("https://test.example.com", b"{}", {})

            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 5)  # Should respect max retries
            self.assertEqual(call_count, 5)

    def test_backoff_not_exceed_maximum(self):
        """Test that backoff doesn't exceed maximum delay."""
        # Use many retries to test backoff capping
        config = Config(upload_retries=10)
        uploader = Uploader(config)

        sleep_calls = []

        def mock_sleep(seconds):
            sleep_calls.append(seconds)

        def mock_post(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.ok = False
            return mock_response

        with patch.object(uploader.session, "post", side_effect=mock_post):
            with patch("time.sleep", side_effect=mock_sleep):
                uploader._upload_with_retry("https://test.example.com", b"{}", {})

                # Check that no backoff exceeds 30 seconds (the max)
                for delay in sleep_calls:
                    self.assertLessEqual(delay, 30)

                # Should have 9 sleep calls (between 10 attempts)
                self.assertEqual(len(sleep_calls), 9)

    def test_successful_retry_after_failures(self):
        """Test successful upload after some failed attempts."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count <= 2:  # First 2 attempts fail
                raise requests.exceptions.ConnectionError("Connection refused")
            else:  # 3rd attempt succeeds
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.text = '{"status": "success"}'
                mock_response.ok = True
                mock_response.json.return_value = {"status": "success"}
                return mock_response

        with patch.object(self.uploader.session, "post", side_effect=mock_post):
            result = self.uploader._upload_with_retry("https://test.example.com", b"{}", {})

            self.assertTrue(result.success)
            self.assertEqual(result.attempts, 3)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(call_count, 3)

    def test_upload_result_structure(self):
        """Test that UploadResult has correct structure."""
        # Test successful result
        success_result = UploadResult(
            success=True,
            status_code=200,
            response_data={"status": "ok"},
            attempts=1,
            duration_ms=150.5,
        )

        self.assertTrue(success_result.success)
        self.assertEqual(success_result.status_code, 200)
        self.assertEqual(success_result.response_data, {"status": "ok"})
        self.assertEqual(success_result.attempts, 1)
        self.assertEqual(success_result.duration_ms, 150.5)
        self.assertIsNone(success_result.error)

        # Test failure result
        failure_result = UploadResult(
            success=False, error="Connection failed", attempts=3, duration_ms=2500.0
        )

        self.assertFalse(failure_result.success)
        self.assertIsNone(failure_result.status_code)
        self.assertIsNone(failure_result.response_data)
        self.assertEqual(failure_result.error, "Connection failed")
        self.assertEqual(failure_result.attempts, 3)
        self.assertEqual(failure_result.duration_ms, 2500.0)

    def test_json_parsing_error_handling(self):
        """Test handling of invalid JSON responses."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "not json response"
        mock_response.ok = True
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch.object(self.uploader.session, "post", return_value=mock_response):
            # Create a test report for upload
            from snail_core.core import CollectionReport

            test_report = CollectionReport(
                hostname="test",
                host_id="test-id",
                collection_id="test-collection",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
            )
            result = self.uploader.upload(test_report)

            # Should still succeed but with fallback response
            self.assertIsInstance(result, dict)
            self.assertIn("status", result)  # Should have fallback data
