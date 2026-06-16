"""Screenshot history management system.

This module provides functionality to store and manage screenshot history,
including automatic cleanup of old screenshots when the limit is exceeded.
"""

import json
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from .i18n import _
from .logger import setup_logger

logger = setup_logger("screenshot_history")


class ScreenshotHistory:
    """Manages screenshot history with automatic cleanup.

    Stores the last N screenshots with metadata in a local directory.
    Automatically cleans up old screenshots when the limit is exceeded.

    Storage structure:
        ~/.config/openSnipaste/history/
        ├── 20260527_143022.png
        ├── 20260527_143045.png
        └── history.json

    Metadata format (history.json):
        {
          "screenshots": [
            {
              "id": "20260527_143022",
              "filename": "20260527_143022.png",
              "timestamp": 1779860622,
              "width": 1920,
              "height": 1080,
              "has_annotations": true
            }
          ],
          "max_count": 100
        }
    """

    def __init__(self, history_dir: str | None = None):
        """Initialize history manager.

        Args:
            history_dir: Optional custom directory (for testing).
                        Default: Path.home() / ".config/openSnipaste/history"
        """
        if history_dir is None:
            self._history_dir = Path.home() / ".config" / "openSnipaste" / "history"
        else:
            self._history_dir = Path(history_dir)

        # Create directory if it doesn't exist
        self._history_dir.mkdir(parents=True, exist_ok=True)

        # Metadata file path
        self._metadata_path = self._history_dir / "history.json"

        # Thumbnail cache (in-memory)
        self._thumbnail_cache: dict[str, QPixmap] = {}

        # Load existing metadata or create new
        self._metadata = self._load_metadata()

        # Save metadata if it doesn't exist yet (create file on init)
        if not self._metadata_path.exists():
            self._save_metadata()

        logger.info(f"Screenshot history initialized: {self._history_dir}")

    @property
    def history_dir(self) -> Path:
        """Get the history directory path.

        Returns:
            Path: Directory where screenshots are stored.
        """
        return self._history_dir

    @property
    def max_count(self) -> int:
        """Get the maximum number of screenshots to keep.

        Returns:
            int: Maximum screenshot count.
        """
        return self._metadata.get("max_count", 100)

    def _load_metadata(self) -> dict:
        """Load metadata from history.json.

        Returns:
            dict: Metadata dictionary with screenshots list and max_count.
        """
        if self._metadata_path.exists():
            try:
                with open(self._metadata_path, encoding='utf-8') as f:
                    data = json.load(f)
                logger.debug(f"Loaded metadata with {len(data.get('screenshots', []))} screenshots")
                return data
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load metadata: {e}, creating new")

        # Return default metadata
        return {
            "screenshots": [],
            "max_count": 100
        }

    def _save_metadata(self) -> None:
        """Save metadata to history.json."""
        try:
            with open(self._metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self._metadata, f, indent=2, ensure_ascii=False)
            logger.debug("Metadata saved successfully")
        except OSError as e:
            logger.error(f"Failed to save metadata: {e}")

    def _generate_screenshot_id(self) -> str:
        """Generate unique screenshot ID in YYYYMMDD_HHMMSS_microseconds format.

        Always includes microseconds for true uniqueness across rapid calls.

        Returns:
            str: Unique screenshot ID.
        """
        timestamp = datetime.now()
        # Always include microseconds for true monotonic uniqueness
        screenshot_id = timestamp.strftime("%Y%m%d_%H%M%S_%f")

        # Get existing IDs from metadata to ensure absolute uniqueness
        screenshot_ids = {s["id"] for s in self._metadata["screenshots"]}

        # If somehow still not unique (extremely rare), add a counter
        counter = 0
        base_id = screenshot_id
        while screenshot_id in screenshot_ids:
            counter += 1
            screenshot_id = f"{base_id}_{counter}"

        return screenshot_id

    def _cleanup_old_screenshots(self) -> None:
        """Remove oldest screenshots when count exceeds max_count."""
        max_count = self._metadata.get("max_count", 100)
        screenshots = self._metadata["screenshots"]

        if len(screenshots) <= max_count:
            return

        # Sort by timestamp (oldest first)
        screenshots.sort(key=lambda x: x["timestamp"])

        # Calculate how many to remove
        to_remove = len(screenshots) - max_count

        # Remove oldest screenshots
        for i in range(to_remove):
            screenshot = screenshots[i]
            screenshot_id = screenshot["id"]
            screenshot_file = self._history_dir / screenshot["filename"]

            # Remove file
            try:
                if screenshot_file.exists():
                    screenshot_file.unlink()
                    logger.debug(f"Removed old screenshot: {screenshot_file}")
            except OSError as e:
                logger.error(f"Failed to remove screenshot file {screenshot_file}: {e}")

            # Remove from thumbnail cache (all sizes for this screenshot)
            keys_to_remove = [k for k in self._thumbnail_cache.keys() if k.startswith(screenshot_id)]
            for key in keys_to_remove:
                del self._thumbnail_cache[key]

        # Update metadata (keep only the newest max_count screenshots)
        self._metadata["screenshots"] = screenshots[to_remove:]
        logger.info(f"Cleaned up {to_remove} old screenshots")

    def _format_time_ago(self, timestamp: int) -> str:
        """Format timestamp as human-readable time.

        Args:
            timestamp: Unix timestamp in seconds.

        Returns:
            str: Human-readable time string (translated via i18n).
        """
        now = int(time.time())
        diff = now - timestamp

        if diff < 60:
            return _("Just now")
        elif diff < 3600:  # < 1 hour
            minutes = diff // 60
            return _("{minutes} minutes ago").format(minutes=minutes)
        elif diff < 86400:  # < 24 hours
            hours = diff // 3600
            return _("{hours} hours ago").format(hours=hours)
        else:
            days = diff // 86400
            return _("{days} days ago").format(days=days)

    def add_screenshot(self, pixmap: QPixmap, has_annotations: bool) -> str:
        """Add screenshot to history.

        Args:
            pixmap: QPixmap to save.
            has_annotations: Whether the screenshot has annotations.

        Returns:
            str: Screenshot ID.
        """
        # Generate unique ID
        screenshot_id = self._generate_screenshot_id()
        filename = f"{screenshot_id}.png"
        filepath = self._history_dir / filename

        # Save pixmap to file
        if not pixmap.save(str(filepath), "PNG"):
            logger.error(f"Failed to save screenshot: {filepath}")
            raise OSError(f"Failed to save screenshot: {filepath}")

        # Create metadata entry
        timestamp = int(time.time())
        metadata_entry = {
            "id": screenshot_id,
            "filename": filename,
            "timestamp": timestamp,
            "width": pixmap.width(),
            "height": pixmap.height(),
            "has_annotations": has_annotations
        }

        # Add to metadata
        self._metadata["screenshots"].append(metadata_entry)

        # Auto-cleanup if exceeds max_count
        self._cleanup_old_screenshots()

        # Save metadata to disk
        self._save_metadata()

        logger.info(f"Added screenshot: {screenshot_id} ({pixmap.width()}x{pixmap.height()})")
        return screenshot_id

    def get_recent(self, count: int = 10) -> list[dict]:
        """Get recent screenshots.

        Args:
            count: Number of screenshots to return (default: 10).

        Returns:
            list[dict]: List of metadata dicts (newest first).
                       Each dict contains: id, filename, timestamp, width, height,
                       has_annotations, and time_ago (computed field).
        """
        screenshots = self._metadata["screenshots"].copy()

        # Sort by timestamp (newest first), then by ID for stable ordering
        # when timestamps are equal (rapid screenshots in same second)
        screenshots.sort(key=lambda x: (x["timestamp"], x["id"]), reverse=True)

        # Limit to count
        screenshots = screenshots[:count]

        # Add time_ago field
        for screenshot in screenshots:
            screenshot["time_ago"] = self._format_time_ago(screenshot["timestamp"])

        return screenshots

    def get_thumbnail(self, screenshot_id: str, size: tuple[int, int] = (48, 36)) -> QPixmap | None:
        """Get thumbnail for screenshot.

        Args:
            screenshot_id: Screenshot ID.
            size: Thumbnail size as (width, height) tuple (default: 48x36).

        Returns:
            QPixmap: Thumbnail pixmap, or None if screenshot doesn't exist.
        """
        # Check cache first
        cache_key = f"{screenshot_id}_{size[0]}x{size[1]}"
        if cache_key in self._thumbnail_cache:
            return self._thumbnail_cache[cache_key]

        # Find screenshot metadata
        screenshot = None
        for s in self._metadata["screenshots"]:
            if s["id"] == screenshot_id:
                screenshot = s
                break

        if screenshot is None:
            logger.warning(f"Screenshot not found: {screenshot_id}")
            return None

        # Load screenshot file
        filepath = self._history_dir / screenshot["filename"]
        if not filepath.exists():
            logger.warning(f"Screenshot file not found: {filepath}")
            return None

        # Load and scale pixmap
        pixmap = QPixmap(str(filepath))
        if pixmap.isNull():
            logger.error(f"Failed to load screenshot: {filepath}")
            return None

        # Scale to requested size with smooth transformation
        thumbnail = pixmap.scaled(
            size[0], size[1],
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Cache the thumbnail
        self._thumbnail_cache[cache_key] = thumbnail

        logger.debug(f"Generated thumbnail for {screenshot_id}: {thumbnail.width()}x{thumbnail.height()}")
        return thumbnail

    def delete_screenshot(self, screenshot_id: str) -> bool:
        """Delete screenshot from history.

        Args:
            screenshot_id: Screenshot ID to delete.

        Returns:
            bool: True if deleted, False if not found.
        """
        # Find screenshot in metadata
        screenshot = None
        screenshot_index = -1

        for i, s in enumerate(self._metadata["screenshots"]):
            if s["id"] == screenshot_id:
                screenshot = s
                screenshot_index = i
                break

        if screenshot is None:
            logger.warning(f"Screenshot not found for deletion: {screenshot_id}")
            return False

        # Remove file
        filepath = self._history_dir / screenshot["filename"]
        try:
            if filepath.exists():
                filepath.unlink()
                logger.debug(f"Deleted screenshot file: {filepath}")
        except OSError as e:
            logger.error(f"Failed to delete screenshot file {filepath}: {e}")

        # Remove from metadata
        self._metadata["screenshots"].pop(screenshot_index)

        # Clear from thumbnail cache (all sizes)
        keys_to_remove = [k for k in self._thumbnail_cache.keys() if k.startswith(screenshot_id)]
        for key in keys_to_remove:
            del self._thumbnail_cache[key]

        # Save updated metadata
        self._save_metadata()

        logger.info(f"Deleted screenshot: {screenshot_id}")
        return True
