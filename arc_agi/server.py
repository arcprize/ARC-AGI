from typing import Callable, Optional, Tuple

from arcengine import FrameDataRaw, GameAction
from flask import Flask, Response

from .api import RestAPI
from .base import Arcade
from .scorecard import EnvironmentScorecard


def create_app(
    arcade: Arcade,
    competition_mode: bool = False,
    save_all_recordings: bool = False,
    add_cookie: Optional[Callable[[Response, str], Response]] = None,
    on_scorecard_close: Optional[Callable[[EnvironmentScorecard], None]] = None,
    renderer: Optional[Callable[[int, FrameDataRaw], None]] = None,
) -> Tuple[Flask, RestAPI]:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    api = RestAPI(
        arcade=arcade,
        competition_mode=competition_mode,
        save_all_recordings=save_all_recordings,
        add_cookie=add_cookie,
        on_scorecard_close=on_scorecard_close,
        renderer=renderer,
    )

    app.api = api

    # api routes
    app.add_url_rule(
        "/api/games",
        methods=["GET"],
        view_func=lambda: api.get_games(),
        endpoint="games",
    )
    app.add_url_rule(
        "/api/games/<game_id>",
        methods=["GET"],
        view_func=lambda game_id: api.get_game_info(game_id=game_id),
        endpoint="game_by_id",
    )

    app.add_url_rule(
        "/api/scorecard/open",
        methods=["POST"],
        view_func=lambda: api.new_scorecard(),
        endpoint="open_scorecard",
    )
    app.add_url_rule(
        "/api/scorecard/close",
        methods=["POST"],
        view_func=lambda: api.close_scorecard(),
        endpoint="close_scorecard",
    )
    app.add_url_rule(
        "/api/scorecard/<card_id>",
        methods=["GET"],
        view_func=lambda card_id: api.get_scorecard(card_id=card_id),
        endpoint="scorecard",
    )
    app.add_url_rule(
        "/api/scorecard/<card_id>/<game_id>",
        methods=["GET"],
        view_func=lambda card_id, game_id: api.get_scorecard(
            card_id=card_id, game_id=game_id
        ),
        endpoint="scorecard_with_gameid",
    )

    app.add_url_rule(
        "/api/cmd/RESET",
        methods=["POST"],
        view_func=lambda: api.cmd(action=GameAction.RESET),
        endpoint="reset",
    )
    app.add_url_rule(
        "/api/cmd/ACTION1",
        methods=["POST"],
        view_func=lambda: api.cmd(action=GameAction.ACTION1),
        endpoint="action1",
    )
    app.add_url_rule(
        "/api/cmd/ACTION2",
        methods=["POST"],
        view_func=lambda: api.cmd(action=GameAction.ACTION2),
        endpoint="action2",
    )
    app.add_url_rule(
        "/api/cmd/ACTION3",
        methods=["POST"],
        view_func=lambda: api.cmd(action=GameAction.ACTION3),
        endpoint="action3",
    )
    app.add_url_rule(
        "/api/cmd/ACTION4",
        methods=["POST"],
        view_func=lambda: api.cmd(action=GameAction.ACTION4),
        endpoint="action4",
    )
    app.add_url_rule(
        "/api/cmd/ACTION5",
        methods=["POST"],
        view_func=lambda: api.cmd(action=GameAction.ACTION5),
        endpoint="action5",
    )
    app.add_url_rule(
        "/api/cmd/ACTION6",
        methods=["POST"],
        view_func=lambda: api.cmd(action=GameAction.ACTION6),
        endpoint="action6",
    )
    app.add_url_rule(
        "/api/cmd/ACTION7",
        methods=["POST"],
        view_func=lambda: api.cmd(action=GameAction.ACTION7),
        endpoint="action7",
    )
    app.add_url_rule(
        "/api/healthcheck",
        methods=["GET"],
        view_func=lambda: ("okay", 200, {"Content-Type": "text/plain"}),
        endpoint="healthcheck",
    )

    return app, api
