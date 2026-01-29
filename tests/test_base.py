"""Tests for the ARCAGI3 base class using unittest."""

import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import requests

# Create a mock dotenv module before any imports
_mock_dotenv = MagicMock()
_mock_dotenv.load_dotenv = MagicMock()
sys.modules["dotenv"] = _mock_dotenv

# Now import arcagi3 - the mock will be used instead of real dotenv
from arc_agi import Arcade, OperationMode  # noqa: E402


class TestARCAGI3Defaults(unittest.TestCase):
    """Test ARCAGI3 with default values."""

    def setUp(self):
        """Clear environment variables before each test."""
        self.env_vars_to_clear = [
            "ARC_API_KEY",
            "ARC_BASE_URL",
            "OPERATION_MODE",
            "OFFLINE_ONLY",
            "ONLINE_ONLY",
            "COMPETITION_MODE",
            "LISTEN_BINDINGS",
            "ENVIRONMENTS_DIR",
        ]
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def tearDown(self):
        """Clean up environment variables after each test."""
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def test_default_initialization(self):
        """Test that default values are used when no parameters are provided."""
        client = Arcade()

        self.assertEqual(client.arc_api_key, "test-key-123")
        self.assertEqual(client.arc_base_url, "https://three.arcprize.org")
        self.assertEqual(client.operation_mode, OperationMode.NORMAL)
        self.assertEqual(client.environments_dir, "environment_files")

    def test_constructor_parameters(self):
        """Test that constructor parameters are used correctly."""
        client = Arcade(
            arc_api_key="test-key-123",
            arc_base_url="https://custom.example.com",
            operation_mode=OperationMode.OFFLINE,
        )

        self.assertEqual(client.arc_api_key, "test-key-123")
        self.assertEqual(client.arc_base_url, "https://custom.example.com")
        self.assertEqual(client.operation_mode, OperationMode.OFFLINE)

    def test_default_logger_created(self):
        """Test that a default logger is created when None is passed."""
        client = Arcade()

        self.assertIsNotNone(client.logger)
        self.assertIsInstance(client.logger, logging.Logger)
        # Check that logger has a StreamHandler pointing to stdout
        handlers = client.logger.handlers
        self.assertGreater(len(handlers), 0)
        stdout_handlers = [h for h in handlers if isinstance(h, logging.StreamHandler)]
        self.assertGreater(len(stdout_handlers), 0)

    def test_custom_logger_used(self):
        """Test that a custom logger is used when provided."""
        custom_logger = logging.getLogger("custom_test_logger")
        custom_logger.setLevel(logging.DEBUG)
        client = Arcade(logger=custom_logger)

        self.assertEqual(client.logger, custom_logger)
        self.assertEqual(client.logger.name, "custom_test_logger")
        self.assertEqual(client.logger.level, logging.DEBUG)


class TestARCAGI3EnvironmentVariables(unittest.TestCase):
    """Test ARCAGI3 with environment variable overrides."""

    def setUp(self):
        """Clear environment variables before each test."""
        self.env_vars_to_clear = [
            "ARC_API_KEY",
            "ARC_BASE_URL",
            "OPERATION_MODE",
            "OFFLINE_ONLY",
            "ONLINE_ONLY",
            "COMPETITION_MODE",
            "LISTEN_BINDINGS",
            "ENVIRONMENTS_DIR",
        ]
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def tearDown(self):
        """Clean up environment variables after each test."""
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def test_arc_api_key_from_env(self):
        """Test that constructor argument overrides environment variable."""
        os.environ["ARC_API_KEY"] = "env-key-456"
        client = Arcade(
            operation_mode=OperationMode.OFFLINE, arc_api_key="constructor-key"
        )

        self.assertEqual(client.arc_api_key, "constructor-key")

    def test_arc_base_url_from_env(self):
        """Test that constructor argument overrides environment variable."""
        os.environ["ARC_BASE_URL"] = "https://env.example.com"
        client = Arcade(
            operation_mode=OperationMode.OFFLINE,
            arc_base_url="https://constructor.example.com",
        )

        self.assertEqual(client.arc_base_url, "https://constructor.example.com")

    def test_operation_mode_from_constructor_overrides_env(self):
        """Test that constructor argument overrides OPERATION_MODE env var."""
        os.environ["OPERATION_MODE"] = "normal"
        client = Arcade(operation_mode=OperationMode.OFFLINE)

        self.assertEqual(client.operation_mode, OperationMode.OFFLINE)

    def test_operation_mode_from_env_when_normal_passed(self):
        """Test that when NORMAL is passed (default), env var is still checked."""
        os.environ["OPERATION_MODE"] = "offline"
        client = Arcade(operation_mode=OperationMode.NORMAL)

        self.assertEqual(client.operation_mode, OperationMode.OFFLINE)

    def test_operation_mode_online_from_constructor_overrides_env(self):
        """Test that constructor ONLINE overrides env var."""
        os.environ["OPERATION_MODE"] = "normal"
        client = Arcade(operation_mode=OperationMode.ONLINE)

        self.assertEqual(client.operation_mode, OperationMode.ONLINE)

    def test_operation_mode_from_env_when_default(self):
        """Test that OPERATION_MODE env is used when default NORMAL is used."""
        os.environ["OPERATION_MODE"] = "online"
        client = Arcade()

        self.assertEqual(client.operation_mode, OperationMode.ONLINE)


