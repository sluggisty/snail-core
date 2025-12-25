"""
Data uploader module for Snail Core.

Handles secure transmission of collected data to a remote endpoint.
"""

from __future__ import annotations

import gzip
import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from snail_core.config import Config
    from snail_core.core import CollectionReport

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of an upload operation."""

    success: bool
    status_code: int | None = None
    response_data: dict[str, Any] | None = None
    error: str | None = None
    attempts: int = 1
    duration_ms: float = 0.0


class Uploader:
    """
    Handles uploading collection reports to a remote server.

    Supports:
    - HTTPS with custom certificates
    - API key authentication
    - Mutual TLS (client certificates)
    - Compression
    - Retries with exponential backoff
    """

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()

        # Configure authentication - use X-API-Key header
        if config.api_key:
            self.session.headers["X-API-Key"] = config.api_key

        # Configure client certificate if provided
        if config.auth_cert_path and config.auth_key_path:
            self.session.cert = (config.auth_cert_path, config.auth_key_path)

        # Set default headers
        self.session.headers.update(
            {
                "User-Agent": f"snail-core/{self._get_version()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def upload(
        self,
        report: CollectionReport,
        endpoint: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a collection report to the server.

        Args:
            report: The CollectionReport to upload.
            endpoint: Optional override for the upload endpoint.

        Returns:
            Server response data.

        Raises:
            UploadError: If upload fails after all retries.
        """
        url = endpoint or self.config.upload_url
        if not url:
            raise ValueError("No upload URL configured")

        # Prepare the data
        payload = report.to_dict()
        json_data = json.dumps(payload, default=str)

        # Compress if enabled
        if self.config.compress_output:
            data = gzip.compress(json_data.encode("utf-8"))
            headers = {"Content-Encoding": "gzip"}
        else:
            data = json_data.encode("utf-8")
            headers = {}

        # Upload with retries
        result = self._upload_with_retry(url, data, headers)

        if not result.success:
            raise UploadError(f"Upload failed after {result.attempts} attempts: {result.error}")

        return result.response_data or {}

    def _upload_with_retry(
        self,
        url: str,
        data: bytes,
        extra_headers: dict[str, str],
    ) -> UploadResult:
        """Upload with exponential backoff retry logic."""
        last_error = None

        for attempt in range(1, self.config.upload_retries + 1):
            start_time = time.perf_counter()

            try:
                response = self.session.post(
                    url,
                    data=data,
                    headers=extra_headers,
                    timeout=self.config.upload_timeout,
                )

                duration = (time.perf_counter() - start_time) * 1000

                if response.ok:
                    try:
                        response_data = response.json()
                    except ValueError:
                        response_data = {"status": "ok", "raw": response.text[:500]}

                    logger.info(
                        f"Upload successful in {duration:.0f}ms "
                        f"(attempt {attempt}/{self.config.upload_retries})"
                    )

                    return UploadResult(
                        success=True,
                        status_code=response.status_code,
                        response_data=response_data,
                        attempts=attempt,
                        duration_ms=duration,
                    )

                # Non-retryable status codes
                if response.status_code in (400, 401, 403, 404):
                    return UploadResult(
                        success=False,
                        status_code=response.status_code,
                        error=f"HTTP {response.status_code}: {response.text[:200]}",
                        attempts=attempt,
                        duration_ms=duration,
                    )

                # Retryable error
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(f"Upload attempt {attempt} failed: {last_error}")

            except requests.exceptions.Timeout:
                last_error = "Request timed out"
                logger.warning(f"Upload attempt {attempt} timed out")

            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e}"
                logger.warning(f"Upload attempt {attempt} connection error: {e}")

            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {e}"
                logger.warning(f"Upload attempt {attempt} error: {e}")

            # Exponential backoff before retry
            if attempt < self.config.upload_retries:
                backoff = min(2**attempt, 30)  # Max 30 seconds
                logger.debug(f"Retrying in {backoff} seconds...")
                time.sleep(backoff)

        return UploadResult(
            success=False,
            error=last_error,
            attempts=self.config.upload_retries,
        )

    def test_connection(self) -> bool:
        """
        Test connection to the upload server.

        Returns:
            True if server is reachable, False otherwise.
        """
        if not self.config.upload_url:
            return False

        try:
            # Try a HEAD or GET request to the base URL
            base_url = self.config.upload_url.rsplit("/", 1)[0]
            response = self.session.head(
                base_url,
                timeout=10,
                allow_redirects=True,
            )
            return bool(response.status_code < 500)
        except requests.exceptions.RequestException:
            return False

    def _get_version(self) -> str:
        """Get snail-core version."""
        try:
            from snail_core import __version__

            return __version__
        except ImportError:
            return "unknown"


class UploadError(Exception):
    """Raised when upload fails."""

    pass
