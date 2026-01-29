"""Local environment wrapper for ARC-AGI-3 environments."""

import importlib.util
import inspect
import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Optional, Type, cast

from arcengine import ARCBaseGame, FrameDataRaw, GameAction

from .models import EnvironmentInfo
from .wrapper import EnvironmentWrapper


class LocalEnvironmentWrapper(EnvironmentWrapper):
    """Wrapper for running ARC-AGI-3 environments locally.

    This wrapper dynamically loads and instantiates game classes from local files.
    """

    def __init__(
        self,
        environment_info: EnvironmentInfo,
        logger: logging.Logger,
        scorecard_id: str,
        seed: int = 0,
        save_recording: bool = False,
        recordings_dir: str = "recordings",
        scorecard_manager: Optional[Any] = None,
        renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
    ) -> None:
        """Initialize the local environment wrapper.

        Args:
            environment_info: Information about the environment.
            logger: Logger instance for logging.
            scorecard_id: Scorecard ID for tracking runs.
            save_recording: Whether to save recordings to JSONL file.
            recordings_dir: Directory to save recordings.
            scorecard_manager: Optional scorecard manager for tracking.
            renderer: Optional callable that accepts FrameDataRaw and performs custom rendering.
        """
        super().__init__(
            environment_info,
            logger,
            scorecard_id,
            save_recording,
            recordings_dir,
            scorecard_manager,
            renderer,
        )

        # Generate UUID for guid (local environments don't get guid from API)
        self._guid = str(uuid.uuid4())

        # Setup recording file now that guid is set
        if self.save_recording:
            self._setup_recording_file()

        self._game: Optional[ARCBaseGame] = None
        self._game_class: Optional[Type[ARCBaseGame]] = None

        # Load the game class
        if self.environment_info.local_dir is None:
            self.logger.error(
                f"Cannot load local environment {self.environment_info.game_id}: "
                "local_dir is None"
            )
            return

        self._load_game_class(seed)
        self.reset()

    def _load_game_class(self, seed: int = 0) -> None:
        """Dynamically load the game class from the local directory."""
        if self.environment_info.local_dir is None:
            return

        local_dir = Path(self.environment_info.local_dir)
        class_name = self.environment_info.class_name

        if not class_name:
            self.logger.error(
                f"Cannot load game class: class_name is not set for {self.environment_info.game_id}"
            )
            return

        # Find the Python file (try both class_name and lowercase version)
        candidates = [
            local_dir / f"{class_name.lower()}.py",
            local_dir / f"{class_name}.py",
        ]

        game_file = next((p for p in candidates if p.exists()), None)
        if game_file is None:
            self.logger.error(
                f"Game source file not found. Looked in: {', '.join(str(p) for p in candidates)}"
            )
            return

        try:
            # Read source code
            source_code = game_file.read_text(encoding="utf-8")
        except Exception as e:
            self.logger.exception(f"Failed to read game source from {game_file}: {e}")
            return

        # Execute the source code in an in-memory module
        module_name = f"arc_agi_3.{self.environment_info.game_id}"
        spec = importlib.util.spec_from_loader(module_name, loader=None)
        if spec is None:
            self.logger.error(f"Could not create module spec for {module_name}")
            return

        module = importlib.util.module_from_spec(spec)
        try:
            exec(source_code, module.__dict__)
        except Exception as e:
            self.logger.exception(
                f"Error executing game source for {self.environment_info.game_id}: {e}"
            )
            return

        # Get the class from the module
        cls: Any | None = getattr(module, class_name, None)
        if cls is None or not isinstance(cls, type):
            self.logger.error(f"Expected class `{class_name}` not found in {game_file}")
            return

        if not issubclass(cls, ARCBaseGame):
            self.logger.error(
                f"Class `{class_name}` exists but is not a subclass of ARCBaseGame"
            )
            return

        sig = inspect.signature(cls)
        if seed is not None and "seed" in sig.parameters:
            kwargs = {"seed": seed}
        else:
            kwargs = {}

        self._game = cls(**kwargs)
        self.logger.info(
            f"Successfully loaded game class {class_name} from {game_file}"
        )

    def reset(self) -> Optional[FrameDataRaw]:
        """Reset the environment and return the initial frame data.

        Returns:
            FrameDataRaw object with initial game state, or None if reset failed.
        """
        if self._game is None:
            self.logger.error("Cannot reset: game not loaded")
            return None

        try:
            from arcengine import ActionInput

            # Perform reset action and get frame data
            reset_action = ActionInput(id=GameAction.RESET)
            frame_data = cast(
                FrameDataRaw, self._game.perform_action(reset_action, raw=True)
            )
            # Set guid in frame_data for local environments
            frame_data.guid = self._guid
            frame_data.game_id = self.environment_info.game_id
            self._set_last_response(frame_data)
            return frame_data

        except Exception as e:
            self.logger.exception(
                f"Error resetting game {self.environment_info.game_id}: {e}"
            )
            return None

    def step(
        self,
        action: GameAction,
        data: Optional[dict[str, Any]] = None,
        reasoning: Optional[dict[str, Any]] = None,
    ) -> Optional[FrameDataRaw]:
        """Perform a step in the environment.

        Args:
            action: The game action to perform.
            data: Optional action data dictionary.
            reasoning: Optional reasoning dictionary.

        Returns:
            FrameDataRaw object with updated game state, or None if step failed.
        """
        if self._game is None:
            self.logger.error("Cannot step: game not initialized. Call reset() first.")
            return None

        try:
            from arcengine import ActionInput

            # Create ActionInput from GameAction with data
            action_input = ActionInput(id=action, data=data or {}, reasoning=reasoning)

            # Perform the action
            frame_data = cast(
                FrameDataRaw, self._game.perform_action(action_input, raw=True)
            )
            # Set guid in frame_data for local environments
            frame_data.guid = self._guid
            frame_data.game_id = self.environment_info.game_id
            self._set_last_response(frame_data, reasoning=reasoning)
            return frame_data

        except Exception as e:
            self.logger.exception(
                f"Error performing step with action {action.name}: {e}"
            )
            return None