class TestARCAGI3BooleanParsing(unittest.TestCase):
    """Test boolean/enum parsing from environment variables."""

    def setUp(self):
        """Clear environment variables before each test."""
        self.env_vars_to_clear = [
            "OPERATION_MODE",
            "OFFLINE_ONLY",
            "ONLINE_ONLY",
            "COMPETITION_MODE",
        ]
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def tearDown(self):
        """Clean up environment variables after each test."""
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def test_operation_mode_env_normal_when_offline_false(self):
        """Test that OFFLINE_ONLY=false yields NORMAL when no other env set."""
        os.environ["OFFLINE_ONLY"] = "false"
        client = Arcade()
        self.assertEqual(client.operation_mode, OperationMode.NORMAL)

    def test_operation_mode_env_online_false_yields_normal(self):
        """Test that ONLINE_ONLY=false with no OPERATION_MODE yields NORMAL."""
        os.environ["ONLINE_ONLY"] = "false"
        client = Arcade()
        self.assertEqual(client.operation_mode, OperationMode.NORMAL)


class TestARCAGI3EdgeCases(unittest.TestCase):
    """Test edge cases and special scenarios."""

    def setUp(self):
        """Clear environment variables before each test."""
        self.env_vars_to_clear = [
            "ARC_API_KEY",
            "ARC_BASE_URL",
            "OPERATION_MODE",
            "OFFLINE_ONLY",
            "ONLINE_ONLY",
            "COMPETITION_MODE",
            "LISTEN_BINDINGS",
            "ENVIRONMENTS_DIR",
        ]
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def tearDown(self):
        """Clean up environment variables after each test."""
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def test_empty_string_api_key(self):
        """Test that empty string API key is handled correctly."""
        client = Arcade(arc_api_key="")

        self.assertEqual(client.arc_api_key, "test-key-123")

    def test_constructor_overrides_when_env_not_set(self):
        """Test that constructor values are used when env vars are not set."""
        client = Arcade(
            arc_api_key="constructor-key",
            arc_base_url="https://constructor.url",
            operation_mode=OperationMode.ONLINE,
        )

        self.assertEqual(client.arc_api_key, "constructor-key")
        self.assertEqual(client.arc_base_url, "https://constructor.url")
        self.assertEqual(client.operation_mode, OperationMode.ONLINE)

    def test_all_env_vars_set(self):
        """Test that all environment variables can be set simultaneously."""
        os.environ["ARC_API_KEY"] = "env-api-key"
        os.environ["ARC_BASE_URL"] = "https://env.url"
        os.environ["OPERATION_MODE"] = "online"

        client = Arcade()

        self.assertEqual(client.arc_api_key, "env-api-key")
        self.assertEqual(client.arc_base_url, "https://env.url")
        self.assertEqual(client.operation_mode, OperationMode.ONLINE)


