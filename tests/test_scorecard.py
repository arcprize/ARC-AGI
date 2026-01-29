"""Tests for scorecard functionality using unittest."""

import logging
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Create a mock dotenv module before any imports
_mock_dotenv = MagicMock()
_mock_dotenv.load_dotenv = MagicMock()
sys.modules["dotenv"] = _mock_dotenv

# Now import arcagi3 - the mock will be used instead of real dotenv
from arcengine import GameAction, GameState  # noqa: E402

from arc_agi import (  # noqa: E402
    Arcade,
    EnvironmentInfo,
    EnvironmentScore,
    EnvironmentScoreCalculator,
    EnvironmentScorecard,
    OperationMode,  # noqa: E402
)


class TestScorecard(unittest.TestCase):
    """Test scorecard functionality."""

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

    def test_scorecard_bt11_four_action3(self):
        """Test that playing bt11 with 4 Action3 actions results in levels_completed = 1."""
        client = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=self.environments_dir,
            logger=self.logger,
        )

        # Create a scorecard
        scorecard_id = client.create_scorecard()
        self.assertIsNotNone(scorecard_id)
        self.logger.info(f"Created scorecard: {scorecard_id}")

        # Make the environment
        wrapper = client.make(game_id="bt11", scorecard_id=scorecard_id)
        self.assertIsNotNone(wrapper)

        # Reset the game
        self.assertIsNotNone(wrapper.observation_space)
        self.assertEqual(wrapper.observation_space.state, GameState.NOT_FINISHED)

        # Perform four ACTION3 (move left) actions
        for i in range(4):
            frame_data = wrapper.step(GameAction.ACTION3)
            self.assertIsNotNone(frame_data, f"Step {i + 1} should return FrameDataRaw")
            self.logger.info(
                f"Step {i + 1}: state={frame_data.state}, level={frame_data.levels_completed}"
            )

        # Get the scorecard and verify levels_completed
        scorecard = client.get_scorecard(scorecard_id)
        self.assertIsNotNone(scorecard)

        # Get the card for bt11
        bt11_card = scorecard.environments[0]
        self.assertEqual(bt11_card.id, "bt11-fd9df0622a1a")

        # Verify levels_completed is 1
        # The card should have one guid (one play)
        self.assertEqual(4, bt11_card.actions)

        # Check levels_completed for this guid
        self.assertEqual(
            bt11_card.levels_completed,
            1,
            "levels_completed should be 1 after completing first level",
        )

        # Verify the final frame also shows level 1
        final_frame = wrapper.observation_space
        self.assertIsNotNone(final_frame)
        self.assertEqual(
            final_frame.levels_completed,
            1,
            "Final frame should show levels_completed = 1",
        )


