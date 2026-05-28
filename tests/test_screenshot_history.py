import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QApplication

from src.core.screenshot_history import ScreenshotHistory


@pytest.fixture
def temp_history_dir():
    """Create temporary history directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def qapp():
    """Qt application fixture."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_pixmap(qapp):
    """Create a sample pixmap for testing."""
    pixmap = QPixmap(100, 100)
    pixmap.fill(QColor(255, 0, 0))
    return pixmap


class TestHistoryInit:
    def test_creates_directory_if_not_exists(self, temp_history_dir):
        """Test that initialization creates the history directory."""
        history_dir = temp_history_dir / "new_history"
        assert not history_dir.exists()

        history = ScreenshotHistory(history_dir=str(history_dir))

        assert history_dir.exists()
        assert history_dir.is_dir()

    def test_creates_metadata_file(self, temp_history_dir):
        """Test that initialization creates history.json metadata file."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))

        metadata_file = temp_history_dir / "history.json"
        assert metadata_file.exists()

        with open(metadata_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert "screenshots" in data
        assert "max_count" in data
        assert data["screenshots"] == []
        assert data["max_count"] == 100

    def test_loads_existing_metadata(self, temp_history_dir):
        """Test that initialization loads existing metadata."""
        metadata_file = temp_history_dir / "history.json"
        existing_data = {
            "screenshots": [
                {
                    "id": "20260527_143022",
                    "filename": "20260527_143022.png",
                    "timestamp": 1779860622,
                    "width": 1920,
                    "height": 1080,
                    "has_annotations": True
                }
            ],
            "max_count": 100
        }

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f)

        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        recent = history.get_recent(count=10)

        assert len(recent) == 1
        assert recent[0]["id"] == "20260527_143022"


class TestAddScreenshot:
    def test_adds_screenshot_to_history(self, temp_history_dir, sample_pixmap):
        """Test that add_screenshot saves the screenshot and metadata."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))

        screenshot_id = history.add_screenshot(sample_pixmap, has_annotations=False)

        assert screenshot_id is not None
        assert len(screenshot_id) > 0

        # Check file was created
        screenshot_file = temp_history_dir / f"{screenshot_id}.png"
        assert screenshot_file.exists()

        # Check metadata was updated
        recent = history.get_recent(count=1)
        assert len(recent) == 1
        assert recent[0]["id"] == screenshot_id
        assert recent[0]["width"] == 100
        assert recent[0]["height"] == 100
        assert recent[0]["has_annotations"] is False

    def test_generates_unique_filenames(self, temp_history_dir, sample_pixmap):
        """Test that multiple screenshots get unique IDs."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))

        id1 = history.add_screenshot(sample_pixmap, has_annotations=False)
        time.sleep(0.01)  # Small delay to ensure different timestamps
        id2 = history.add_screenshot(sample_pixmap, has_annotations=True)

        assert id1 != id2
        assert (temp_history_dir / f"{id1}.png").exists()
        assert (temp_history_dir / f"{id2}.png").exists()

    def test_saves_metadata_to_disk(self, temp_history_dir, sample_pixmap):
        """Test that metadata is persisted to disk."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        screenshot_id = history.add_screenshot(sample_pixmap, has_annotations=True)

        # Load metadata directly from file
        metadata_file = temp_history_dir / "history.json"
        with open(metadata_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert len(data["screenshots"]) == 1
        assert data["screenshots"][0]["id"] == screenshot_id
        assert data["screenshots"][0]["has_annotations"] is True


class TestAutoCleanup:
    def test_cleanup_when_exceeds_max_count(self, temp_history_dir, sample_pixmap):
        """Test that old screenshots are deleted when exceeding max_count."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        history._metadata["max_count"] = 5  # Set low limit for testing

        screenshot_ids = []
        for i in range(7):
            screenshot_id = history.add_screenshot(sample_pixmap, has_annotations=False)
            screenshot_ids.append(screenshot_id)
            time.sleep(0.01)  # Ensure different timestamps

        # Should only have the 5 most recent
        recent = history.get_recent(count=10)
        assert len(recent) == 5

        # Oldest 2 should be deleted
        assert not (temp_history_dir / f"{screenshot_ids[0]}.png").exists()
        assert not (temp_history_dir / f"{screenshot_ids[1]}.png").exists()

        # Newest 5 should exist
        for i in range(2, 7):
            assert (temp_history_dir / f"{screenshot_ids[i]}.png").exists()


class TestGetRecent:
    def test_returns_correct_count(self, temp_history_dir, sample_pixmap):
        """Test that get_recent returns the requested number of screenshots."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))

        for _ in range(5):
            history.add_screenshot(sample_pixmap, has_annotations=False)
            time.sleep(0.01)

        recent = history.get_recent(count=3)
        assert len(recent) == 3

    def test_returns_newest_first(self, temp_history_dir, sample_pixmap):
        """Test that screenshots are returned in reverse chronological order."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))

        ids = []
        for _ in range(3):
            screenshot_id = history.add_screenshot(sample_pixmap, has_annotations=False)
            ids.append(screenshot_id)
            time.sleep(0.01)

        recent = history.get_recent(count=10)

        # Most recent should be first
        assert recent[0]["id"] == ids[-1]
        assert recent[1]["id"] == ids[-2]
        assert recent[2]["id"] == ids[-3]

    def test_includes_time_ago_field(self, temp_history_dir, sample_pixmap):
        """Test that each screenshot includes a time_ago field."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        history.add_screenshot(sample_pixmap, has_annotations=False)

        recent = history.get_recent(count=1)
        assert "time_ago" in recent[0]
        assert isinstance(recent[0]["time_ago"], str)

    def test_includes_all_metadata_fields(self, temp_history_dir, sample_pixmap):
        """Test that all required fields are present in returned data."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        history.add_screenshot(sample_pixmap, has_annotations=True)

        recent = history.get_recent(count=1)
        screenshot = recent[0]

        assert "id" in screenshot
        assert "filename" in screenshot
        assert "timestamp" in screenshot
        assert "width" in screenshot
        assert "height" in screenshot
        assert "has_annotations" in screenshot
        assert "time_ago" in screenshot


class TestGetThumbnail:
    def test_returns_thumbnail_for_existing_screenshot(self, temp_history_dir, sample_pixmap):
        """Test that get_thumbnail returns a thumbnail pixmap."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        screenshot_id = history.add_screenshot(sample_pixmap, has_annotations=False)

        thumbnail = history.get_thumbnail(screenshot_id, size=(48, 36))

        assert thumbnail is not None
        assert not thumbnail.isNull()
        assert thumbnail.width() <= 48
        assert thumbnail.height() <= 36

    def test_returns_none_for_nonexistent_screenshot(self, temp_history_dir):
        """Test that get_thumbnail returns None for non-existent ID."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))

        thumbnail = history.get_thumbnail("nonexistent_id")

        assert thumbnail is None

    def test_caches_thumbnails(self, temp_history_dir, sample_pixmap):
        """Test that thumbnails are cached in memory."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        screenshot_id = history.add_screenshot(sample_pixmap, has_annotations=False)

        # First call should cache the thumbnail
        thumbnail1 = history.get_thumbnail(screenshot_id, size=(48, 36))
        cache_key = f"{screenshot_id}_48x36"
        assert cache_key in history._thumbnail_cache

        # Second call should return cached version
        thumbnail2 = history.get_thumbnail(screenshot_id, size=(48, 36))
        assert thumbnail1 is not None
        assert thumbnail2 is not None

    def test_uses_smooth_transformation(self, temp_history_dir, sample_pixmap):
        """Test that thumbnail scaling maintains quality."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        screenshot_id = history.add_screenshot(sample_pixmap, has_annotations=False)

        thumbnail = history.get_thumbnail(screenshot_id, size=(24, 18))

        assert thumbnail is not None
        # Thumbnail should be smaller than original
        assert thumbnail.width() < sample_pixmap.width()
        assert thumbnail.height() < sample_pixmap.height()


class TestDeleteScreenshot:
    def test_deletes_existing_screenshot(self, temp_history_dir, sample_pixmap):
        """Test that delete_screenshot removes the file and metadata."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        screenshot_id = history.add_screenshot(sample_pixmap, has_annotations=False)

        # Verify it exists
        screenshot_file = temp_history_dir / f"{screenshot_id}.png"
        assert screenshot_file.exists()

        # Delete it
        result = history.delete_screenshot(screenshot_id)

        assert result is True
        assert not screenshot_file.exists()

        # Verify metadata was updated
        recent = history.get_recent(count=10)
        assert len(recent) == 0

    def test_returns_false_for_nonexistent_screenshot(self, temp_history_dir):
        """Test that deleting non-existent screenshot returns False."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))

        result = history.delete_screenshot("nonexistent_id")

        assert result is False

    def test_clears_thumbnail_cache(self, temp_history_dir, sample_pixmap):
        """Test that deleting a screenshot removes it from thumbnail cache."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        screenshot_id = history.add_screenshot(sample_pixmap, has_annotations=False)

        # Load thumbnail to cache it
        history.get_thumbnail(screenshot_id, size=(48, 36))
        cache_key = f"{screenshot_id}_48x36"
        assert cache_key in history._thumbnail_cache

        # Delete screenshot
        history.delete_screenshot(screenshot_id)

        # Verify it's removed from cache (check that no keys start with screenshot_id)
        remaining_keys = [k for k in history._thumbnail_cache.keys() if k.startswith(screenshot_id)]
        assert len(remaining_keys) == 0

    def test_saves_updated_metadata(self, temp_history_dir, sample_pixmap):
        """Test that deletion persists metadata changes to disk."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        id1 = history.add_screenshot(sample_pixmap, has_annotations=False)
        id2 = history.add_screenshot(sample_pixmap, has_annotations=True)

        history.delete_screenshot(id1)

        # Load metadata directly from file
        metadata_file = temp_history_dir / "history.json"
        with open(metadata_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert len(data["screenshots"]) == 1
        assert data["screenshots"][0]["id"] == id2


class TestMetadataPersistence:
    def test_metadata_survives_reload(self, temp_history_dir, sample_pixmap):
        """Test that metadata persists across ScreenshotHistory instances."""
        # Create first instance and add screenshots
        history1 = ScreenshotHistory(history_dir=str(temp_history_dir))
        id1 = history1.add_screenshot(sample_pixmap, has_annotations=False)
        id2 = history1.add_screenshot(sample_pixmap, has_annotations=True)

        # Create second instance and verify data is loaded
        history2 = ScreenshotHistory(history_dir=str(temp_history_dir))
        recent = history2.get_recent(count=10)

        assert len(recent) == 2
        assert {r["id"] for r in recent} == {id1, id2}


class TestTimeAgoFormatting:
    def test_format_just_now(self, temp_history_dir, sample_pixmap):
        """Test time ago formatting for < 1 minute."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))
        history.add_screenshot(sample_pixmap, has_annotations=False)

        recent = history.get_recent(count=1)
        assert recent[0]["time_ago"] == "刚才"

    def test_format_minutes_ago(self, temp_history_dir):
        """Test time ago formatting for minutes."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))

        # Manually create metadata with timestamp 5 minutes ago
        current_time = int(time.time())
        five_minutes_ago = current_time - (5 * 60)

        history._metadata["screenshots"].append({
            "id": "test_id",
            "filename": "test.png",
            "timestamp": five_minutes_ago,
            "width": 100,
            "height": 100,
            "has_annotations": False
        })

        recent = history.get_recent(count=1)
        assert recent[0]["time_ago"] == "5分钟前"

    def test_format_hours_ago(self, temp_history_dir):
        """Test time ago formatting for hours."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))

        current_time = int(time.time())
        three_hours_ago = current_time - (3 * 60 * 60)

        history._metadata["screenshots"].append({
            "id": "test_id",
            "filename": "test.png",
            "timestamp": three_hours_ago,
            "width": 100,
            "height": 100,
            "has_annotations": False
        })

        recent = history.get_recent(count=1)
        assert recent[0]["time_ago"] == "3小时前"

    def test_format_days_ago(self, temp_history_dir):
        """Test time ago formatting for days."""
        history = ScreenshotHistory(history_dir=str(temp_history_dir))

        current_time = int(time.time())
        two_days_ago = current_time - (2 * 24 * 60 * 60)

        history._metadata["screenshots"].append({
            "id": "test_id",
            "filename": "test.png",
            "timestamp": two_days_ago,
            "width": 100,
            "height": 100,
            "has_annotations": False
        })

        recent = history.get_recent(count=1)
        assert recent[0]["time_ago"] == "2天前"