class TestARCAGI3EnvironmentsDirScanning(unittest.TestCase):
    """Test environments_dir scanning functionality."""

    def setUp(self):
        """Clear environment variables before each test."""
        self.env_vars_to_clear = ["ENVIRONMENTS_DIR"]
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def tearDown(self):
        """Clean up environment variables after each test."""
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def test_environments_dir_scanning(self):
        """Test that environments_dir scanning finds metadata.json files."""
        import tempfile
        from pathlib import Path

        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            environments_dir = Path(tmpdir) / "environments"
            environments_dir.mkdir()

            # Create environment1 with metadata.json
            env1_dir = environments_dir / "env1"
            env1_dir.mkdir()
            metadata1 = env1_dir / "metadata.json"
            metadata1.write_text(
                '{"game_id": "test1", "title": "Test1", "tags": ["tag1"], "baseline_actions": [10]}',
                encoding="utf-8",
            )

            # Create environment2 in subdirectory
            env2_dir = environments_dir / "env2" / "subdir"
            env2_dir.mkdir(parents=True)
            metadata2 = env2_dir / "metadata.json"
            metadata2.write_text(
                '{"game_id": "test2", "title": "Test2", "tags": ["tag2"], "baseline_actions": [20]}',
                encoding="utf-8",
            )

            # Create invalid metadata file (should be skipped)
            env3_dir = environments_dir / "env3"
            env3_dir.mkdir()
            metadata3 = env3_dir / "metadata.json"
            metadata3.write_text("invalid json", encoding="utf-8")

            # Initialize ARCAGI3 with environments_dir
            client = Arcade(environments_dir=str(environments_dir))

            # Should have found 2 valid environments
            self.assertEqual(len(client.available_environments), 2)
            # Check that both environments were found (order may vary)
            environment_ids = {env.game_id for env in client.available_environments}
            self.assertEqual(environment_ids, {"test1", "test2"})

    def test_environments_dir_none(self):
        """Test that environments_dir can be explicitly set to None."""
        client = Arcade(environments_dir=None)

        self.assertIsNone(client.environments_dir)
        self.assertEqual(len(client.available_environments), 0)

    def test_environments_dir_default(self):
        """Test that environments_dir defaults to 'environment_files'."""
        client = Arcade()

        self.assertEqual(client.environments_dir, "environment_files")

    def test_environments_dir_nonexistent(self):
        """Test that non-existent environments_dir is handled gracefully."""
        client = Arcade(environments_dir="/nonexistent/path")

        self.assertEqual(client.environments_dir, "/nonexistent/path")
        self.assertEqual(len(client.available_environments), 0)

    def test_environments_dir_from_env(self):
        """Test that environments_dir can be set from environment variable when constructor uses default."""
        import tempfile
        from pathlib import Path

        # Create a temporary directory with metadata
        with tempfile.TemporaryDirectory() as tmpdir:
            environments_dir = Path(tmpdir) / "environments"
            environments_dir.mkdir()
            env_dir = environments_dir / "env1"
            env_dir.mkdir()
            metadata = env_dir / "metadata.json"
            metadata.write_text(
                '{"game_id": "env-test", "title": "EnvTest", "tags": ["tag1"], "baseline_actions": [10]}',
                encoding="utf-8",
            )

            os.environ["ENVIRONMENTS_DIR"] = str(environments_dir)
            try:
                # No constructor arg, should use env var
                client = Arcade()

                self.assertEqual(client.environments_dir, str(environments_dir))
                self.assertEqual(len(client.available_environments), 1)
                self.assertEqual(client.available_environments[0].game_id, "env-test")
            finally:
                os.environ.pop("ENVIRONMENTS_DIR", None)

    def test_environments_dir_empty_directory(self):
        """Test that empty environments_dir results in no environments."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            environments_dir = Path(tmpdir) / "environments"
            environments_dir.mkdir()

            client = Arcade(environments_dir=str(environments_dir))

            self.assertEqual(len(client.available_environments), 0)

    def test_environments_dir_with_test_files(self):
        """Test scanning the test_environment_files directory."""
        from pathlib import Path

        test_environments_dir = Path(__file__).parent.parent / "test_environment_files"
        if test_environments_dir.exists():
            client = Arcade(environments_dir=str(test_environments_dir))

            # Should find at least 2 metadata.json files
            self.assertGreaterEqual(len(client.available_environments), 2)
            # Check that the expected environments are found
            environment_ids = {env.game_id for env in client.available_environments}
            self.assertIn("bt11-fd9df0622a1a", environment_ids)
            self.assertIn("tg62-12345678", environment_ids)


class TestARCAGI3APIFetching(unittest.TestCase):
    """Test API fetching functionality."""

    def setUp(self):
        """Clear environment variables before each test."""
        self.env_vars_to_clear = [
            "ENVIRONMENTS_DIR",
            "OPERATION_MODE",
            "OFFLINE_ONLY",
            "ONLINE_ONLY",
            "ARC_API_KEY",
        ]
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def tearDown(self):
        """Clean up environment variables after each test."""
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    @patch("arc_agi.base.requests.get")
    def test_api_fetch_when_not_offline(self, mock_get):
        """Test that API is called when not in OFFLINE mode."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "game_id": "api-game-1",
                "title": "API Game 1",
                "tags": ["api-tag"],
                "baseline_actions": [10, 20],
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = Arcade(
            arc_api_key="test-api-key",
            operation_mode=OperationMode.NORMAL,
            environments_dir=None,  # No local scanning
        )

        # Verify API was called
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "https://three.arcprize.org/api/games")
        self.assertEqual(call_args[1]["headers"]["X-API-Key"], "test-api-key")

        # Verify environment was added
        self.assertEqual(len(client.available_environments), 1)
        self.assertEqual(client.available_environments[0].game_id, "api-game-1")

    @patch("arc_agi.base.requests.get")
    def test_api_not_fetched_when_offline(self, mock_get):
        """Test that API is not called when in OFFLINE mode."""
        _ = Arcade(
            arc_api_key="test-api-key",
            operation_mode=OperationMode.OFFLINE,
            environments_dir=None,
        )

        # Verify API was not called
        mock_get.assert_not_called()

    @patch("arc_agi.base.requests.get")
    def test_api_merge_with_local_environments(self, mock_get):
        """Test that API environments are merged with local environments."""
        import tempfile
        from pathlib import Path

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "game_id": "api-game-1",
                "title": "API Game 1",
                "tags": ["api-tag"],
                "baseline_actions": [10],
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Create local environment with different game_id
        with tempfile.TemporaryDirectory() as tmpdir:
            environments_dir = Path(tmpdir) / "environments"
            environments_dir.mkdir()
            env_dir = environments_dir / "env1"
            env_dir.mkdir()
            metadata = env_dir / "metadata.json"
            metadata.write_text(
                '{"game_id": "local-game-1", "title": "Local Game 1", "tags": ["local-tag"], "baseline_actions": [5]}',
                encoding="utf-8",
            )

            client = Arcade(
                arc_api_key="test-api-key",
                operation_mode=OperationMode.NORMAL,
                environments_dir=str(environments_dir),
            )

            # Should have both local and API environments
            self.assertEqual(len(client.available_environments), 2)
            game_ids = {env.game_id for env in client.available_environments}
            self.assertEqual(game_ids, {"local-game-1", "api-game-1"})

    @patch("arc_agi.base.requests.get")
    def test_api_removes_duplicate_game_ids(self, mock_get):
        """Test that duplicate game_ids from API are not added if they exist locally."""
        import tempfile
        from pathlib import Path

        # Mock API response with same game_id as local
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "game_id": "duplicate-game",
                "title": "API Version",
                "tags": ["api-tag"],
                "baseline_actions": [10],
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Create local environment with same game_id
        with tempfile.TemporaryDirectory() as tmpdir:
            environments_dir = Path(tmpdir) / "environments"
            environments_dir.mkdir()
            env_dir = environments_dir / "env1"
            env_dir.mkdir()
            metadata = env_dir / "metadata.json"
            metadata.write_text(
                '{"game_id": "duplicate-game", "title": "Local Version", "tags": ["local-tag"], "baseline_actions": [5]}',
                encoding="utf-8",
            )

            client = Arcade(
                arc_api_key="test-api-key",
                operation_mode=OperationMode.NORMAL,
                environments_dir=str(environments_dir),
            )

            # Should only have one environment (local version, API duplicate ignored)
            self.assertEqual(len(client.available_environments), 1)
            self.assertEqual(client.available_environments[0].game_id, "duplicate-game")
            # Should be the local version (scanned first)
            self.assertEqual(client.available_environments[0].title, "Local Version")

    @patch("arc_agi.base.requests.get")
    def test_api_no_key_skips_fetch(self, mock_get):
        """Test that API is not called when no API key is provided."""
        _ = Arcade(
            arc_api_key="",  # Empty API key
            operation_mode=OperationMode.NORMAL,
            environments_dir=None,
        )

        # Verify API was not called
        mock_get.assert_not_called()

    @patch("arc_agi.base.requests.get")
    def test_api_error_handled_gracefully(self, mock_get):
        """Test that API errors are handled gracefully."""
        # Mock API error
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        client = Arcade(
            arc_api_key="test-api-key",
            operation_mode=OperationMode.NORMAL,
            environments_dir=None,
        )

        # Should not raise exception, just have no environments
        self.assertEqual(len(client.available_environments), 0)

    @patch("arc_agi.base.requests.get")
    def test_api_http_error_handled_gracefully(self, mock_get):
        """Test that HTTP errors are handled gracefully."""
        # Mock HTTP error response
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found"
        )
        mock_get.return_value = mock_response

        client = Arcade(
            arc_api_key="test-api-key",
            operation_mode=OperationMode.NORMAL,
            environments_dir=None,
        )

        # Should not raise exception, just have no environments
        self.assertEqual(len(client.available_environments), 0)

    @patch("arc_agi.base.requests.get")
    def test_api_invalid_response_handled_gracefully(self, mock_get):
        """Test that invalid API responses are handled gracefully."""
        # Mock invalid JSON response
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = Arcade(
            arc_api_key="test-api-key",
            operation_mode=OperationMode.NORMAL,
            environments_dir=None,
        )

        # Should not raise exception, just have no environments
        self.assertEqual(len(client.available_environments), 0)

    @patch("arc_agi.base.requests.get")
    def test_api_custom_base_url(self, mock_get):
        """Test that API uses custom base_url."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        _ = Arcade(
            arc_api_key="test-api-key",
            arc_base_url="https://custom.example.com",
            operation_mode=OperationMode.NORMAL,
            environments_dir=None,
        )

        # Verify API was called with custom URL
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "https://custom.example.com/api/games")


if __name__ == "__main__":
    unittest.main()