class TestEnvironmentScore(unittest.TestCase):
    """Test EnvironmentScore and EnvironmentScoreCalculator."""

    def test_environment_score_creation(self):
        """Test that EnvironmentScore can be created with all fields."""
        score = EnvironmentScore(
            id="test-id",
            score=85.5,
            levels_completed=3,
            actions=42,
            resets=2,
            completed=True,
            message="Test message",
        )
        self.assertEqual(score.id, "test-id")
        self.assertEqual(score.score, 85.5)
        self.assertEqual(score.levels_completed, 3)
        self.assertEqual(score.actions, 42)
        self.assertEqual(score.resets, 2)
        self.assertEqual(score.completed, True)
        self.assertEqual(score.message, "Test message")

    def test_environment_score_optional_fields(self):
        """Test that EnvironmentScore optional fields work correctly."""
        # Test with all optional fields None
        score = EnvironmentScore(
            id="test-id",
            score=50.0,
            levels_completed=1,
            actions=10,
        )
        self.assertIsNone(score.resets)
        self.assertIsNone(score.completed)
        self.assertIsNone(score.message)

        # Test with resets but no completed
        score2 = EnvironmentScore(
            id="test-id-2",
            score=75.0,
            levels_completed=2,
            actions=20,
            resets=1,
        )
        self.assertEqual(score2.resets, 1)
        self.assertIsNone(score2.completed)

        # Test with completed but no resets
        score3 = EnvironmentScore(
            id="test-id-3",
            score=90.0,
            levels_completed=3,
            actions=30,
            completed=False,
        )
        self.assertIsNone(score3.resets)
        self.assertEqual(score3.completed, False)

    def test_environment_score_calculator_initialization(self):
        """Test that EnvironmentScoreCalculator initializes correctly."""
        calculator = EnvironmentScoreCalculator(id="test-id", resets=2)
        self.assertEqual(calculator.id, "test-id")
        self.assertEqual(calculator.resets, 2)
        self.assertEqual(calculator.level_scores, [])
        self.assertEqual(calculator.levels_completed, 0)
        self.assertEqual(calculator.actions, 0)
        self.assertIsNone(calculator.completed)

    def test_environment_score_calculator_optional_resets(self):
        """Test that EnvironmentScoreCalculator can be initialized without resets."""
        calculator = EnvironmentScoreCalculator(id="test-id")
        self.assertEqual(calculator.id, "test-id")
        self.assertIsNone(calculator.resets)

    def test_add_level_completed(self):
        """Test add_level with completed=True calculates score correctly."""
        calculator = EnvironmentScoreCalculator(id="test-id", resets=0)

        # Baseline: 10 actions, taken: 5 actions -> score = (10/5) * 100 = 200, capped at 100
        calculator.add_level(completed=True, actions_taken=5, baseline_actions=10)
        self.assertEqual(calculator.levels_completed, 1)
        self.assertEqual(calculator.actions, 5)
        self.assertEqual(len(calculator.level_scores), 1)
        self.assertEqual(calculator.level_scores[0], 100.0)  # Capped at 100

    def test_add_level_completed_exact_baseline(self):
        """Test add_level with actions_taken equal to baseline."""
        calculator = EnvironmentScoreCalculator(id="test-id", resets=0)

        # Baseline: 10 actions, taken: 10 actions -> score = (10/10) * 100 = 100
        calculator.add_level(completed=True, actions_taken=10, baseline_actions=10)
        self.assertEqual(calculator.levels_completed, 1)
        self.assertEqual(calculator.actions, 10)
        self.assertEqual(calculator.level_scores[0], 100.0)

    def test_add_level_completed_below_baseline(self):
        """Test add_level with actions_taken below baseline."""
        calculator = EnvironmentScoreCalculator(id="test-id", resets=0)

        # Baseline: 10 actions, taken: 8 actions -> score = (10/8) * 100 = 125, capped at 100
        calculator.add_level(completed=True, actions_taken=8, baseline_actions=10)
        self.assertEqual(calculator.level_scores[0], 100.0)  # Capped at 100

    def test_add_level_completed_above_baseline(self):
        """Test add_level with actions_taken above baseline."""
        calculator = EnvironmentScoreCalculator(id="test-id", resets=0)

        # Baseline: 10 actions, taken: 20 actions -> score = (10/20) * 100 = 50
        calculator.add_level(completed=True, actions_taken=20, baseline_actions=10)
        self.assertEqual(calculator.level_scores[0], 50.0)

    def test_add_level_not_completed(self):
        """Test add_level with completed=False appends 0."""
        calculator = EnvironmentScoreCalculator(id="test-id", resets=0)

        calculator.add_level(completed=False, actions_taken=15, baseline_actions=10)
        self.assertEqual(calculator.levels_completed, 0)  # Not incremented
        self.assertEqual(calculator.actions, 15)  # Still added to total
        self.assertEqual(len(calculator.level_scores), 1)
        self.assertEqual(calculator.level_scores[0], 0.0)

    def test_add_level_zero_actions(self):
        """Test add_level with zero actions_taken."""
        calculator = EnvironmentScoreCalculator(id="test-id", resets=0)

        calculator.add_level(completed=True, actions_taken=0, baseline_actions=10)
        self.assertEqual(calculator.levels_completed, 1)
        self.assertEqual(calculator.actions, 0)
        self.assertEqual(
            calculator.level_scores[0], 0.0
        )  # Should be 0 if actions_taken is 0

    def test_add_level_multiple_levels(self):
        """Test adding multiple levels."""
        calculator = EnvironmentScoreCalculator(id="test-id", resets=0)

        # Level 1: completed with 8 actions (baseline 10) -> score = 125, capped at 100
        calculator.add_level(completed=True, actions_taken=8, baseline_actions=10)

        # Level 2: completed with 12 actions (baseline 10) -> score = (10/12) * 100 = 83.33...
        calculator.add_level(completed=True, actions_taken=12, baseline_actions=10)

        # Level 3: not completed
        calculator.add_level(completed=False, actions_taken=5, baseline_actions=10)

        self.assertEqual(calculator.levels_completed, 2)
        self.assertEqual(calculator.actions, 25)  # 8 + 12 + 5
        self.assertEqual(len(calculator.level_scores), 3)
        self.assertEqual(calculator.level_scores[0], 100.0)
        self.assertAlmostEqual(calculator.level_scores[1], 83.33333333333333, places=5)
        self.assertEqual(calculator.level_scores[2], 0.0)

    def test_to_score_average(self):
        """Test that to_score calculates average of level_scores."""
        calculator = EnvironmentScoreCalculator(id="test-id", resets=2)

        calculator.add_level(
            completed=True, actions_taken=10, baseline_actions=10
        )  # score = 100
        calculator.add_level(
            completed=True, actions_taken=20, baseline_actions=10
        )  # score = 50
        calculator.add_level(
            completed=False, actions_taken=5, baseline_actions=10
        )  # score = 0
        calculator.completed = True  # Set completed flag

        score = calculator.to_score()
        self.assertIsInstance(score, EnvironmentScore)
        self.assertEqual(score.id, "test-id")
        self.assertEqual(score.resets, 2)
        self.assertEqual(score.completed, True)
        self.assertEqual(score.levels_completed, 2)
        self.assertEqual(score.actions, 35)  # 10 + 20 + 5
        # Average: (100 + 50 + 0) / 3 = 50.0
        self.assertAlmostEqual(score.score, 50.0, places=5)

    def test_to_score_empty_levels(self):
        """Test to_score with no levels added."""
        calculator = EnvironmentScoreCalculator(id="test-id")

        score = calculator.to_score()
        self.assertEqual(score.id, "test-id")
        self.assertEqual(score.score, 0.0)
        self.assertEqual(score.levels_completed, 0)
        self.assertEqual(score.actions, 0)
        self.assertIsNone(score.resets)
        self.assertIsNone(score.completed)

    def test_to_score_single_level(self):
        """Test to_score with single level."""
        calculator = EnvironmentScoreCalculator(id="test-id", resets=1)

        calculator.add_level(completed=True, actions_taken=15, baseline_actions=10)
        calculator.completed = False  # Set completed flag

        score = calculator.to_score()
        self.assertEqual(
            score.score, (10 / 15) * 100
        )  # Should be exact value, not average of one
        self.assertEqual(score.levels_completed, 1)
        self.assertEqual(score.actions, 15)
        self.assertEqual(score.resets, 1)
        self.assertEqual(score.completed, False)


