"""Environment wrapper for ARC-AGI-3 environments."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from arcengine import FrameDataRaw, GameAction

from .models import EnvironmentInfo
from .scorecard import ScorecardManager


class EnvironmentWrapper:
    """Base wrapper class for ARC-AGI-3 environments.

    This class provides a common interface for interacting with environments,
    whether they are local or remote. Subclasses should implement the `reset`
    and `step` methods to provide environment-specific behavior.
    """

    def __init__(
        self,
        environment_info: EnvironmentInfo,
        logger: logging.Logger,
        scorecard_id: str,
        save_recording: bool = False,
        recordings_dir: str = "recordings",
        scorecard_manager: Optional[ScorecardManager] = None,
        renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
    ) -> None:
        """Initialize the environment wrapper.

        Args:
            environment_info: Information about the environment.
            logger: Logger instance for logging.
            scorecard_id: Optional scorecard ID for tracking runs.
            save_recording: Whether to save recordings to JSONL file.
            recordings_dir: Directory to save recordings.
            scorecard_manager: Optional scorecard manager for tracking.
            renderer: Optional callable that accepts FrameDataRaw and performs custom rendering.
        """
        self.environment_info = environment_info
        self.logger = logger
        self.scorecard_id = scorecard_id
        self.save_recording = save_recording
        self.recordings_dir = recordings_dir
        self.scorecard_manager = scorecard_manager
        self.renderer = renderer
        self._last_response: Optional[FrameDataRaw] = None
        self._guid: Optional[str] = None
        self._recording_filename: Optional[Path] = None
        self._steps: int = 0
        # Note: _setup_recording_file() should be called after guid is set

    def reset(self) -> Optional[FrameDataRaw]:
        """Reset the environment.

        This method should be overridden by subclasses to provide
        environment-specific reset behavior.
        """
        return None

    def step(
        self,
        action: GameAction,
        data: Optional[dict[str, Any]] = None,
        reasoning: Optional[dict[str, Any]] = None,
    ) -> Optional[FrameDataRaw]:
        """Perform a step in the environment.

        This method should be overridden by subclasses to provide
        environment-specific step behavior.
        """
        return None

    def _setup_recording_file(self) -> None:
        """Set up the recording file path for JSONL output."""
        if not self._guid:
            self.logger.warning("Cannot setup recording file: guid not set")
            return

        try:
            # Create directory structure: {recordings_dir}/{scorecard_id}/
            recording_dir = Path(self.recordings_dir) / self.scorecard_id
            recording_dir.mkdir(parents=True, exist_ok=True)

            # Create filename: {game_id}-{guid}.jsonl
            filename = f"{self.environment_info.game_id}-{self._guid}.jsonl"
            self._recording_filename = recording_dir / filename

            self.logger.info(f"Recording to {self._recording_filename}")

        except Exception as e:
            self.logger.error(
                f"Failed to setup recording file: {e}",
                exc_info=True,
            )
            self._recording_filename = None

    def _record(self, data: dict[str, Any]) -> None:
        """Records an event to the file.

        Args:
            data: Dictionary (JSON-serializable) to record.
        """
        if not self.save_recording or not self._recording_filename:
            return

        try:
            event: dict[str, Any] = {}
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
            event["data"] = data

            with open(self._recording_filename, "a", encoding="utf-8") as f:
                json.dump(event, f)
                f.write("\n")

        except Exception as e:
            self.logger.error(
                f"Failed to write to recording file: {e}",
                exc_info=True,
            )

    def _set_last_response(
        self, resp: FrameDataRaw, reasoning: Optional[dict[str, Any]] = None
    ) -> None:
        """Set the last response from the environment.

        Args:
            resp: The FrameDataRaw response from the environment.
            reasoning: Optional reasoning dictionary to include in recording.
        """
        self._last_response = resp

        # Save to recording file if enabled
        if self.save_recording:
            # Convert FrameDataRaw to JSON-serializable dict
            data: dict[str, Any] = {
                "game_id": resp.game_id,
                "frame": [
                    frame_layer.tolist()
                    if hasattr(frame_layer, "tolist")
                    else frame_layer
                    for frame_layer in resp.frame
                ],
                "state": resp.state.name
                if hasattr(resp.state, "name")
                else str(resp.state),
                "levels_completed": resp.levels_completed,
                "win_levels": resp.win_levels,
                "action_input": {
                    "id": resp.action_input.id.name
                    if hasattr(resp.action_input.id, "name")
                    else str(resp.action_input.id),
                    "data": resp.action_input.data,
                    "reasoning": reasoning
                    if reasoning
                    else resp.action_input.reasoning,
                }
                if resp.action_input
                else None,
                "guid": resp.guid,
                "full_reset": getattr(resp, "full_reset", False),
                "available_actions": resp.available_actions,
            }

            self._record(data)

        # Render frames if renderer is set
        self._steps += 1
        if self.renderer is not None and resp.frame:
            try:
                self.renderer(self._steps, resp)
            except Exception as e:
                self.logger.error(
                    f"Failed to render frames: {e}",
                    exc_info=True,
                )

        # Update scorecard if manager is available
        if self.scorecard_manager and resp.guid:
            try:
                # Register guid with scorecard if not already registered
                self.scorecard_manager.add_game(self.scorecard_id, resp.guid)

                # Update scorecard
                self.scorecard_manager.update_scorecard(
                    resp.guid, resp, resp.full_reset
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to update scorecard: {e}",
                    exc_info=True,
                )

    @property
    def observation_space(self) -> Optional[FrameDataRaw]:
        """Get the observation space (last response data).

        Returns:
            The FrameDataRaw object from the last response, or None if no
            response has been set yet.
        """
        return self._last_response

    @property
    def action_space(self) -> list[GameAction]:
        """Get the action space (available actions).

        Returns:
            A list of GameAction objects converted from the available_actions
            in the last response. Returns an empty list if no response has
            been set yet or if available_actions is empty.
        """
        if self._last_response is None or not self._last_response.available_actions:
            return []

        return [
            GameAction.from_id(action_id)
            for action_id in self._last_response.available_actions
        ]

    @property
    def info(self) -> EnvironmentInfo:
        """Get the environment information.

        Returns:
            The EnvironmentInfo object for this environment.
        """
        return self.environment_info
