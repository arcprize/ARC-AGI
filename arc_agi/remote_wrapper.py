"""Remote environment wrapper for ARC-AGI-3 environments."""

import json
import logging
import threading
from typing import Any, Callable, Optional

import numpy as np
import requests
from arcengine import FrameData, FrameDataRaw, GameAction
from requests.cookies import RequestsCookieJar

from .models import EnvironmentInfo
from .wrapper import EnvironmentWrapper


class RemoteEnvironmentWrapper(EnvironmentWrapper):
    """Wrapper for running ARC-AGI-3 environments remotely via API.

    This wrapper makes HTTP requests to the ARC-AGI-3 API to interact with
    environments that are hosted remotely.
    """

    def __init__(
        self,
        base_url: str,
        environment_info: EnvironmentInfo,
        arc_api_key: str,
        logger: logging.Logger,
        scorecard_id: str,
        save_recording: bool = False,
        recordings_dir: str = "recordings",
        scorecard_manager: Optional[Any] = None,
        renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
        master_cookie_jar: Optional[RequestsCookieJar] = None,
        cookie_lock: Optional[threading.Lock] = None,
    ) -> None:
        """Initialize the remote environment wrapper.

        Args:
            base_url: Base URL for the ARC-AGI-3 API (e.g., "https://three.arcprize.org").
            environment_info: EnvironmentInfo object with game metadata.
            arc_api_key: API key for authentication.
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
        self.base_url = base_url
        self.arc_api_key = arc_api_key
        self.headers = {
            "X-API-Key": arc_api_key,
            "Accept": "application/json",
        }
        self._session = requests.Session()
        self._session.headers.update(self.headers)

        self._master_cookie_jar = (
            master_cookie_jar if master_cookie_jar is not None else RequestsCookieJar()
        )
        self._cookie_lock = cookie_lock if cookie_lock is not None else threading.Lock()

        self.reset()

    def reset(self) -> Optional[FrameDataRaw]:
        """Reset the environment and return the initial frame data.

        Returns:
            FrameDataRaw object with initial game state, or None if reset failed.
        """
        try:
            url = f"{self.base_url}/api/cmd/RESET"
            headers = {
                "X-Api-Key": self.arc_api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "card_id": self.scorecard_id,
                "game_id": self.environment_info.game_id,
            }
            if self._guid:
                payload["guid"] = self._guid

            with self._cookie_lock:
                self._session.cookies.update(self._master_cookie_jar)  # type: ignore[no-untyped-call]

            response = self._session.post(
                url, json=payload, headers=headers, timeout=10
            )

            with self._cookie_lock:
                self._master_cookie_jar.update(self._session.cookies)  # type: ignore[no-untyped-call]

            response.raise_for_status()
            response_data = response.json()

            # Convert API response to FrameDataRaw
            frame_data_raw = self._convert_to_frame_data_raw(response_data)
            if frame_data_raw:
                # Store guid from response
                self._guid = response_data.get("guid")
                # Setup recording file now that guid is set
                if self.save_recording and self._guid:
                    self._setup_recording_file()
                self._set_last_response(frame_data_raw)
                self.logger.info(
                    f"Successfully reset game {self.environment_info.game_id}, guid={self._guid}, scorecard_id={self.scorecard_id}"
                )
                return frame_data_raw

            return None

        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"Failed to reset game {self.environment_info.game_id}: {e}",
                exc_info=True,
            )
            return None
        except Exception as e:
            self.logger.exception(
                f"Unexpected error while resetting game {self.environment_info.game_id}: {e}"
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
            data: Optional action data dictionary (for complex actions, should contain "x" and "y").
            reasoning: Optional reasoning dictionary.

        Returns:
            FrameDataRaw object with updated game state, or None if step failed.
        """
        if self._guid is None:
            self.logger.error("Cannot step: game not reset. Call reset() first.")
            return None

        try:
            # Determine action endpoint
            if action == GameAction.RESET:
                action_name = "RESET"
            else:
                action_name = f"ACTION{action.value}"

            url = f"{self.base_url}/api/cmd/{action_name}"
            headers = {
                "X-Api-Key": self.arc_api_key,
                "Content-Type": "application/json",
            }

            # Build payload
            payload = {
                "game_id": self.environment_info.game_id,
                "guid": self._guid,
            }

            # Add x, y coordinates for complex actions
            if data:
                if "x" in data:
                    payload["x"] = data["x"]
                if "y" in data:
                    payload["y"] = data["y"]

            # Add reasoning if provided
            if reasoning:
                payload["reasoning"] = json.dumps(reasoning)

            with self._cookie_lock:
                self._session.cookies.update(self._master_cookie_jar)  # type: ignore[no-untyped-call]

            response = self._session.post(
                url, json=payload, headers=headers, timeout=10
            )

            with self._cookie_lock:
                self._master_cookie_jar.update(self._session.cookies)  # type: ignore[no-untyped-call]

            response.raise_for_status()
            response_data = response.json()

            # Convert API response to FrameDataRaw
            frame_data_raw = self._convert_to_frame_data_raw(response_data)
            if frame_data_raw:
                self._set_last_response(frame_data_raw, reasoning=reasoning)
                return frame_data_raw

            return None

        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"Failed to perform action {action.name} for game {self.environment_info.game_id}: {e}",
                exc_info=True,
            )
            return None
        except Exception as e:
            self.logger.exception(
                f"Unexpected error while performing action {action.name}: {e}"
            )
            return None

    def _convert_to_frame_data_raw(
        self, response_data: dict[str, Any]
    ) -> Optional[FrameDataRaw]:
        """Convert API response dictionary to FrameDataRaw.

        Args:
            response_data: Dictionary from API response.

        Returns:
            FrameDataRaw object if successful, None otherwise.
        """
        try:
            # First, try to parse as FrameData (Pydantic model)
            frame_data = FrameData.model_validate(response_data)

            # Convert FrameData to FrameDataRaw
            frame_data_raw = FrameDataRaw()
            frame_data_raw.game_id = frame_data.game_id
            # Convert frame from list of lists of lists to list of ndarrays
            frame_data_raw.frame = [
                np.array(frame_layer, dtype=np.int8) for frame_layer in frame_data.frame
            ]
            frame_data_raw.state = frame_data.state
            frame_data_raw.levels_completed = frame_data.levels_completed
            frame_data_raw.win_levels = frame_data.win_levels
            frame_data_raw.action_input = frame_data.action_input
            frame_data_raw.guid = frame_data.guid
            frame_data_raw.full_reset = getattr(frame_data, "full_reset", False)
            frame_data_raw.available_actions = frame_data.available_actions

            return frame_data_raw

        except Exception as e:
            self.logger.error(
                f"Failed to convert API response to FrameDataRaw: {e}",
                exc_info=True,
            )
            return None