class TestEnvironmentScorecard(unittest.TestCase):
    """Test EnvironmentScorecard functionality."""

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

    def tearDown(self):
        """Clean up after tests."""
        for var in self.env_vars_to_clear:
            os.environ.pop(var, None)
        os.environ["ARC_API_KEY"] = "test-key-123"

    def test_from_scorecard_basic(self):
        """Test basic EnvironmentScorecard creation."""
        from arc_agi.scorecard import Card, Scorecard

        # Create a simple scorecard with one game
        card = Card(
            game_id="bt11",
            total_plays=1,
            guids=["guid1"],
            levels_completed=[1],
            actions=[10],
            resets=[0],
            states=[GameState.WIN],
            actions_by_level=[[(1, 10)]],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11": card},
        )

        env_info = EnvironmentInfo(
            game_id="bt11",
            title="BT11",
            baseline_actions=[10],
            tags=["test"],
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(scorecard, [env_info])

        self.assertEqual(scorecard_result.card_id, "test-card")
        self.assertEqual(scorecard_result.api_key, "test-key")
        self.assertEqual(len(scorecard_result.environments), 1)
        self.assertEqual(scorecard_result.environments[0].id, "bt11")
        self.assertEqual(scorecard_result.environments[0].levels_completed, 1)
        # Score should be (10/10) * 100 = 100
        self.assertAlmostEqual(scorecard_result.environments[0].score, 100.0, places=5)
        self.assertEqual(scorecard_result.score, 100.0)  # Average of one score

    def test_from_scorecard_highest_levels_completed(self):
        """Test that only the play with highest levels_completed is used."""
        from arc_agi.scorecard import Card, Scorecard

        # Create a card with multiple plays, where second has higher levels_completed
        card = Card(
            game_id="bt11",
            total_plays=2,
            guids=["guid1", "guid2"],
            levels_completed=[1, 2],  # guid2 has higher levels_completed
            actions=[10, 20],
            resets=[0, 0],
            states=[GameState.WIN, GameState.WIN],
            actions_by_level=[[(1, 10)], [(1, 10), (2, 20)]],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11": card},
        )

        env_info = EnvironmentInfo(
            game_id="bt11",
            title="BT11",
            baseline_actions=[10, 15],
            tags=["test"],
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(scorecard, [env_info])
        # Should only have one environment score (for guid2)
        self.assertEqual(len(scorecard_result.environments), 1)
        self.assertEqual(scorecard_result.environments[0].id, "bt11")
        self.assertEqual(scorecard_result.environments[0].levels_completed, 2)
        self.assertEqual(scorecard_result.environments[0].runs[1].guid, "guid2")

    def test_from_scorecard_multiple_games(self):
        """Test EnvironmentScorecard with multiple games."""
        from arc_agi.scorecard import Card, Scorecard

        card1 = Card(
            game_id="bt11",
            total_plays=1,
            guids=["guid1"],
            levels_completed=[1],
            actions=[10],
            resets=[0],
            states=[GameState.WIN],
            actions_by_level=[[(1, 10)]],
        )

        card2 = Card(
            game_id="am92",
            total_plays=1,
            guids=["guid2"],
            levels_completed=[2],
            actions=[30],
            resets=[1],
            states=[GameState.WIN],
            actions_by_level=[[(1, 15), (2, 30)]],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11": card1, "am92": card2},
        )

        env_info1 = EnvironmentInfo(
            game_id="bt11",
            title="BT11",
            baseline_actions=[10],
            tags=["tag1"],
        )

        env_info2 = EnvironmentInfo(
            game_id="am92",
            title="AM92",
            baseline_actions=[15, 20],
            tags=["tag2"],
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(
            scorecard, [env_info1, env_info2]
        )

        self.assertEqual(len(scorecard_result.environments), 2)
        # Find scores by id
        scores_by_id = {s.id: s for s in scorecard_result.environments}
        self.assertIn("bt11", scores_by_id)
        self.assertIn("am92", scores_by_id)

        # bt11 score: (10/10) * 100 = 100
        self.assertAlmostEqual(scores_by_id["bt11"].score, 100.0, places=5)
        # am92 score: average of level 1 ((15/15)*100=100) and level 2 ((20/15)*100=133.33, capped at 100)
        # Actually wait, let me recalculate: level 1 took 15 actions (baseline 15) = 100, level 2 took 15 actions (baseline 20) = (20/15)*100 = 133.33 capped at 100
        # So average = (100 + 100) / 2 = 100
        self.assertAlmostEqual(scores_by_id["am92"].score, 100.0, places=5)

        # Average score should be (100 + 100) / 2 = 100
        self.assertAlmostEqual(scorecard_result.score, 100.0, places=5)

    def test_from_scorecard_missing_baseline_actions(self):
        """Test handling of missing baseline_actions."""
        from arc_agi.scorecard import Card, Scorecard

        card = Card(
            game_id="bt11",
            total_plays=1,
            guids=["guid1"],
            levels_completed=[1],
            actions=[10],
            resets=[0],
            states=[GameState.WIN],
            actions_by_level=[[(1, 10)]],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11": card},
        )

        # EnvironmentInfo without baseline_actions
        env_info = EnvironmentInfo(
            game_id="bt11",
            title="BT11",
            baseline_actions=None,
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(scorecard, [env_info])

        self.assertEqual(len(scorecard_result.environments), 1)
        score = scorecard_result.environments[0]
        self.assertEqual(score.score, 0.0)
        self.assertEqual(
            score.runs[0].message,
            "Human baseline actions are not available for this environment",
        )
        self.assertEqual(score.levels_completed, 1)

    def test_from_scorecard_baseline_size_mismatch(self):
        """Test handling of baseline_actions size mismatch."""
        from arc_agi.scorecard import Card, Scorecard

        card = Card(
            game_id="bt11",
            total_plays=1,
            guids=["guid1"],
            levels_completed=[3],  # Completed 3 levels
            actions=[30],
            resets=[0],
            states=[GameState.WIN],
            actions_by_level=[[(1, 10), (2, 20), (3, 30)]],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11": card},
        )

        # EnvironmentInfo with fewer baseline_actions than levels_completed
        env_info = EnvironmentInfo(
            game_id="bt11",
            title="BT11",
            baseline_actions=[10, 15],  # Only 2 baselines, but 3 levels completed
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(scorecard, [env_info])

        self.assertEqual(len(scorecard_result.environments), 1)
        score = scorecard_result.environments[0]
        self.assertEqual(score.score, 0.0)
        self.assertEqual(score.runs[0].message, "Human baseline actions size mismatch")
        self.assertEqual(score.levels_completed, 3)

    def test_from_scorecard_tags_scores(self):
        """Test that tags_scores are computed correctly."""
        from arc_agi.scorecard import Card, Scorecard

        card1 = Card(
            game_id="bt11",
            total_plays=1,
            guids=["guid1"],
            levels_completed=[1],
            actions=[10],
            resets=[0],
            states=[GameState.WIN],
            actions_by_level=[[(1, 20)]],
        )

        card2 = Card(
            game_id="am92",
            total_plays=1,
            guids=["guid2"],
            levels_completed=[1],
            actions=[15],
            resets=[0],
            states=[GameState.WIN],
            actions_by_level=[[(1, 25)]],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11": card1, "am92": card2},
        )

        env_info1 = EnvironmentInfo(
            game_id="bt11",
            title="BT11",
            baseline_actions=[10],
            tags=["tag1", "shared"],  # Has shared tag
        )

        env_info2 = EnvironmentInfo(
            game_id="am92",
            title="AM92",
            baseline_actions=[15],
            tags=["tag2", "shared"],  # Also has shared tag
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(
            scorecard, [env_info1, env_info2]
        )

        # Should have tag scores for tag1, tag2, and shared
        self.assertGreater(len(scorecard_result.tags_scores), 0)
        tags_by_id = {s.id: s for s in scorecard_result.tags_scores}

        # Check that shared tag has aggregated scores from both games
        if "shared" in tags_by_id:
            shared_score = tags_by_id["shared"]
            # Should have 2 levels completed (one from each game)
            self.assertEqual(shared_score.levels_completed, 2)
            # Score should be average of both: bt11 (10/10)*100=100, am92 (15/15)*100=100, avg=100
            self.assertAlmostEqual(shared_score.score, 55.0, places=5)
        if "tag1" in tags_by_id:
            shared_score = tags_by_id["tag1"]
            # Should have 2 levels completed (one from each game)
            self.assertEqual(shared_score.levels_completed, 1)
            # Score should be average of both: bt11 (10/10)*100=100, am92 (15/15)*100=100, avg=100
            self.assertAlmostEqual(shared_score.score, 50.0, places=5)
        if "tag2" in tags_by_id:
            shared_score = tags_by_id["tag2"]
            # Should have 2 levels completed (one from each game)
            self.assertEqual(shared_score.levels_completed, 1)
            # Score should be average of both: bt11 (10/10)*100=100, am92 (15/15)*100=100, avg=100
            self.assertAlmostEqual(shared_score.score, 60.0, places=5)

    def test_not_completed_games(self):
        """Test that tags_scores are computed correctly."""
        from arc_agi.scorecard import Card, Scorecard

        card1 = Card(
            game_id="bt11",
            total_plays=1,
            guids=["guid1"],
            levels_completed=[1],
            actions=[1000],
            resets=[0],
            states=[GameState.GAME_OVER],
            actions_by_level=[[(1, 20)]],
        )

        card2 = Card(
            game_id="am92",
            total_plays=1,
            guids=["guid2"],
            levels_completed=[1],
            actions=[1000],
            resets=[0],
            states=[GameState.GAME_OVER],
            actions_by_level=[[(1, 25)]],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11": card1, "am92": card2},
        )

        env_info1 = EnvironmentInfo(
            game_id="bt11",
            title="BT11",
            baseline_actions=[10, 20],
            tags=["tag1", "shared"],  # Has shared tag
        )

        env_info2 = EnvironmentInfo(
            game_id="am92",
            title="AM92",
            baseline_actions=[15, 30, 45],
            tags=["tag2", "shared"],  # Also has shared tag
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(
            scorecard, [env_info1, env_info2]
        )

        # Should have tag scores for tag1, tag2, and shared
        self.assertGreater(len(scorecard_result.tags_scores), 0)
        tags_by_id = {s.id: s for s in scorecard_result.tags_scores}

        # Check that shared tag has aggregated scores from both games
        if "shared" in tags_by_id:
            shared_score = tags_by_id["shared"]
            # Should have 2 levels completed (one from each game)
            self.assertEqual(shared_score.levels_completed, 2)
            # Score should be average of both: bt11 (10/10)*100=100, am92 (15/15)*100=100, avg=100
            self.assertAlmostEqual(shared_score.score, 22.0, places=5)
            self.assertEqual(shared_score.number_of_levels, 5)
            self.assertEqual(shared_score.number_of_environments, 2)
        if "tag1" in tags_by_id:
            shared_score = tags_by_id["tag1"]
            # Should have 2 levels completed (one from each game)
            self.assertEqual(shared_score.levels_completed, 1)
            # Score should be average of both: bt11 (10/10)*100=100, am92 (15/15)*100=100, avg=100
            self.assertAlmostEqual(shared_score.score, 25.0, places=5)
            self.assertEqual(shared_score.number_of_levels, 2)
            self.assertEqual(shared_score.number_of_environments, 1)
        if "tag2" in tags_by_id:
            shared_score = tags_by_id["tag2"]
            # Should have 2 levels completed (one from each game)
            self.assertEqual(shared_score.levels_completed, 1)
            # Score should be average of both: bt11 (10/10)*100=100, am92 (15/15)*100=100, avg=100
            self.assertAlmostEqual(shared_score.score, 20.0, places=5)
            self.assertEqual(shared_score.number_of_levels, 3)
            self.assertEqual(shared_score.number_of_environments, 1)

    def test_completed_games_average_score_calculation(self):
        """Test that top-level score is correctly calculated as average."""
        from arc_agi.scorecard import Card, Scorecard

        card1 = Card(
            game_id="bt11",
            total_plays=1,
            guids=["guid1"],
            levels_completed=[1],
            actions=[20],  # 20 actions for baseline of 10 = 50% score
            resets=[0],
            states=[GameState.WIN],
            actions_by_level=[[(1, 20)]],
        )

        card2 = Card(
            game_id="am92",
            total_plays=1,
            guids=["guid2"],
            levels_completed=[1],
            actions=[10],  # 10 actions for baseline of 10 = 100% score
            resets=[0],
            states=[GameState.WIN],
            actions_by_level=[[(1, 10)]],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11": card1, "am92": card2},
        )

        env_info1 = EnvironmentInfo(
            game_id="bt11",
            title="BT11",
            baseline_actions=[10],
        )

        env_info2 = EnvironmentInfo(
            game_id="am92",
            title="AM92",
            baseline_actions=[10],
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(
            scorecard, [env_info1, env_info2]
        )

        # bt11: (10/20) * 100 = 50
        # am92: (10/10) * 100 = 100
        # Average: (50 + 100) / 2 = 75
        self.assertAlmostEqual(scorecard_result.score, 75.0, places=5)

    def test_from_scorecard_empty_scorecard(self):
        """Test EnvironmentScorecard with empty scorecard."""
        from arc_agi.scorecard import Scorecard

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={},
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(scorecard, [])

        self.assertEqual(len(scorecard_result.environments), 0)
        self.assertEqual(len(scorecard_result.tags_scores), 0)
        self.assertEqual(scorecard_result.score, 0.0)

    def test_from_scorecard_no_matching_env_info(self):
        """Test EnvironmentScorecard when no matching EnvironmentInfo exists."""
        from arc_agi.scorecard import Card, Scorecard

        card = Card(
            game_id="bt11",
            total_plays=1,
            guids=["guid1"],
            levels_completed=[1],
            actions=[10],
            resets=[0],
            states=[GameState.WIN],
            actions_by_level=[[(1, 10)]],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11": card},
        )

        # No matching EnvironmentInfo
        scorecard_result = EnvironmentScorecard.from_scorecard(scorecard, [])

        self.assertEqual(len(scorecard_result.environments), 1)
        score = scorecard_result.environments[0]
        self.assertEqual(score.score, 0.0)
        self.assertEqual(
            score.runs[0].message,
            "No Matching EnvironmentInfo found for bt11",
        )

    def test_from_scorecard_multiple_plays_same_game(self):
        """Test that only best play is selected when multiple plays exist."""
        from arc_agi.scorecard import Card, Scorecard

        # Create card with 3 plays, middle one has highest levels_completed
        card = Card(
            game_id="bt11",
            total_plays=3,
            guids=["guid1", "guid2", "guid3"],
            levels_completed=[1, 3, 2],  # guid2 has highest (3)
            actions=[10, 30, 20],
            resets=[0, 0, 0],
            states=[GameState.WIN, GameState.WIN, GameState.WIN],
            actions_by_level=[
                [(1, 10)],
                [(1, 10), (2, 20), (3, 30)],
                [(1, 10), (2, 20)],
            ],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11": card},
        )

        env_info = EnvironmentInfo(
            game_id="bt11",
            title="BT11",
            baseline_actions=[10, 15, 20],
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(scorecard, [env_info])
        # Should only have one environment score (for guid2)
        self.assertEqual(len(scorecard_result.environments), 1)
        self.assertEqual(scorecard_result.environments[0].id, "bt11")
        self.assertEqual(scorecard_result.environments[0].levels_completed, 3)

    def test_realistic_scorecard_for_bt11(self):
        """Test that only best play is selected when multiple plays exist."""
        from arc_agi.scorecard import Card, Scorecard

        # Create card with 3 plays, middle one has highest levels_completed
        card = Card(
            game_id="bt11-fd9df0622a1a",
            total_plays=1,
            guids=["guid1"],
            levels_completed=[2],  # guid2 has highest (3)
            actions=[118],
            resets=[6],
            states=[GameState.NOT_FINISHED],
            actions_by_level=[[(1, 4), (2, 12)]],
        )

        scorecard = Scorecard(
            card_id="test-card",
            api_key="test-key",
            cards={"bt11-fd9df0622a1a": card},
        )

        env_info = EnvironmentInfo(
            game_id="bt11-fd9df0622a1a",
            title="BT11",
            tags=["tag1", "shared"],
            baseline_actions=[4, 8, 16, 20, 24],
        )

        scorecard_result = EnvironmentScorecard.from_scorecard(scorecard, [env_info])

        print(scorecard_result.model_dump_json())

        # Should only have one environment score (for guid2)
        self.assertEqual(len(scorecard_result.environments), 1)
        self.assertEqual(scorecard_result.environments[0].id, "bt11-fd9df0622a1a")
        self.assertEqual(scorecard_result.environments[0].levels_completed, 2)

        envs_by_id = {s.id: s for s in scorecard_result.environments}

        # Check that shared tag has aggregated scores from both games
        if "bt11-fd9df0622a1a" in envs_by_id:
            game_score = envs_by_id["bt11-fd9df0622a1a"]
            # Should have 2 levels completed (one from each game)
            self.assertEqual(game_score.levels_completed, 2)
            self.assertAlmostEqual(game_score.score, 40.0, places=5)
            self.assertEqual(game_score.actions, 118)
            self.assertEqual(game_score.resets, 6)
            self.assertEqual(game_score.completed, False)
        else:
            self.fail("bt11 environment not found")


if __name__ == "__main__":
    unittest.main()
