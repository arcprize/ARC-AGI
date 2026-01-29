"""Tests for LocalEnvironmentWrapper using unittest."""

import logging
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_mock_dotenv = MagicMock()
_mock_dotenv.load_dotenv = MagicMock()
sys.modules["dotenv"] = _mock_dotenv

from arcengine import GameAction, GameState  # noqa: E402

from arc_agi import Arcade, OperationMode  # noqa: E402


class TestLocalEnvironmentWrapper(unittest.TestCase):
    """Test LocalEnvironmentWrapper functionality."""

    def setUp(self):
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

        # Set up logger
        self.logger = logging.getLogger("test")
        self.logger.setLevel(logging.INFO)

        # Set environments_dir to test_environment_files
        test_dir = Path(__file__).parent.parent / "test_environment_files"
        self.environments_dir = str(test_dir)

    def tearDown(self):
        """Clean up after tests."""
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def test_make_bt11_without_version(self):
        """Test making bt11 game without version (should find latest)."""
        client = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=self.environments_dir,
            logger=self.logger,
        )

        wrapper = client.make(game_id="bt11", scorecard_id="test-scorecard-1")

        self.assertIsNotNone(wrapper, "Wrapper should be created")
        self.assertEqual(wrapper.environment_info.game_id, "bt11-fd9df0622a1a")
        self.assertEqual(wrapper.scorecard_id, "test-scorecard-1")
        self.assertIsNotNone(wrapper.environment_info.local_dir)

    def test_make_bt11_with_version(self):
        """Test making bt11 game with specific version."""
        client = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=self.environments_dir,
            logger=self.logger,
        )

        wrapper = client.make(
            game_id="bt11-fd9df0622a1a", scorecard_id="test-scorecard-2"
        )

        self.assertIsNotNone(wrapper, "Wrapper should be created")
        self.assertEqual(wrapper.environment_info.game_id, "bt11-fd9df0622a1a")
        self.assertEqual(wrapper.scorecard_id, "test-scorecard-2")
        self.assertIsNotNone(wrapper.environment_info.local_dir)

    def test_make_bt11_reset(self):
        """Test that reset() works and returns FrameDataRaw."""
        client = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=self.environments_dir,
            logger=self.logger,
        )

        wrapper = client.make(game_id="bt11", scorecard_id="test-reset")

        self.assertIsNotNone(wrapper)

        # Test reset
        frame_data = wrapper.reset()
        self.assertIsNotNone(frame_data, "Reset should return FrameDataRaw")
        self.assertEqual(frame_data.game_id, "bt11-fd9df0622a1a")
        self.assertEqual(frame_data.state, GameState.NOT_FINISHED)

        # Check observation_space
        obs = wrapper.observation_space
        self.assertIsNotNone(obs)
        self.assertEqual(obs.game_id, "bt11-fd9df0622a1a")

    def test_make_bt11_four_action3_steps(self):
        """Test that four ACTION3 (move left) steps get past the first level."""
        client = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=self.environments_dir,
            logger=self.logger,
        )

        wrapper = client.make(game_id="bt11", scorecard_id="test-action3")

        self.assertIsNotNone(wrapper)

        # Reset the game
        reset_frame = wrapper.reset()
        self.assertIsNotNone(reset_frame)
        self.assertEqual(reset_frame.state, GameState.NOT_FINISHED)
        initial_level = reset_frame.levels_completed

        # Perform four ACTION3 (move left) actions
        for i in range(4):
            frame_data = wrapper.step(GameAction.ACTION3)
            self.assertIsNotNone(frame_data, f"Step {i + 1} should return FrameDataRaw")
            self.logger.info(
                f"Step {i + 1}: state={frame_data.state}, level={frame_data.levels_completed}"
            )

        # After 4 ACTION3 steps, should have advanced to next level
        # Score should have increased (level completion increases score)
        final_frame = wrapper.observation_space
        self.assertIsNotNone(final_frame)
        self.assertGreater(
            final_frame.levels_completed,
            initial_level,
            "Score should increase after completing first level",
        )
        self.assertNotEqual(
            final_frame.state,
            GameState.GAME_OVER,
            "Game should not be over after 4 ACTION3 steps",
        )

        # Verify we can see the action space
        action_space = wrapper.action_space
        self.assertGreater(len(action_space), 0, "Action space should have actions")
        self.assertIn(GameAction.ACTION3, action_space, "ACTION3 should be available")

    def test_make_invalid_game_id(self):
        """Test that invalid game_id format returns None."""
        client = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=self.environments_dir,
            logger=self.logger,
        )

        wrapper = client.make(game_id="invalid", scorecard_id="test")
        self.assertIsNone(wrapper, "Invalid game_id should return None")

    def test_make_game_not_found(self):
        """Test that non-existent game returns None."""
        client = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=self.environments_dir,
            logger=self.logger,
        )

        wrapper = client.make(game_id="xxxx", scorecard_id="test")
        self.assertIsNone(wrapper, "Non-existent game should return None")

    def test_make_with_wrong_version(self):
        """Test that wrong version returns None."""
        client = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=self.environments_dir,
            logger=self.logger,
        )

        wrapper = client.make(game_id="bt11-wrongversion", scorecard_id="test")
        self.assertIsNone(wrapper, "Wrong version should return None")

    def test_make_bt11_fd9df0622a1b_with_action6(self):
        """Test that bt11-fd9df0622a1b loads and four ACTION6 (GLICK) actions with x=1, y=1 get past the first level."""
        client = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=self.environments_dir,
            logger=self.logger,
        )

        wrapper = client.make(game_id="bt11-fd9df0622a1b", scorecard_id="test-action6")

        self.assertIsNotNone(wrapper, "Wrapper should be created")
        self.assertEqual(wrapper.environment_info.game_id, "bt11-fd9df0622a1b")
        self.assertEqual(wrapper.scorecard_id, "test-action6")
        self.assertIsNotNone(wrapper.environment_info.local_dir)

        # Reset the game
        reset_frame = wrapper.reset()
        self.assertIsNotNone(reset_frame)
        self.assertEqual(reset_frame.state, GameState.NOT_FINISHED)
        initial_level = reset_frame.levels_completed

        # Perform four ACTION6 (GLICK) actions with x=1, y=1
        for i in range(4):
            frame_data = wrapper.step(GameAction.ACTION6, data={"x": 1, "y": 1})
            self.assertIsNotNone(frame_data, f"Step {i + 1} should return FrameDataRaw")
            self.logger.info(
                f"Step {i + 1}: state={frame_data.state}, level={frame_data.levels_completed}"
            )

        # After 4 ACTION6 steps, should have advanced to next level
        # Score should have increased (level completion increases score)
        final_frame = wrapper.observation_space
        self.assertIsNotNone(final_frame)
        self.assertGreater(
            final_frame.levels_completed,
            initial_level,
            "Score should increase after completing first level",
        )
        self.assertNotEqual(
            final_frame.state,
            GameState.GAME_OVER,
            "Game should not be over after 4 ACTION6 steps",
        )

        # Verify we can see the action space
        action_space = wrapper.action_space
        self.assertGreater(len(action_space), 0, "Action space should have actions")
        self.assertIn(GameAction.ACTION6, action_space, "ACTION6 should be available")


if __name__ == "__main__":
    unittest.main()
