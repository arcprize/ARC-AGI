import json
import threading
import time
import uuid
from typing import Any, Callable, Optional, Tuple

from arcengine import ActionInput, FrameData, FrameDataRaw, GameAction
from flask import Response, jsonify, request
from pydantic import ValidationError

from .base import Arcade
from .models import APIError
from .scorecard import EnvironmentScorecard
from .wrapper import EnvironmentWrapper

MAX_OPAQUE_BYTES = 16 * 1024  # 16KiB (16384 bytes)


class RestAPI:
    def __init__(
        self,
        arcade: Arcade,
        competition_mode: bool = False,
        save_all_recordings: bool = False,
        add_cookie: Optional[Callable[[Response, str], Response]] = None,
        on_scorecard_close: Optional[Callable[[EnvironmentScorecard], None]] = None,
        renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
    ) -> None:
        self.arcade = arcade
        self.competition_mode = competition_mode
        self.save_all_recordings = save_all_recordings
        self.add_cookie = add_cookie
        self.on_scorecard_close = on_scorecard_close
        self._environmentCache: dict[str, EnvironmentWrapper] = {}
        self._cache_lock = threading.Lock()
        self.renderer = renderer

    def _json_with_cookie(
        self,
        data: Any,
        *,
        api_key: Optional[str] = None,
    ) -> Response:
        """Return JSON response with 200; optionally wrap response with add_cookie(response, api_key)."""
        resp = jsonify(data)
        if self.add_cookie is not None and api_key is not None:
            resp = self.add_cookie(resp, api_key)
        return resp

    def get_games(self) -> Tuple[Response, int]:
        out = [e.model_dump(mode="json") for e in self.arcade.available_environments]
        return jsonify(out), 200

    def get_game_info(self, game_id: str) -> Tuple[Response, int]:
        for env in self.arcade.available_environments:
            if env.game_id == game_id or env.game_id.startswith(f"{game_id}-"):
                return jsonify(env.model_dump(mode="json")), 200
        return jsonify(
            {
                "error": APIError.SERVER_ERROR,
                "message": f"game {game_id} not found",
            }
        ), 404

    def get_scorecard(
        self, card_id: Optional[str] = None, game_id: Optional[str] = None
    ) -> Tuple[Response, int]:
        api_key = request.headers.get("X-API-Key", "1234")
        scorecard = (
            self.arcade.scorecard_manager.get_scorecard(card_id, api_key)
            if card_id
            else None
        )
        if scorecard is None:
            return jsonify(
                {
                    "error": APIError.SERVER_ERROR,
                    "message": f"card_id `{card_id}` not found",
                }
            ), 404

        if game_id is not None:
            return self._json_with_cookie(
                scorecard.get_json_for(game_id),
                api_key=api_key,
            ), 200
        else:
            envs = self.arcade.available_environments
            if envs is None:
                return jsonify(
                    {
                        "error": APIError.SERVER_ERROR,
                        "message": "no environments available",
                    }
                ), 500
            out = EnvironmentScorecard.from_scorecard(scorecard, envs)
            out.api_key = None  # do not expose api_key
            return self._json_with_cookie(
                out.model_dump(exclude_none=True),
                api_key=api_key,
            ), 200

    def new_scorecard(self) -> Tuple[Response, int]:
        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify({"error": "request body must be a JSON object"}), 400

        # ----- opaque guard-rail -----------------------------------------
        opaque = data.get("opaque")
        try:
            # stringify exactly the bytes we’ll send to Postgres
            opaque_bytes = json.dumps(opaque, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            return jsonify({"error": "opaque must be JSON-serialisable"}), 400

        if len(opaque_bytes) > MAX_OPAQUE_BYTES:
            return jsonify({"error": "opaque exceeds 8 KB limit"}), 400
        # -----------------------------------------------------------------

        tags = data.get("tags", [])
        if "human" not in tags and "agent" not in tags:
            tags.append("agent")

        source_url = data.get("source_url")
        api_key = request.headers.get("X-API-Key", "1234")

        card_id = self.arcade.scorecard_manager.new_scorecard(
            source_url=source_url,
            tags=tags,
            api_key=api_key,
            opaque=opaque,  # original Python value
        )
        return self._json_with_cookie(
            {"card_id": card_id},
            api_key=api_key,
        ), 200

    def close_scorecard(self) -> Tuple[Response, int]:
        data = request.get_json()
        if not isinstance(data, dict) or "card_id" not in data:
            return jsonify(
                {
                    "error": APIError.VALIDATION_ERROR.name,
                    "message": "missing `card_id` in action data",
                }
            ), 400

        api_key = request.headers.get("X-API-Key", "1234")
        scorecard, guids, _ = self.arcade.scorecard_manager.close_scorecard(
            data["card_id"], api_key
        )
        if scorecard is None:
            return jsonify(
                {
                    "error": APIError.VALIDATION_ERROR.name,
                    "message": f"scorecard {data['card_id']} not found",
                }
            ), 404

        envs = self.arcade.available_environments
        if envs is None:
            return jsonify(
                {
                    "error": APIError.SERVER_ERROR,
                    "message": "no environments available",
                }
            ), 500
        out = EnvironmentScorecard.from_scorecard(scorecard, envs)
        if self.on_scorecard_close is not None:
            self.on_scorecard_close(out)
        if guids is not None:
            for guid in guids:
                self.cleanup_environment(guid)
        out.api_key = None  # do not expose api_key
        return self._json_with_cookie(
            out.model_dump(exclude_none=True),
            api_key=api_key,
        ), 200

    def cmd(self, action: GameAction) -> Tuple[Response, int]:
        data = request.get_json()

        if not isinstance(data, dict) or "game_id" not in data:
            return jsonify(
                {
                    "error": APIError.VALIDATION_ERROR.name,
                    "message": "missing `game_id` in action data",
                }
            ), 400

        # if data["game_id"] not in os.environ.get("GAMES", "").split(","):
        #     return jsonify(
        #         {
        #             "error": APIError.GAME_NOT_AVAILABLE_ERROR.name,
        #             "message": f"game {data['game_id']} is not available, check to make sure its included in your local .env",
        #         }
        #     ), 400

        try:
            action.validate_data(data)
        except ValidationError:
            return jsonify(
                {"error": APIError.VALIDATION_ERROR.name, "message": "{e}}"}
            ), 400

        out = {}
        for field, model in action.action_type.model_fields.items():
            out[field] = data[field]

        api_key = request.headers.get("X-API-Key", "1234")
        game_id = data["game_id"]

        game, full_reset = self._get_or_create_environment(
            game_id=game_id,
            scorecard_id=data.get("card_id", None),
            guid=data.get("guid", None),
            api_key=api_key,
        )

        if game:
            if game.api_key != api_key:  # type: ignore[attr-defined]
                return jsonify(
                    {
                        "error": APIError.VALIDATION_ERROR.name,
                        "message": f"game {game_id} with guid {data.get('guid', '')} does not match API key {api_key}",
                    }
                ), 400

            guid = data.get("guid")
            if action == GameAction.RESET:
                if not guid:
                    guid = str(uuid.uuid4())

            if not guid:
                return jsonify(
                    {
                        "error": APIError.VALIDATION_ERROR.name,
                        "message": "missing `guid` for any action other than RESET",
                    }
                ), 400

            g = game

            try:
                input_action = ActionInput(
                    id=action,
                    data=out,
                    reasoning=data.get("reasoning"),
                )
                # Only send the action if not a full reset (brand new game)
                response = (
                    g.step(
                        action=input_action.id,
                        data=input_action.data,
                        reasoning=input_action.reasoning,
                    )
                    if not full_reset
                    else g.observation_space
                )
                if response is None:
                    return jsonify(
                        {
                            "error": APIError.GAME_NOT_STARTED_ERROR.name,
                            "message": f"game {game_id} is available but has not been started, send {GameAction.RESET.name} to begin playing",
                        }
                    ), 400
                update = {
                    "game_id": game_id,
                    "levels_completed": response.levels_completed,
                    "win_levels": response.win_levels,
                    "frame": response.frame,
                    "state": response.state,
                    "guid": guid,
                    "action_input": response.action_input,
                    "available_actions": response.available_actions,
                }
                update["action_input"] = response.action_input
                python_frame = FrameData(**update)

                self._save_to_environment_cache(g, guid)

                if python_frame.is_empty():
                    return jsonify(
                        {
                            "error": APIError.GAME_NOT_STARTED_ERROR.name,
                            "message": f"game {data['game_id']} is available but has not been started, send {GameAction.RESET.name} to begin playing",
                        }
                    ), 400

                out = python_frame.model_dump()
                out["state"] = out["state"].name
                out["action_input"]["id"] = out["action_input"]["id"].value
                # arcade.scorecard_manager.update_scorecard(
                #     guid, python_frame, full_reset or response.full_reset
                # )
                return self._json_with_cookie(out, api_key=api_key), 200
            except ValidationError as exc:
                return jsonify(
                    {
                        "error": APIError.VALIDATION_ERROR.name,
                        "message": f"error creating ActionInput: {exc}",
                    }
                ), 400

        return jsonify(
            {
                "error": APIError.SERVER_ERROR.name,
                "message": f"game {game_id} not found",
            }
        ), 400

    def _get_or_create_environment(
        self, game_id: str, scorecard_id: str | None, guid: str | None, api_key: str
    ) -> tuple[EnvironmentWrapper | None, bool]:
        with self._cache_lock:
            game: Optional[EnvironmentWrapper] = None
            # if there is a guid, try and find it from our cache
            if guid and guid in self._environmentCache:
                game = self._environmentCache.get(guid)
                if game and game.environment_info.game_id == game_id:
                    return game, False

            if not scorecard_id:
                return None, False

            game = self.arcade.make(
                game_id,
                scorecard_id=scorecard_id,
                save_recording=self.save_all_recordings,
                renderer=self.renderer,
            )
            if game is None:
                return None, False
            setattr(game, "api_key", api_key)
            return game, True

    def _save_to_environment_cache(
        self, environment: EnvironmentWrapper, guid: str
    ) -> None:
        with self._cache_lock:
            self._environmentCache[guid] = environment

    def scorecard_cleanup_loop(self) -> None:
        """Wake up every minute and close stale scorecards."""
        while True:
            time.sleep(60)
            stale_ids = self.arcade.scorecard_manager.get_stale_cards()
            for cid in stale_ids:
                self.arcade.logger.info(
                    f"[auto-close] scorecard {cid} idle > {self.arcade.scorecard_manager.idle_for.total_seconds() / 60} min"
                )
                scorecard, guids, _ = self.arcade.scorecard_manager.close_scorecard(
                    cid, None
                )
                if scorecard is not None:
                    if self.arcade._on_scorecard_close is not None:
                        envScorecard = EnvironmentScorecard.from_scorecard(
                            scorecard, self.arcade.available_environments
                        )
                        self.arcade._on_scorecard_close(envScorecard)
                    if guids is not None:
                        for guid in guids:
                            self.cleanup_environment(guid)

    def cleanup_environment(self, guid: str) -> None:
        with self._cache_lock:
            if guid in self._environmentCache:
                del self._environmentCache[guid]
