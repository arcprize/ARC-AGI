"""Base class for ARC-AGI-3 environments."""

import logging
import os
import sys
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import requests
from arcengine import FrameDataRaw
from dotenv import load_dotenv
from flask import Flask, Response
from pydantic import ValidationError

from .local_wrapper import LocalEnvironmentWrapper
from .models import EnvironmentInfo
from .remote_wrapper import RemoteEnvironmentWrapper
from .rendering import render_frames, render_frames_terminal
from .scorecard import EnvironmentScorecard, ScorecardManager
from .wrapper import EnvironmentWrapper

# Load environment variables from .env.example first, then .env (with override)
# Handle missing files and permission errors gracefully
try:
    load_dotenv(dotenv_path=".env.example")
except (OSError, PermissionError, FileNotFoundError):
    pass

try:
    load_dotenv(dotenv_path=".env", override=True)
except (OSError, PermissionError, FileNotFoundError):
    pass


class OperationMode(str, Enum):
    """Mode for environment discovery and usage.

    - NORMAL: Use both local environments and API (default).
    - ONLINE: Use only remote environments via API.
    - OFFLINE: Use only locally available environments.
    """

    NORMAL = "normal"
    ONLINE = "online"
    OFFLINE = "offline"


class Arcade:
    """Base class for ARC-AGI-3 environments.

    This class handles configuration loading from environment variables and
    constructor parameters. Environment variables are loaded from .env.example
    and .env files using python-dotenv.
    """

    def __init__(
        self,
        arc_api_key: str = "",
        arc_base_url: str = "https://three.arcprize.org",
        operation_mode: OperationMode = OperationMode.NORMAL,
        environments_dir: str = "environment_files",
        recordings_dir: str = "recordings",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Initialize ARCAGI3 instance.

        Args:
            arc_api_key: API key for ARC API. Defaults to empty string.
                Can be overridden by ARC_API_KEY environment variable.
            arc_base_url: Base URL for ARC API. Defaults to "https://three.arcprize.org".
                Can be overridden by ARC_BASE_URL environment variable.
            operation_mode: NORMAL (local + API), ONLINE (API only), or OFFLINE (local only).
                Defaults to NORMAL. Can be overridden by OPERATION_MODE env var
                ("normal", "online", "offline"), or by OFFLINE_ONLY/ONLINE_ONLY for backward compatibility.
            environments_dir: Directory to scan for metadata.json files. Defaults to "environment_files".
                Can be overridden by ENVIRONMENTS_DIR environment variable.
            recordings_dir: Directory to save recordings. Defaults to "recordings".
                Can be overridden by RECORDINGS_DIR environment variable.
            logger: Optional logger instance. Defaults to a logger that logs to STDOUT.
        """
        # Priority order: constructor args > env vars > defaults

        # arc_api_key: constructor arg > env var > default ""
        if arc_api_key != "":
            self.arc_api_key = arc_api_key
        else:
            self.arc_api_key = os.getenv("ARC_API_KEY", "")

        # arc_base_url: constructor arg > env var > default URL
        default_base_url = "https://three.arcprize.org"
        if arc_base_url != default_base_url:
            self.arc_base_url = arc_base_url
        else:
            self.arc_base_url = os.getenv("ARC_BASE_URL", default_base_url)

        # operation_mode: constructor arg > env var > default NORMAL
        if operation_mode != OperationMode.NORMAL:
            self.operation_mode: OperationMode = operation_mode
        else:
            self.operation_mode = self._parse_operation_mode_from_env()

        # environments_dir: constructor arg > env var > default
        default_environments_dir = "environment_files"
        if environments_dir != default_environments_dir:
            self.environments_dir = environments_dir
        else:
            self.environments_dir = os.getenv(
                "ENVIRONMENTS_DIR", default_environments_dir
            )

        # recordings_dir: constructor arg > env var > default
        default_recordings_dir = "recordings"
        if recordings_dir != default_recordings_dir:
            self.recordings_dir = recordings_dir
        else:
            self.recordings_dir = os.getenv("RECORDINGS_DIR", default_recordings_dir)

        # Set up logger - default to STDOUT if not provided
        if logger is not None:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
            # Remove existing handlers to avoid duplicates
            self.logger.handlers.clear()
            # Create STDOUT handler
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            stdout_handler.setFormatter(formatter)
            self.logger.addHandler(stdout_handler)

        # Create scorecard manager
        self.scorecard_manager = ScorecardManager()

        # Store default scorecard_id (will be created on first make() call if needed)
        self._default_scorecard_id: Optional[str] = None

        # Scan for available environments
        self.available_environments: list[EnvironmentInfo] = []
        self._scan_for_environments()

        if self.operation_mode == OperationMode.ONLINE:
            self.headers = {
                "X-API-Key": self.arc_api_key,
                "Accept": "application/json",
            }
            self._session = requests.Session()
            self._session.headers.update(self.headers)

        self._lock = threading.Lock()
        self._cookie_lock = threading.Lock()

        if self.arc_api_key == "" or self.arc_api_key is None:
            if self.operation_mode != OperationMode.OFFLINE:
                self.arc_api_key = self._get_anonymous_api_key()

        # Fetch from API if not in offline mode
        if self.operation_mode != OperationMode.OFFLINE:
            self._fetch_from_api()

        # Callback for when a scorecard is closed, defaults to None
        # Set by listen_and_serve()
        self.on_scorecard_close: Optional[Callable[[EnvironmentScorecard], None]] = None

    def _parse_operation_mode_from_env(self) -> OperationMode:
        """Resolve operation mode from env: OPERATION_MODE, then OFFLINE_ONLY/ONLINE_ONLY."""
        env_op = os.getenv("OPERATION_MODE", "").strip().lower()
        if env_op in ("normal", "online", "offline"):
            return OperationMode(env_op)
        return OperationMode.NORMAL

    def _get_anonymous_api_key(self) -> str:
        """Get an anonymous API key."""
        url = f"{self.arc_base_url}/api/games/anonkey"
        headers = {
            "Accept": "application/json",
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        if "api_key" in json_data:
            key = json_data["api_key"]
            self.logger.info(f"Got anonymous API key: {key}")
            self.logger.info(f"You can register for an API key at {self.arc_base_url}")
            return str(key)
        return ""

    def _scan_for_environments(self) -> None:
        """Scan environments_dir for metadata.json files and load them as EnvironmentInfo."""
        if self.environments_dir is None:
            return

        environments_path = Path(self.environments_dir)
        if not environments_path.exists() or not environments_path.is_dir():
            return

        # Recursively find all metadata.json files
        for metadata_file in environments_path.rglob("metadata.json"):
            try:
                # Read and parse the JSON file
                json_data = metadata_file.read_text(encoding="utf-8")
                env_info = EnvironmentInfo.model_validate_json(json_data)
                # Set local_dir to the parent directory of metadata.json
                env_info.local_dir = str(metadata_file.parent)
                self.available_environments.append(env_info)
            except Exception as e:
                # Skip files that fail to load (invalid JSON, missing fields, etc.)
                self.logger.warning(
                    f"Failed to load metadata.json from {metadata_file}: {e}",
                    exc_info=True,
                )
                continue

    def _fetch_from_api(self) -> None:
        """Fetch available environments from the API and merge with local environments."""
        if not self.arc_api_key:
            # Skip API call if no API key is provided
            return

        try:
            url = f"{self.arc_base_url}/api/games"
            headers = {
                "X-Api-Key": self.arc_api_key,
                "Accept": "application/json",
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Parse response
            games_data = response.json()

            # Convert API response to EnvironmentInfo objects
            api_environments: list[EnvironmentInfo] = []
            for game_data in games_data:
                try:
                    # API may return different structure, adapt as needed
                    # Assuming API returns list of dicts with at least game_id and title
                    env_info = EnvironmentInfo(
                        game_id=game_data.get("game_id", ""),
                        title=game_data.get("title", ""),
                        tags=game_data.get("tags", []),
                        baseline_actions=game_data.get("baseline_actions", []),
                        date_downloaded=game_data.get("date_downloaded"),
                        class_name=game_data.get("class_name"),
                    )
                    api_environments.append(env_info)
                except Exception as e:
                    # Skip invalid entries
                    game_id = game_data.get("game_id", "unknown")
                    self.logger.warning(
                        f"Failed to parse API environment entry (game_id: {game_id}): {e}",
                        exc_info=True,
                    )
                    continue

            # Merge with existing environments, removing duplicates by game_id
            existing_game_ids = {env.game_id for env in self.available_environments}
            for api_env in api_environments:
                if api_env.game_id not in existing_game_ids:
                    self.available_environments.append(api_env)
                    existing_game_ids.add(api_env.game_id)

            if api_environments:
                self.logger.info(
                    f"Successfully fetched {len(api_environments)} environment(s) from API"
                )

        except requests.exceptions.RequestException as e:
            # Network or HTTP errors
            self.logger.error(
                f"Failed to fetch environments from API ({self.arc_base_url}/api/games): {e}",
                exc_info=True,
            )
        except Exception as e:
            # Other errors (invalid JSON, unexpected response format, etc.)
            self.logger.error(
                f"Unexpected error while fetching environments from API: {e}",
                exc_info=True,
            )

    def get_environments(self) -> list[EnvironmentInfo]:
        """Get the list of available environments.

        Returns:
            List of EnvironmentInfo objects representing available environments.
        """
        return self.available_environments

    def _create_renderer_from_mode(
        self,
        render_mode: Optional[str],
        renderer: Optional[Callable[[int, FrameDataRaw], None]],
        environment_info: EnvironmentInfo,
    ) -> Optional[Callable[[int, FrameDataRaw], None]]:
        """Create a renderer callable from render_mode if needed.

        Args:
            render_mode: Optional render mode string ("human", "terminal", "terminal-fast").
            renderer: Optional callable that accepts FrameDataRaw and performs custom rendering.
            environment_info: EnvironmentInfo to get default_fps from.

        Returns:
            Renderer callable if render_mode or renderer is provided, None otherwise.
        """
        # If renderer is provided, use it directly
        if renderer is not None:
            return renderer

        # If render_mode is provided, create a callable from it
        if render_mode is not None:
            default_fps = environment_info.default_fps
            if render_mode == "terminal":
                return lambda steps, frame_data: render_frames_terminal(
                    steps=steps,
                    frame_data=frame_data,
                    default_fps=default_fps,
                    scale=1,
                )
            if render_mode == "terminal-fast":
                return lambda steps, frame_data: render_frames_terminal(
                    steps=steps,
                    frame_data=frame_data,
                    default_fps=default_fps,
                    scale=1,
                    skip_deplay=True,
                )
            elif render_mode == "human":
                return lambda steps, frame_data: render_frames(
                    steps=steps,
                    frame_data=frame_data,
                    default_fps=default_fps,
                    scale=4,
                )
            else:
                self.logger.warning(
                    f"Unknown render_mode: {render_mode}. No renderer will be used."
                )
                return None

        return None

    def open_scorecard(
        self,
        source_url: Optional[str] = None,
        tags: Optional[list[str]] = None,
        opaque: Optional[Any] = None,
    ) -> str:
        """Open a scorecard by ID.

        Args:
            scorecard_id: The ID of the scorecard to open.

        Returns:
            The EnvironmentScorecard object.
        """
        return self.create_scorecard(source_url, tags, opaque)

    def create_scorecard(
        self,
        source_url: Optional[str] = None,
        tags: Optional[list[str]] = None,
        opaque: Optional[Any] = None,
    ) -> str:
        """Create a new scorecard.

        Args:
            source_url: Optional source URL for the scorecard.
            tags: Optional list of tags for the scorecard.
            opaque: Optional opaque data for the scorecard.

        Returns:
            The ID of the newly created scorecard.
        """
        with self._lock:
            return self._create_scorecard_no_lock(source_url, tags, opaque)

    def _create_scorecard_no_lock(
        self,
        source_url: Optional[str] = None,
        tags: Optional[list[str]] = None,
        opaque: Optional[Any] = None,
    ) -> str:
        """Create a new scorecard.

        Args:
            source_url: Optional source URL for the scorecard.
            tags: Optional list of tags for the scorecard.
            opaque: Optional opaque data for the scorecard.

        Returns:
            The ID of the newly created scorecard.
        """
        if self.operation_mode == OperationMode.ONLINE:
            url = f"{self.arc_base_url}/api/scorecard/open"
            headers = {
                "X-API-Key": self.arc_api_key,
                "Accept": "application/json",
            }
            payload: dict[str, Any] = {}
            if tags is not None:
                payload["tags"] = tags
            else:
                payload["tags"] = ["wrapper"]
            if source_url is not None:
                payload["source_url"] = source_url
            if opaque is not None:
                payload["opaque"] = opaque
            response = self._session.post(
                url, headers=headers, json=payload, timeout=10
            )
            print(response.text)
            response.raise_for_status()
            print(response.json())
            card_id = response.json()["card_id"]
            self.logger.info(f"Created new scorecard: {card_id}")
            return str(card_id)

        # Local scorecard (NORMAL or OFFLINE)
        card_id = self.scorecard_manager.new_scorecard(
            source_url=source_url,
            tags=tags,
            api_key=self.arc_api_key,
            opaque=opaque,
        )
        self.logger.info(f"Created new scorecard: {card_id}")
        return str(card_id)

    def close_scorecard(
        self, scorecard_id: Optional[str] = None
    ) -> Optional[EnvironmentScorecard]:
        with self._lock:
            if scorecard_id is None:
                scorecard_id = self._default_scorecard_id

            if scorecard_id is None:
                return None

            if self.operation_mode == OperationMode.ONLINE:
                url = f"{self.arc_base_url}/api/scorecard/close"
                headers = {
                    "X-API-Key": self.arc_api_key,
                    "Accept": "application/json",
                }
                data = {
                    "card_id": scorecard_id,
                }
                response = self._session.post(
                    url, headers=headers, json=data, timeout=10
                )
                response.raise_for_status()
                if scorecard_id == self._default_scorecard_id:
                    self._default_scorecard_id = None
                self.logger.info(f"Closed scorecard: {scorecard_id}")
                return self._convert_scorecard_to_environment_scorecard(response.json())

            scorecard, _, _ = self.scorecard_manager.close_scorecard(
                scorecard_id, self.arc_api_key
            )
            if scorecard is None:
                return None

            # Convert to EnvironmentScorecard using available environments
            out = EnvironmentScorecard.from_scorecard(
                scorecard, self.available_environments
            )
            out.api_key = None
            if scorecard_id == self._default_scorecard_id:
                self._default_scorecard_id = None

            self.logger.info(f"Closed scorecard: {scorecard_id}")
            return out

    def get_scorecard(
        self, scorecard_id: Optional[str] = None
    ) -> Optional[EnvironmentScorecard]:
        """Get a scorecard by ID, converted to EnvironmentScorecard.

        Args:
            scorecard_id: Optional scorecard ID. If not provided, returns the default scorecard.

        Returns:
            EnvironmentScorecard object if found, None otherwise.
        """
        with self._lock:
            print(f"scorecard_id: {scorecard_id}")
            if scorecard_id is None:
                if self._default_scorecard_id is None:
                    # Create default scorecard if it doesn't exist
                    self._default_scorecard_id = self._create_scorecard_no_lock()
                scorecard_id = self._default_scorecard_id

            if self.operation_mode == OperationMode.ONLINE:
                url = f"{self.arc_base_url}/api/scorecard/{scorecard_id}"
                headers = {
                    "X-API-Key": self.arc_api_key,
                    "Accept": "application/json",
                }
                response = self._session.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                return self._convert_scorecard_to_environment_scorecard(response.json())

            # Get scorecard from manager
            scorecard = self.scorecard_manager.get_scorecard(
                scorecard_id, self.arc_api_key
            )
            if scorecard is None:
                return None

            # Convert to EnvironmentScorecard using available environments
            out = EnvironmentScorecard.from_scorecard(
                scorecard, self.available_environments
            )
            out.api_key = None
            return out

    def _convert_scorecard_to_environment_scorecard(
        self, data: dict[str, Any]
    ) -> EnvironmentScorecard:
        """Convert a scorecard from the API to an EnvironmentScorecard."""
        try:
            if "open_at" in data:
                del data["open_at"]
            if "last_update" in data:
                del data["last_update"]
            out = EnvironmentScorecard.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"Invalid EnvironmentScorecard from {data}: {e}") from e

        out.api_key = None
        return out

    def make(
        self,
        game_id: str,
        seed: int = 0,
        scorecard_id: Optional[str] = None,
        save_recording: bool = False,
        render_mode: Optional[str] = None,
        renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
    ) -> Optional[EnvironmentWrapper]:
        """Make (download and prepare) an environment.

        Args:
            game_id: Game identifier in format 'ls20' or 'ls20-1234abcd'.
                The first 4 characters are the game_id, everything after '-' is the version.
            scorecard_id: Optional scorecard ID for tracking runs. If not provided,
                a new scorecard will be created and stored for subsequent calls.
            save_recording: Whether to save recordings to JSONL file.
            render_mode: Optional render mode string ("human", "terminal"). If provided,
                creates a renderer callable automatically.
            renderer: Optional callable that accepts FrameDataRaw and performs custom rendering.
                If both render_mode and renderer are provided, renderer takes precedence.

        Returns:
            LocalEnvironmentWrapper object if successful, None otherwise.
        """
        with self._lock:
            # If scorecard_id not provided, use or create default
            if scorecard_id is None:
                if self._default_scorecard_id is None:
                    scorecard_id = self._create_scorecard_no_lock()
                    self._default_scorecard_id = scorecard_id
                scorecard_id = self._default_scorecard_id

            # Split game_id into base_id and version
            if "-" in game_id:
                base_id, version = game_id.split("-", 1)
            else:
                base_id = game_id
                version = None

            # OFFLINE mode: search in scanned environments only
            if self.operation_mode == OperationMode.OFFLINE:
                return self._find_local_game(
                    base_id,
                    version,
                    scorecard_id,
                    save_recording,
                    seed,
                    render_mode,
                    renderer,
                )

            # NORMAL mode: download game and run locally
            if self.operation_mode == OperationMode.NORMAL:
                return self._download_game(
                    base_id,
                    version,
                    scorecard_id,
                    save_recording,
                    seed,
                    render_mode,
                    renderer,
                )

            # ONLINE mode: create remote wrapper
            return self._create_remote_wrapper(
                base_id, version, scorecard_id, save_recording, render_mode, renderer
            )

    def _find_local_game(
        self,
        game_id: str,
        version: Optional[str],
        scorecard_id: str,
        save_recording: bool,
        seed: int = 0,
        render_mode: Optional[str] = None,
        renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
    ) -> Optional[LocalEnvironmentWrapper]:
        """Find a local game from scanned environments.

        Args:
            game_id: 4-character game identifier.
            version: Optional version string. If None, returns the latest downloaded version.
            scorecard_id: Scorecard ID for tracking runs.

        Returns:
            LocalEnvironmentWrapper if found, None otherwise.
        """
        # Filter environments by base game_id (first 4 characters)
        matching_envs = []
        for env in self.available_environments:
            # Extract base_id from env.game_id (e.g. "ls20" or "ls20-1234abcd")
            env_base_id = env.game_id.split("-", 1)[0]
            if env_base_id == game_id:
                matching_envs.append(env)

        if not matching_envs:
            self.logger.error(
                f"Game {game_id} not found in scanned environments. "
                f"Available games: {sorted(set(e.game_id.split('-', 1)[0] for e in self.available_environments))}"
            )
            return None

        # If version is specified, find exact match
        if version:
            for env in matching_envs:
                # Extract version from env.game_id (everything after '-')
                env_version = (
                    env.game_id.split("-", 1)[1] if "-" in env.game_id else None
                )
                if env_version == version:
                    if env.local_dir is None:
                        self.logger.error(
                            f"Found game {game_id}-{version} but local_dir is None"
                        )
                        return None
                    return self._create_wrapper(
                        env, scorecard_id, save_recording, seed, render_mode, renderer
                    )

            self.logger.error(
                f"Game {game_id} with version {version} not found. "
                f"Available versions: {[e.game_id.split('-')[1] if '-' in e.game_id else 'default' for e in matching_envs]}"
            )
            return None

        # No version specified - return the latest downloaded one
        # Sort by date_downloaded (most recent first)
        matching_envs.sort(
            key=lambda e: e.date_downloaded
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        latest_env = matching_envs[0]

        if latest_env.local_dir is None:
            self.logger.error(f"Found game {game_id} but local_dir is None")
            return None

        self.logger.info(
            f"Found latest version of {game_id}: {latest_env.game_id} "
            f"(downloaded: {latest_env.date_downloaded})"
        )
        return self._create_wrapper(
            latest_env, scorecard_id, save_recording, seed, render_mode, renderer
        )

    def _create_wrapper(
        self,
        env_info: EnvironmentInfo,
        scorecard_id: str,
        save_recording: bool,
        seed: int = 0,
        render_mode: Optional[str] = None,
        renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
    ) -> Optional[LocalEnvironmentWrapper]:
        """Create a LocalEnvironmentWrapper from EnvironmentInfo.

        Args:
            env_info: EnvironmentInfo to wrap.
            scorecard_id: Scorecard ID for tracking runs.
            save_recording: Whether to save recordings.
            render_mode: Optional render mode string ("human", "terminal").
            renderer: Optional callable that accepts FrameDataRaw and performs custom rendering.

        Returns:
            LocalEnvironmentWrapper if successful, None otherwise.
        """
        # Create renderer callable from render_mode if needed
        final_renderer = self._create_renderer_from_mode(
            render_mode, renderer, env_info
        )

        try:
            wrapper = LocalEnvironmentWrapper(
                environment_info=env_info,
                seed=seed,
                logger=self.logger,
                scorecard_id=scorecard_id,
                save_recording=save_recording,
                recordings_dir=self.recordings_dir,
                scorecard_manager=self.scorecard_manager,
                renderer=final_renderer,
            )
            return wrapper
        except Exception as e:
            self.logger.error(
                f"Failed to create LocalEnvironmentWrapper for {env_info.game_id}: {e}",
                exc_info=True,
            )
            return None

    def _fetch_metadata(
        self,
        game_id: str,
    ) -> Optional[dict[str, Any]]:
        """Fetch game metadata from the API.

        Returns:
            Metadata dictionary if successful, None otherwise.
        """
        if not self.arc_api_key:
            self.logger.error("Cannot fetch metadata: no API key provided")
            return None

        metadata_url = f"{self.arc_base_url}/api/games/{game_id}"
        headers = {
            "X-Api-Key": self.arc_api_key,
            "Accept": "application/json",
        }

        try:
            response = requests.get(metadata_url, headers=headers, timeout=10)

            if not response.ok:
                self.logger.warning(
                    "Failed to fetch metadata for game %s (status=%s): %s",
                    game_id,
                    response.status_code,
                    response.text,
                )
                return None

            metadata: dict[str, Any] = response.json()
            self.logger.info("Successfully fetched metadata for game %s", game_id)
            return metadata

        except requests.exceptions.RequestException as e:
            # Network errors, timeouts, DNS, connection refused, etc.
            self.logger.error(
                "Request error while fetching metadata for game %s: %s",
                game_id,
                e,
                exc_info=True,
            )
            return None

        except ValueError as e:
            # JSON decode errors
            self.logger.error(
                "Invalid JSON returned for game %s: %s",
                game_id,
                e,
                exc_info=True,
            )
            return None

    def _create_remote_wrapper(
        self,
        game_id: str,
        version: Optional[str],
        scorecard_id: str,
        save_recording: bool,
        render_mode: Optional[str] = None,
        renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
    ) -> Optional[RemoteEnvironmentWrapper]:
        """Create a RemoteEnvironmentWrapper for online-only mode.

        Args:
            game_id: 4-character game identifier.
            version: Optional version string. If None, fetches from API.
            scorecard_id: Scorecard ID for tracking runs.

        Returns:
            RemoteEnvironmentWrapper if successful, None otherwise.
        """
        if not self.arc_api_key:
            self.logger.error("Cannot create remote wrapper: no API key provided")
            return None

        try:
            # Fetch metadata to get exact game_id with version
            metadata = self._fetch_metadata(game_id)
            if metadata is None:
                return None

            # Get full game_id with version from metadata
            full_game_id = metadata.get("game_id", game_id)
            if version and full_game_id != f"{game_id}-{version}":
                # If version was provided, construct full_game_id
                full_game_id = f"{game_id}-{version}"
            elif not version and "-" not in full_game_id:
                # If no version in metadata, we need to get it from the API response
                # For now, use the game_id from metadata
                self.logger.warning(
                    f"Could not determine version for {game_id}, using {full_game_id}"
                )

            # Create EnvironmentInfo from metadata
            env_info = EnvironmentInfo(
                game_id=metadata.get("game_id", full_game_id),
                title=metadata.get("title", game_id),
                tags=metadata.get("tags", []),
                baseline_actions=metadata.get("baseline_actions", []),
                date_downloaded=metadata.get("date_downloaded"),
                class_name=metadata.get("class_name"),
            )
            # local_dir is None for remote environments
            env_info.local_dir = None

            # Create renderer callable from render_mode if needed
            final_renderer = self._create_renderer_from_mode(
                render_mode, renderer, env_info
            )

            # Create RemoteEnvironmentWrapper
            wrapper = RemoteEnvironmentWrapper(
                base_url=self.arc_base_url,
                environment_info=env_info,
                arc_api_key=self.arc_api_key,
                logger=self.logger,
                scorecard_id=scorecard_id,
                save_recording=save_recording,
                recordings_dir=self.recordings_dir,
                scorecard_manager=self.scorecard_manager,
                renderer=final_renderer,
                master_cookie_jar=self._session.cookies,
                cookie_lock=self._cookie_lock,
            )
            return wrapper

        except Exception as e:
            self.logger.error(
                f"Unexpected error while creating remote wrapper for {game_id}: {e}",
                exc_info=True,
            )
            return None

    def _download_game(
        self,
        game_id: str,
        version: Optional[str],
        scorecard_id: str,
        save_recording: bool,
        seed: int = 0,
        render_mode: Optional[str] = None,
        renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
    ) -> Optional[LocalEnvironmentWrapper]:
        """Download game metadata and source from API.

        Args:
            game_id: 4-character game identifier.
            version: Optional version string.
            scorecard_id: Scorecard ID for tracking runs.

        Returns:
            LocalEnvironmentWrapper if successful, None otherwise.
        """
        if not self.arc_api_key:
            self.logger.error("Cannot download game: no API key provided")
            return None

        try:
            # Fetch metadata
            metadata = self._fetch_metadata(game_id)
            if metadata is None:
                return self._find_local_game(
                    game_id,
                    version,
                    scorecard_id,
                    save_recording,
                    seed,
                    render_mode,
                    renderer,
                )

            # Get version from metadata if not provided
            if version is None:
                version = (
                    metadata.get("version")
                    or metadata.get("game_id", "").split("-")[-1]
                    if "-" in metadata.get("game_id", "")
                    else None
                )

            # Create directory structure: {environment_files}/{game_id}/{version}
            env_dir = Path(self.environments_dir) / game_id
            if version:
                env_dir = env_dir / version
            env_dir.mkdir(parents=True, exist_ok=True)

            # Add date_downloaded to metadata before saving
            date_downloaded = datetime.now(timezone.utc)
            metadata["tags"] = metadata.get("tags", [])
            metadata["baseline_actions"] = metadata.get("baseline_actions", [])
            metadata["local_dir"] = str(env_dir)
            metadata["date_downloaded"] = date_downloaded.isoformat()

            # Save metadata.json
            metadata_file = env_dir / "metadata.json"
            import json

            # Get class_name from metadata or default to game_id
            class_name = metadata.get("class_name")
            if not class_name:
                # Generate from game_id (first 4 chars, capitalize first letter)
                class_name = game_id[0].upper() + game_id[1:] if game_id else "Game"

            # Create EnvironmentInfo
            env_info = EnvironmentInfo(
                game_id=metadata.get(
                    "game_id", f"{game_id}-{version}" if version else game_id
                ),
                title=metadata.get("title", game_id),
                tags=metadata.get("tags", []),
                baseline_actions=metadata.get("baseline_actions", []),
                date_downloaded=date_downloaded,
                class_name=class_name,
            )
            env_info.local_dir = str(env_dir)

            metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            # Check if game_class is already in the directory
            game_class_file = env_dir / f"{class_name.lower()}.py"
            if game_class_file.exists():
                return self._create_wrapper(
                    env_info, scorecard_id, save_recording, seed, render_mode, renderer
                )

            # Download source code
            source_url = f"{self.arc_base_url}/api/games/{game_id}-{version}/source"
            headers = {
                "X-Api-Key": self.arc_api_key,
                "Accept": "application/json",
            }
            source_response = requests.get(source_url, headers=headers, timeout=10)
            source_response.raise_for_status()
            source_code = source_response.text

            # Determine Python filename from class_name in metadata
            class_name = metadata.get("class_name")
            if not class_name:
                # Generate from game_id (first 4 chars, capitalize first letter)
                class_name = game_id[0].upper() + game_id[1:] if game_id else "Game"

            # Save source code
            source_file = env_dir / f"{class_name.lower()}.py"
            source_file.write_text(source_code, encoding="utf-8")

            self.logger.info(
                f"Successfully downloaded game {game_id} (version: {version}) to {env_dir}"
            )

            # Create and return LocalEnvironmentWrapper
            return self._create_wrapper(
                env_info, scorecard_id, save_recording, seed, render_mode, renderer
            )

        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"Failed to download game {game_id} from API: {e}",
                exc_info=True,
            )
            return None
        except Exception as e:
            self.logger.error(
                f"Unexpected error while downloading game {game_id}: {e}",
                exc_info=True,
            )
            return None

    def listen_and_serve(
        self,
        host: str = "0.0.0.0",
        port: int = 8001,
        competition_mode: bool = False,
        save_all_recordings: bool = False,
        add_cookie: Optional[Callable[[Response, str], Response]] = None,
        scorecard_timeout: Optional[int] = None,
        on_scorecard_close: Optional[Callable[[EnvironmentScorecard], None]] = None,
        extra_api_routes: Optional[Callable[["Arcade", Flask], None]] = None,
        renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
        **kwargs: Any,
    ) -> None:
        """Spin up a Flask server (blocking). Uses arc_agi.server.create_app()."""
        from .server import create_app

        app, api = create_app(
            self,
            save_all_recordings=save_all_recordings,
            add_cookie=add_cookie,
            on_scorecard_close=on_scorecard_close,
            renderer=renderer,
        )
        app.debug = False
        app.threaded = True  # False increases stability

        if on_scorecard_close is not None:
            self._on_scorecard_close = on_scorecard_close
            cleaner = threading.Thread(target=api.scorecard_cleanup_loop, daemon=True)
            cleaner.start()

        if extra_api_routes is not None:
            extra_api_routes(self, app)

        if scorecard_timeout is not None:
            self.scorecard_manager.set_idle_for(scorecard_timeout)

        app.run(host=host, port=port, **kwargs)
