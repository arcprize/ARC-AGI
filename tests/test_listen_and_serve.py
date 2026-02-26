"""Tests for listen_and_serve: offline server with online client."""

import logging
import os
import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_mock_dotenv = MagicMock()
_mock_dotenv.load_dotenv = MagicMock()
sys.modules["dotenv"] = _mock_dotenv

from arcengine import GameAction  # noqa: E402

from arc_agi import Arcade, OperationMode  # noqa: E402


def _find_free_port() -> int:
    """Bind to port 0 to get an OS-assigned free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestListenAndServe(unittest.TestCase):
    """Test listen_and_serve with offline server and online client."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.env_vars_to_clear = [
            "ARC_API_KEY",
            "ARC_BASE_URL",
            "OFFLINE_ONLY",
            "ONLINE_ONLY",
            "COMPETITION_MODE",
            "LISTEN_BINDINGS",
            "ENVIRONMENTS_DIR",
        ]
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

        self.logger = logging.getLogger("test")
        self.logger.setLevel(logging.INFO)

        test_dir = Path(__file__).parent.parent / "test_environment_files"
        self.environments_dir = str(test_dir)

    def tearDown(self) -> None:
        """Clean up after tests."""
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def test_offline_server_online_client_four_action3_levels_completed_one(
        self,
    ) -> None:
        """Spin up Arcade in offline mode with test_environment_files, serve backend,
        then use online client to play bt11: four ACTION3 steps yield levels_completed=1."""
        if not Path(self.environments_dir).exists():
            self.skipTest("test_environment_files not found")

        port = _find_free_port()
        base_url = f"http://127.0.0.1:{port}"

        # Server: offline Arcade with test_environment_files
        server_arc = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=self.environments_dir,
            arc_api_key="test-key-123",
            logger=self.logger,
        )
        self.assertGreater(
            len(server_arc.available_environments),
            0,
            "Server should have at least one environment from test_environment_files",
        )

        # Run server in background thread (blocking listen_and_serve)
        server_error: list[Exception] = []

        def run_server() -> None:
            try:
                server_arc.listen_and_serve(
                    host="127.0.0.1",
                    port=port,
                    use_reloader=False,
                )
            except Exception as e:
                server_error.append(e)

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # Give server time to bind
        time.sleep(1.5)

        try:
            # Client: online Arcade pointing at localhost
            client_arc = Arcade(
                operation_mode=OperationMode.ONLINE,
                arc_base_url=base_url,
                arc_api_key="test-key-123",
                logger=self.logger,
            )

            # Open scorecard on server (POST /api/scorecard/open)
            card_id = client_arc.create_scorecard()
            self.assertIsNotNone(card_id, "Should get card_id from server")

            # Make remote wrapper for bt11
            env = client_arc.make(game_id="bt11", scorecard_id=card_id)
            self.assertIsNotNone(env, "Should create remote environment")

            # get starting frame and play four ACTION3 steps
            start_frame = env.observation_space
            self.assertIsNotNone(start_frame, "Reset should return frame")
            initial_level = start_frame.levels_completed

            for i in range(4):
                frame = env.step(GameAction.ACTION3)
                self.assertIsNotNone(frame, f"Step {i + 1} should return frame")

            final_frame = env.observation_space
            self.assertIsNotNone(final_frame)
            self.assertEqual(
                final_frame.levels_completed,
                1,
                "Four ACTION3 steps should result in levels_completed=1",
            )
            self.assertGreater(
                final_frame.levels_completed,
                initial_level,
                "levels_completed should have increased",
            )
        finally:
            if server_error:
                raise server_error[0]


if __name__ == "__main__":
    unittest.main()
