"""Tests for the EnvironmentInfo model using unittest."""

import json
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from arc_agi import EnvironmentInfo


class TestEnvironmentInfo(unittest.TestCase):
    """Test EnvironmentInfo model."""

    def test_create_from_dict(self):
        """Test creating EnvironmentInfo from a dictionary."""
        data = {
            "game_id": "tg61-28585068",
            "title": "TG61",
            "tags": ["tag1", "tag2"],
            "baseline_actions": [12, 17, 18, 22, 50],
        }
        env_info = EnvironmentInfo(**data)

        self.assertEqual(env_info.game_id, "tg61-28585068")
        self.assertEqual(env_info.title, "TG61")
        self.assertEqual(env_info.tags, ["tag1", "tag2"])
        self.assertEqual(env_info.baseline_actions, [12, 17, 18, 22, 50])
        # date_downloaded should default to now
        self.assertIsNotNone(env_info.date_downloaded)
        self.assertIsInstance(env_info.date_downloaded, datetime)
        # class_name should default to first 4 chars of game_id capitalized
        self.assertEqual(env_info.class_name, "Tg61")

    def test_create_from_keyword_args(self):
        """Test creating EnvironmentInfo from keyword arguments."""
        env_info = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1", "tag2"],
            baseline_actions=[12, 17, 18, 22, 50],
        )

        self.assertEqual(env_info.game_id, "tg61-28585068")
        self.assertEqual(env_info.title, "TG61")
        self.assertEqual(env_info.tags, ["tag1", "tag2"])
        self.assertEqual(env_info.baseline_actions, [12, 17, 18, 22, 50])
        # date_downloaded should default to now
        self.assertIsNotNone(env_info.date_downloaded)
        self.assertIsInstance(env_info.date_downloaded, datetime)
        # class_name should default to first 4 chars of game_id capitalized
        self.assertEqual(env_info.class_name, "Tg61")

    def test_serialize_to_json(self):
        """Test serializing EnvironmentInfo to JSON string."""
        env_info = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1", "tag2"],
            baseline_actions=[12, 17, 18, 22, 50],
        )

        json_str = env_info.model_dump_json()
        self.assertIsInstance(json_str, str)

        # Parse JSON to verify structure
        parsed = json.loads(json_str)
        self.assertEqual(parsed["game_id"], "tg61-28585068")
        self.assertEqual(parsed["title"], "TG61")
        self.assertEqual(parsed["tags"], ["tag1", "tag2"])
        self.assertEqual(parsed["baseline_actions"], [12, 17, 18, 22, 50])
        # Defaults should be set
        self.assertIsNotNone(parsed["date_downloaded"])
        self.assertEqual(parsed["class_name"], "Tg61")

    def test_deserialize_from_json_string(self):
        """Test deserializing EnvironmentInfo from JSON string."""
        json_str = '{"game_id": "tg61-28585068", "title": "TG61", "tags": ["tag1", "tag2"], "baseline_actions": [12, 17, 18, 22, 50]}'

        env_info = EnvironmentInfo.model_validate_json(json_str)

        self.assertEqual(env_info.game_id, "tg61-28585068")
        self.assertEqual(env_info.title, "TG61")
        self.assertEqual(env_info.tags, ["tag1", "tag2"])
        self.assertEqual(env_info.baseline_actions, [12, 17, 18, 22, 50])

    def test_deserialize_from_json_bytes(self):
        """Test deserializing EnvironmentInfo from JSON bytes."""
        json_bytes = b'{"game_id": "tg61-28585068", "title": "TG61", "tags": ["tag1", "tag2"], "baseline_actions": [12, 17, 18, 22, 50]}'

        env_info = EnvironmentInfo.model_validate_json(json_bytes)

        self.assertEqual(env_info.game_id, "tg61-28585068")
        self.assertEqual(env_info.title, "TG61")
        self.assertEqual(env_info.tags, ["tag1", "tag2"])
        self.assertEqual(env_info.baseline_actions, [12, 17, 18, 22, 50])

    def test_round_trip_json(self):
        """Test round-trip serialization: object -> JSON -> object."""
        original = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1", "tag2"],
            baseline_actions=[12, 17, 18, 22, 50],
        )

        json_str = original.model_dump_json()
        restored = EnvironmentInfo.model_validate_json(json_str)

        self.assertEqual(original.game_id, restored.game_id)
        self.assertEqual(original.title, restored.title)
        self.assertEqual(original.tags, restored.tags)
        self.assertEqual(original.baseline_actions, restored.baseline_actions)

    def test_empty_tags(self):
        """Test EnvironmentInfo with empty tags list."""
        env_info = EnvironmentInfo(
            game_id="test-game",
            title="Test",
            tags=[],
            baseline_actions=[10, 20],
        )

        self.assertEqual(env_info.tags, [])

    def test_empty_baseline_actions(self):
        """Test EnvironmentInfo with empty baseline_actions list."""
        env_info = EnvironmentInfo(
            game_id="test-game",
            title="Test",
            tags=["tag1"],
            baseline_actions=[],
        )

        self.assertEqual(env_info.baseline_actions, [])

    def test_missing_game_id(self):
        """Test that missing game_id raises ValidationError."""
        with self.assertRaises(ValidationError):
            EnvironmentInfo(
                title="TG61",
                tags=["tag1"],
                baseline_actions=[12],
            )

    def test_invalid_game_id_type(self):
        """Test that invalid game_id type raises ValidationError."""
        with self.assertRaises(ValidationError):
            EnvironmentInfo(
                game_id=12345,  # Should be string
                title="TG61",
                tags=["tag1"],
                baseline_actions=[12],
            )

    def test_invalid_title_type(self):
        """Test that invalid title type raises ValidationError."""
        with self.assertRaises(ValidationError):
            EnvironmentInfo(
                game_id="tg61-28585068",
                title=12345,  # Should be string
                tags=["tag1"],
                baseline_actions=[12],
            )

    def test_invalid_tags_type(self):
        """Test that invalid tags type raises ValidationError."""
        with self.assertRaises(ValidationError):
            EnvironmentInfo(
                game_id="tg61-28585068",
                title="TG61",
                tags="not-a-list",  # Should be list
                baseline_actions=[12],
            )

    def test_invalid_baseline_actions_type(self):
        """Test that invalid baseline_actions type raises ValidationError."""
        with self.assertRaises(ValidationError):
            EnvironmentInfo(
                game_id="tg61-28585068",
                title="TG61",
                tags=["tag1"],
                baseline_actions="not-a-list",  # Should be list
            )

    def test_baseline_actions_with_numeric_strings(self):
        """Test that baseline_actions with numeric strings are coerced to integers."""
        # Pydantic v2 auto-coerces numeric strings to integers
        env_info = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1"],
            baseline_actions=["12", "17"],  # Will be coerced to [12, 17]
        )
        self.assertEqual(env_info.baseline_actions, [12, 17])
        self.assertIsInstance(env_info.baseline_actions[0], int)
        self.assertIsInstance(env_info.baseline_actions[1], int)

    def test_baseline_actions_with_non_numeric_strings(self):
        """Test that baseline_actions with non-numeric strings raises ValidationError."""
        with self.assertRaises(ValidationError):
            EnvironmentInfo(
                game_id="tg61-28585068",
                title="TG61",
                tags=["tag1"],
                baseline_actions=["not-a-number", "also-not-a-number"],
            )

    def test_tags_with_non_strings(self):
        """Test that tags with non-strings raises ValidationError."""
        with self.assertRaises(ValidationError):
            EnvironmentInfo(
                game_id="tg61-28585068",
                title="TG61",
                tags=[1, 2, 3],  # Should be strings
                baseline_actions=[12],
            )

    def test_model_dump(self):
        """Test model_dump returns dictionary."""
        env_info = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1", "tag2"],
            baseline_actions=[12, 17, 18, 22, 50],
        )

        dumped = env_info.model_dump()
        self.assertIsInstance(dumped, dict)
        self.assertEqual(dumped["game_id"], "tg61-28585068")
        self.assertEqual(dumped["title"], "TG61")
        self.assertEqual(dumped["tags"], ["tag1", "tag2"])
        self.assertEqual(dumped["baseline_actions"], [12, 17, 18, 22, 50])

    def test_model_validate_from_dict(self):
        """Test model_validate creates instance from dictionary."""
        data = {
            "game_id": "tg61-28585068",
            "title": "TG61",
            "tags": ["tag1", "tag2"],
            "baseline_actions": [12, 17, 18, 22, 50],
        }

        env_info = EnvironmentInfo.model_validate(data)

        self.assertEqual(env_info.game_id, "tg61-28585068")
        self.assertEqual(env_info.title, "TG61")
        self.assertEqual(env_info.tags, ["tag1", "tag2"])
        self.assertEqual(env_info.baseline_actions, [12, 17, 18, 22, 50])

    def test_date_downloaded_defaults_to_now(self):
        """Test that date_downloaded defaults to current time if not provided."""
        from datetime import datetime, timezone

        env_info = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1"],
            baseline_actions=[12],
        )

        # Should be set to a datetime (approximately now)
        self.assertIsNotNone(env_info.date_downloaded)
        self.assertIsInstance(env_info.date_downloaded, datetime)
        # Should be recent (within last minute)
        now = datetime.now(timezone.utc)
        time_diff = abs((now - env_info.date_downloaded).total_seconds())
        self.assertLess(time_diff, 60)

    def test_date_downloaded_with_datetime(self):
        """Test that date_downloaded can be set to a datetime object."""
        download_date = datetime.now(timezone.utc)
        env_info = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1"],
            baseline_actions=[12],
            date_downloaded=download_date,
        )

        self.assertEqual(env_info.date_downloaded, download_date)
        self.assertIsInstance(env_info.date_downloaded, datetime)

    def test_date_downloaded_json_serialization(self):
        """Test that date_downloaded is serialized to ISO format in JSON."""
        download_date = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        env_info = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1"],
            baseline_actions=[12],
            date_downloaded=download_date,
        )

        json_str = env_info.model_dump_json()
        parsed = json.loads(json_str)

        self.assertIn("date_downloaded", parsed)
        # Pydantic v2 serializes UTC as 'Z' format
        self.assertEqual(parsed["date_downloaded"], "2024-01-15T10:30:45Z")

    def test_date_downloaded_json_deserialization(self):
        """Test that date_downloaded can be deserialized from ISO format string."""
        json_str = '{"game_id": "tg61-28585068", "title": "TG61", "tags": ["tag1"], "baseline_actions": [12], "date_downloaded": "2024-01-15T10:30:45+00:00"}'

        env_info = EnvironmentInfo.model_validate_json(json_str)

        self.assertIsNotNone(env_info.date_downloaded)
        self.assertIsInstance(env_info.date_downloaded, datetime)
        self.assertEqual(env_info.date_downloaded.year, 2024)
        self.assertEqual(env_info.date_downloaded.month, 1)
        self.assertEqual(env_info.date_downloaded.day, 15)

    def test_date_downloaded_round_trip(self):
        """Test round-trip serialization with date_downloaded."""
        download_date = datetime.now(timezone.utc)
        original = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1"],
            baseline_actions=[12],
            date_downloaded=download_date,
        )

        json_str = original.model_dump_json()
        restored = EnvironmentInfo.model_validate_json(json_str)

        self.assertEqual(original.date_downloaded, restored.date_downloaded)
        self.assertIsInstance(restored.date_downloaded, datetime)

    def test_date_downloaded_from_dict(self):
        """Test creating EnvironmentInfo with date_downloaded from dictionary."""
        download_date = datetime.now(timezone.utc)
        data = {
            "game_id": "tg61-28585068",
            "title": "TG61",
            "tags": ["tag1"],
            "baseline_actions": [12],
            "date_downloaded": download_date,
        }

        env_info = EnvironmentInfo(**data)

        self.assertEqual(env_info.date_downloaded, download_date)

    def test_class_name_defaults_from_game_id(self):
        """Test that class_name defaults to first 4 characters of game_id capitalized."""
        # Test with game_id that has 4+ characters
        env_info = EnvironmentInfo(
            game_id="ls20-ajk315135",
            title="Test",
            tags=["tag1"],
            baseline_actions=[12],
        )

        self.assertEqual(env_info.class_name, "Ls20")

        # Test with shorter game_id
        env_info2 = EnvironmentInfo(
            game_id="ab1",
            title="Test",
            tags=["tag1"],
            baseline_actions=[12],
        )

        self.assertEqual(env_info2.class_name, "Ab1")

    def test_class_name_with_value(self):
        """Test that class_name can be set to a string."""
        env_info = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1"],
            baseline_actions=[12],
            class_name="MyGameClass",
        )

        self.assertEqual(env_info.class_name, "MyGameClass")
        self.assertIsInstance(env_info.class_name, str)

    def test_class_name_json_serialization(self):
        """Test that class_name is serialized correctly in JSON."""
        env_info = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1"],
            baseline_actions=[12],
            class_name="MyGameClass",
        )

        json_str = env_info.model_dump_json()
        parsed = json.loads(json_str)

        self.assertIn("class_name", parsed)
        self.assertEqual(parsed["class_name"], "MyGameClass")

    def test_class_name_json_deserialization(self):
        """Test that class_name can be deserialized from JSON string."""
        json_str = '{"game_id": "tg61-28585068", "title": "TG61", "tags": ["tag1"], "baseline_actions": [12], "class_name": "MyGameClass"}'

        env_info = EnvironmentInfo.model_validate_json(json_str)

        self.assertEqual(env_info.class_name, "MyGameClass")
        self.assertIsInstance(env_info.class_name, str)

    def test_class_name_round_trip(self):
        """Test round-trip serialization with class_name."""
        original = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1"],
            baseline_actions=[12],
            class_name="MyGameClass",
        )

        json_str = original.model_dump_json()
        restored = EnvironmentInfo.model_validate_json(json_str)

        self.assertEqual(original.class_name, restored.class_name)

    def test_class_name_from_dict(self):
        """Test creating EnvironmentInfo with class_name from dictionary."""
        data = {
            "game_id": "tg61-28585068",
            "title": "TG61",
            "tags": ["tag1"],
            "baseline_actions": [12],
            "class_name": "MyGameClass",
        }

        env_info = EnvironmentInfo(**data)

        self.assertEqual(env_info.class_name, "MyGameClass")

    def test_class_name_empty_string(self):
        """Test that class_name can be an empty string (explicit override)."""
        env_info = EnvironmentInfo(
            game_id="tg61-28585068",
            title="TG61",
            tags=["tag1"],
            baseline_actions=[12],
            class_name="",
        )

        self.assertEqual(env_info.class_name, "")

    def test_class_name_various_game_ids(self):
        """Test class_name generation from various game_id formats."""
        test_cases = [
            ("ls20-ajk315135", "Ls20"),
            ("tg61-28585068", "Tg61"),
            ("dr44", "Dr44"),
            ("ab1", "Ab1"),
            ("a", "A"),
            ("ABCD-123", "ABCD"),  # Capitalize first letter only, keep rest as-is
        ]

        for game_id, expected_class_name in test_cases:
            with self.subTest(game_id=game_id):
                env_info = EnvironmentInfo(
                    game_id=game_id,
                    title="Test",
                    tags=["tag1"],
                    baseline_actions=[12],
                )
                self.assertEqual(env_info.class_name, expected_class_name)

    def test_date_downloaded_and_class_name_both_default(self):
        """Test that both defaults work together."""
        env_info = EnvironmentInfo(
            game_id="ls20-test",
            title="Test",
            tags=["tag1"],
            baseline_actions=[12],
        )

        self.assertIsNotNone(env_info.date_downloaded)
        self.assertIsInstance(env_info.date_downloaded, datetime)
        self.assertEqual(env_info.class_name, "Ls20")


if __name__ == "__main__":
    unittest.main()
