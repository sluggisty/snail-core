"""
Core orchestration module for Snail Core.

Handles discovery, execution, and aggregation of collectors.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from snail_core.auth import ensure_api_key
from snail_core.collectors import get_all_collectors
from snail_core.config import Config
from snail_core.host_id import get_host_id
from snail_core.uploader import Uploader

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    """Result of a single collector run."""

    collector_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class CollectionReport:
    """Complete collection report from all collectors."""

    hostname: str
    host_id: str
    collection_id: str
    timestamp: str
    snail_version: str
    results: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "meta": {
                "hostname": self.hostname,
                "host_id": self.host_id,
                "collection_id": self.collection_id,
                "timestamp": self.timestamp,
                "snail_version": self.snail_version,
            },
            "data": self.results,
            "errors": self.errors,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


class SnailCore:
    """
    Main orchestrator for system data collection.

    Discovers and runs collectors, aggregates results, and handles upload.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.collectors = get_all_collectors()
        # Try to ensure API key is available if upload URL is configured
        # Check both config.upload_url and SNAIL_UPLOAD_URL env var
        upload_url = self.config.upload_url or os.environ.get("SNAIL_UPLOAD_URL")
        if upload_url and not self.config.api_key:
            if not ensure_api_key(self.config, upload_url):
                logger.warning(
                    "Failed to obtain API key. Upload may fail. "
                    "Set SNAIL_USERNAME and SNAIL_PASSWORD, or SNAIL_API_KEY directly."
                )
        self.uploader = Uploader(self.config) if self.config.upload_url else None

    def collect(self, collector_names: list[str] | None = None) -> CollectionReport:
        """
        Run collection on specified or all collectors.

        Args:
            collector_names: Optional list of specific collectors to run.
                           If None, runs all available collectors.

        Returns:
            CollectionReport with all collected data.
        """
        import socket
        import time
        import uuid

        from snail_core import __version__

        # Get persistent host ID (or generate if first run)
        host_id = get_host_id(self.config.output_dir)

        # Generate a unique collection ID for this specific collection run
        collection_id = str(uuid.uuid4())

        report = CollectionReport(
            hostname=socket.gethostname(),
            host_id=host_id,
            collection_id=collection_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            snail_version=__version__,
        )

        # Filter collectors if specific names provided
        collectors_to_run = self.collectors
        if collector_names:
            collectors_to_run = {
                name: cls for name, cls in self.collectors.items() if name in collector_names
            }

        logger.info(f"Running {len(collectors_to_run)} collectors")

        for name, collector_cls in collectors_to_run.items():
            start = time.perf_counter()
            try:
                collector = collector_cls()
                data = collector.collect()
                duration = (time.perf_counter() - start) * 1000

                report.results[name] = data
                logger.debug(f"Collector '{name}' completed in {duration:.2f}ms")

            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                error_msg = f"Collector '{name}' failed: {e}"
                report.errors.append(error_msg)
                logger.error(error_msg)

        return report

    def upload(self, report: CollectionReport) -> dict[str, Any]:
        """
        Upload collection report to configured endpoint.

        Args:
            report: The collection report to upload.

        Returns:
            Response data from the server.

        Raises:
            ValueError: If no upload URL is configured.
        """
        if not self.uploader:
            raise ValueError("No upload URL configured. Set 'upload_url' in config.")

        return self.uploader.upload(report)

    def collect_and_upload(
        self, collector_names: list[str] | None = None
    ) -> tuple[CollectionReport, dict[str, Any] | None]:
        """
        Convenience method to collect and upload in one call.

        Returns:
            Tuple of (report, upload_response). upload_response is None
            if upload is disabled or fails.
        """
        report = self.collect(collector_names)

        upload_response = None
        if self.uploader and self.config.upload_enabled:
            # Double-check API key is available before upload
            if not self.config.api_key:
                upload_url = self.config.upload_url or os.environ.get("SNAIL_UPLOAD_URL")
                if upload_url:
                    if ensure_api_key(self.config, upload_url):
                        # Recreate uploader with new API key
                        self.uploader = Uploader(self.config)
                    else:
                        logger.error("No API key available and unable to obtain one")
            try:
                upload_response = self.upload(report)
            except Exception as e:
                logger.error(f"Upload failed: {e}")
                report.errors.append(f"Upload failed: {e}")

        return report, upload_response


def run_collection(
    config: Config | None = None,
    collector_names: list[str] | None = None,
    upload: bool = True,
) -> CollectionReport:
    """
    Convenience function to run a collection.

    Args:
        config: Optional configuration. Uses defaults if not provided.
        collector_names: Optional list of specific collectors to run.
        upload: Whether to upload results (if configured).

    Returns:
        The collection report.
    """
    core = SnailCore(config)

    if upload and core.uploader:
        report, _ = core.collect_and_upload(collector_names)
    else:
        report = core.collect(collector_names)

    return report
