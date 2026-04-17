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

from requests.exceptions import HTTPError

_mock_dotenv = MagicMock()
_mock_dotenv.load_dotenv = MagicMock()
sys.modules["dotenv"] = _mock_dotenv

from arcengine import GameAction  # noqa: E402

from arc_agi import (  # noqa: E402
    Arcade,
    OperationMode,
)


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

            result = client_arc.close_scorecard(scorecard_id=card_id)
            self.assertIsNotNone(result, "Close should return scorecard")
            self.assertIs(
                result.competition_mode,
                False,
                "Scorecard should not have a competition_mode",
            )
        finally:
            if server_error:
                raise server_error[0]

    def test_competition_mode_on_client_can_open_multiple_scorecards(
        self,
    ) -> None:
        if not Path(self.environments_dir).exists():
            self.skipTest("test_environment_files not found")

        port = _find_free_port()
        base_url = f"http://127.0.0.1:{port}"

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

        time.sleep(1.5)

        try:
            client_arc = Arcade(
                operation_mode=OperationMode.COMPETITION,
                arc_base_url=base_url,
                arc_api_key="test-key-123",
                logger=self.logger,
            )

            card_id_1 = client_arc.create_scorecard()
            self.assertIsNotNone(card_id_1, "Should get card_id from server")

            card_id_2 = client_arc.create_scorecard()
            self.assertIsNotNone(card_id_2, "Should get card_id from server")
        finally:
            if server_error:
                raise server_error[0]

    def test_competition_mode_on_sever_can_not_open_multiple_scorecards(
        self,
    ) -> None:
        if not Path(self.environments_dir).exists():
            self.skipTest("test_environment_files not found")

        port = _find_free_port()
        base_url = f"http://127.0.0.1:{port}"

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

        server_error: list[Exception] = []

        def run_server() -> None:
            try:
                server_arc.listen_and_serve(
                    host="127.0.0.1",
                    port=port,
                    use_reloader=False,
                    competition_mode=True,
                )
            except Exception as e:
                server_error.append(e)

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        time.sleep(1.5)

        try:
            client_arc = Arcade(
                operation_mode=OperationMode.COMPETITION,
                arc_base_url=base_url,
                arc_api_key="test-key-123",
                logger=self.logger,
            )

            card_id_1 = client_arc.create_scorecard()
            self.assertIsNotNone(card_id_1, "Should get card_id from server")

            with self.assertRaises(HTTPError):
                client_arc.create_scorecard()
        finally:
            if server_error:
                raise server_error[0]

    def test_competition_mode_scorecard_create_and_close_when_client_is_competition(
        self,
    ) -> None:
        if not Path(self.environments_dir).exists():
            self.skipTest("test_environment_files not found")

        port = _find_free_port()
        base_url = f"http://127.0.0.1:{port}"

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

        time.sleep(1.5)

        try:
            client_arc = Arcade(
                operation_mode=OperationMode.COMPETITION,
                arc_base_url=base_url,
                arc_api_key="test-key-123",
                logger=self.logger,
            )

            card_id = client_arc.create_scorecard()
            self.assertIsNotNone(card_id, "Should get card_id from server")

            result = client_arc.close_scorecard(scorecard_id=card_id)
            self.assertIsNotNone(result, "Close should return scorecard")
            self.assertIs(
                result.competition_mode,
                True,
                "Scorecard should have competition_mode=True",
            )
        finally:
            if server_error:
                raise server_error[0]

    def test_competition_mode_scorecard_create_and_close_when_server_is_competition(
        self,
    ) -> None:
        if not Path(self.environments_dir).exists():
            self.skipTest("test_environment_files not found")

        port = _find_free_port()
        base_url = f"http://127.0.0.1:{port}"

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

        server_error: list[Exception] = []

        def run_server() -> None:
            try:
                server_arc.listen_and_serve(
                    host="127.0.0.1",
                    port=port,
                    use_reloader=False,
                    competition_mode=True,
                )
            except Exception as e:
                server_error.append(e)

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        time.sleep(1.5)

        try:
            client_arc = Arcade(
                operation_mode=OperationMode.ONLINE,
                arc_base_url=base_url,
                arc_api_key="test-key-123",
                logger=self.logger,
            )

            card_id = client_arc.create_scorecard()
            self.assertIsNotNone(card_id, "Should get card_id from server")

            # This should throw an exception from the rest server
            with self.assertRaises(HTTPError):
                client_arc.get_scorecard(scorecard_id=card_id)

            result = client_arc.close_scorecard(scorecard_id=card_id)
            self.assertIsNotNone(result, "Close should return scorecard")
            self.assertIs(
                result.competition_mode,
                True,
                "Scorecard should have competition_mode=True",
            )

            # Make sure the scoreard has all the environments
            self.assertIsNotNone(
                result.find_environment("bt11"), "Should have bt11 in the scorecard"
            )
            self.assertIsNotNone(
                result.find_environment("bt33"), "Should have bt33 in the scorecard"
            )

        finally:
            if server_error:
                raise server_error[0]

    def test_competition_mode_can_only_create_one_instance_of_an_environment(
        self,
    ) -> None:
        if not Path(self.environments_dir).exists():
            self.skipTest("test_environment_files not found")

        port = _find_free_port()
        base_url = f"http://127.0.0.1:{port}"

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

        time.sleep(1.5)

        try:
            client_arc_normal = Arcade(
                operation_mode=OperationMode.ONLINE,
                arc_base_url=base_url,
                arc_api_key="test-key-123",
                logger=self.logger,
            )

            normal_card_id = client_arc_normal.create_scorecard()
            self.assertIsNotNone(normal_card_id, "Should get card_id from server")

            normal_env_1 = client_arc_normal.make(
                game_id="bt11", scorecard_id=normal_card_id
            )
            self.assertIsNotNone(normal_env_1, "Should get emv from server")
            normal_env_2 = client_arc_normal.make(
                game_id="bt11", scorecard_id=normal_card_id
            )
            self.assertIsNotNone(normal_env_2, "Should get card_id from server")

            normal_scorecard = client_arc_normal.close_scorecard(
                scorecard_id=normal_card_id
            )
            normal_env_score = normal_scorecard.find_environment("bt11")
            self.assertIsNotNone(normal_env_score, "Should get a environment")
            self.assertEqual(len(normal_env_score.runs), 2, "Should have 2 runs")

            client_arc_comp = Arcade(
                operation_mode=OperationMode.COMPETITION,
                arc_base_url=base_url,
                arc_api_key="test-key-987",
                logger=self.logger,
            )
            comp_card_id = client_arc_comp.create_scorecard()
            self.assertIsNotNone(comp_card_id, "Should get card_id from server")

            comp_env_1 = client_arc_comp.make(game_id="bt11", scorecard_id=comp_card_id)
            self.assertIsNotNone(comp_env_1, "Should get env from server")
            comp_env_2 = client_arc_comp.make(
                game_id="bt11", scorecard_id=comp_card_id
            )  # This should raise an error
            self.assertIsNotNone(comp_env_2, "should get an env")
            self.assertIsNone(
                comp_env_2.observation_space, "Should not get a observation space"
            )

            comp_scorecard = client_arc_comp.close_scorecard(scorecard_id=comp_card_id)
            comp_env_score = comp_scorecard.find_environment("bt11")
            self.assertIsNotNone(comp_env_score, "Should get a environment")
            self.assertEqual(len(comp_env_score.runs), 1, "Should have 1 runs")

        finally:
            if server_error:
                raise server_error[0]

    def test_competition_mode_can_only_reset_levels(
        self,
    ) -> None:
        if not Path(self.environments_dir).exists():
            self.skipTest("test_environment_files not found")

        port = _find_free_port()
        base_url = f"http://127.0.0.1:{port}"

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

        time.sleep(1.5)

        try:
            client_arc_normal = Arcade(
                operation_mode=OperationMode.ONLINE,
                arc_base_url=base_url,
                arc_api_key="test-key-123",
                logger=self.logger,
            )

            normal_card_id = client_arc_normal.create_scorecard()
            self.assertIsNotNone(normal_card_id, "Should get card_id from server")

            normal_env_1 = client_arc_normal.make(
                game_id="bt11", scorecard_id=normal_card_id
            )
            self.assertIsNotNone(normal_env_1, "Should get env from server")

            for i in range(4):
                frame = normal_env_1.step(GameAction.ACTION3)
                self.assertIsNotNone(frame, f"Step {i + 1} should return frame")

            normal_final_frame = normal_env_1.observation_space
            self.assertIsNotNone(normal_final_frame)
            self.assertEqual(
                normal_final_frame.levels_completed,
                1,
                "Four ACTION3 steps should result in levels_completed=1",
            )

            normal_reset_frame = normal_env_1.reset()
            self.assertIsNotNone(normal_reset_frame)
            self.assertEqual(
                normal_reset_frame.levels_completed,
                0,
                "Full reset should have put us back to the starting level",
            )

            # Full reset should have 2 runs
            normal_scorecard = client_arc_normal.close_scorecard(
                scorecard_id=normal_card_id
            )
            normal_env_score = normal_scorecard.find_environment("bt11")
            self.assertIsNotNone(normal_env_score, "Should get a environment")
            self.assertEqual(len(normal_env_score.runs), 2, "Should have 2 runs")

            client_arc_comp = Arcade(
                operation_mode=OperationMode.COMPETITION,
                arc_base_url=base_url,
                arc_api_key="test-key-987",
                logger=self.logger,
            )
            comp_card_id = client_arc_comp.create_scorecard()
            self.assertIsNotNone(comp_card_id, "Should get card_id from server")

            comp_env_1 = client_arc_comp.make(game_id="bt11", scorecard_id=comp_card_id)
            self.assertIsNotNone(comp_env_1, "Should get env from server")

            for i in range(4):
                frame = comp_env_1.step(GameAction.ACTION3)
                self.assertIsNotNone(frame, f"Step {i + 1} should return frame")

            comp_final_frame = comp_env_1.observation_space
            self.assertIsNotNone(comp_final_frame)
            self.assertEqual(
                comp_final_frame.levels_completed,
                1,
                "Four ACTION3 steps should result in levels_completed=1",
            )

            comp_reset_frame = comp_env_1.step(GameAction.RESET)
            self.assertIsNotNone(comp_reset_frame)
            self.assertEqual(
                comp_reset_frame.levels_completed,
                1,
                "Full reset not have happend and thuse levels_completed should be 1",
            )

            # a second level reset shouldn't reset the game either
            comp_reset_frame = comp_env_1.step(GameAction.RESET)
            self.assertIsNotNone(comp_reset_frame)
            self.assertEqual(
                comp_reset_frame.levels_completed,
                1,
                "Full reset not have happend and thuse levels_completed should be 1",
            )

            # a third level reset shouldn't reset the game either, this time via reset()
            comp_reset_frame = comp_env_1.reset()
            self.assertIsNotNone(comp_reset_frame)
            self.assertEqual(
                comp_reset_frame.levels_completed,
                1,
                "Full reset not have happend and thuse levels_completed should be 1",
            )
            # a fourth level reset shouldn't reset the game either, this time via reset()
            comp_reset_frame = comp_env_1.reset()
            self.assertIsNotNone(comp_reset_frame)
            self.assertEqual(
                comp_reset_frame.levels_completed,
                1,
                "Full reset not have happend and thuse levels_completed should be 1",
            )            

            # No full reset should happen and thus we should have 1 run
            comp_scorecard = client_arc_comp.close_scorecard(scorecard_id=comp_card_id)
            comp_env_score = comp_scorecard.find_environment("bt11")
            self.assertIsNotNone(comp_env_score, "Should get a environment")
            self.assertEqual(len(comp_env_score.runs), 1, "Should have 1 runs")
            self.assertEqual(
                comp_env_score.runs[0].actions,
                8,
                "Should have 8 actions, even the failed reset counts as an action",
            )

        finally:
            if server_error:
                raise server_error[0]


if __name__ == "__main__":
    unittest.main()
