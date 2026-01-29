import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple

from arcengine import FrameDataRaw, GameState
from pydantic import BaseModel, Field, computed_field

from .models import EnvironmentInfo

logger = logging.getLogger()

DEFAULT_STALE_MINUTES = 15  # hard-coded fallback
_MIN, _MAX = 1, 60  # sanity window (optional)


def _get_stale_minutes() -> int:
    """Read STALE_MINUTES from the environment, fall back to default,
    and clamp to a safe range.
    """
    raw = os.getenv("STALE_MINUTES", str(DEFAULT_STALE_MINUTES))
    try:
        value = int(raw)
    except ValueError:
        logging.warning(
            "STALE_MINUTES=%r is not an int; using default=%d",
            raw,
            DEFAULT_STALE_MINUTES,
        )
        value = DEFAULT_STALE_MINUTES

    if not _MIN <= value <= _MAX:
        logging.warning("STALE_MINUTES=%d outside %d–%d; clamping", value, _MIN, _MAX)
        value = max(_MIN, min(_MAX, value))

    return value


STALE_MINUTES = _get_stale_minutes()


class EnvironmentScore(BaseModel):
    """Score for an environment run."""

    id: Optional[str] = None
    guid: Optional[str] = None
    score: float
    levels_completed: int
    actions: int
    resets: Optional[int] = None
    state: Optional[GameState] = None
    completed: Optional[bool] = None
    level_scores: Optional[list[float]] = None
    level_actions: Optional[list[int]] = None
    level_baseline_actions: Optional[list[int]] = None
    number_of_levels: Optional[int] = None
    number_of_environments: Optional[int] = 0
    message: Optional[str] = None

    def model_dump_json(self, *, exclude_none: bool = True, **kwargs: Any) -> str:
        """Serialize to JSON string, excluding None fields by default.

        Args:
            exclude_none: If True, exclude fields that are None. Defaults to True.
            **kwargs: Additional arguments passed to parent model_dump_json.

        Returns:
            JSON string representation of the model.
        """
        return super().model_dump_json(exclude_none=exclude_none, **kwargs)


class EnvironmentScoreCalculator:
    """Calculator for environment scores."""

    def __init__(
        self,
        id: Optional[str] = None,
        resets: Optional[int] = None,
        state: Optional[GameState] = None,
        guid: Optional[str] = None,
    ) -> None:
        """Initialize the calculator.

        Args:
            id: Identifier for the environment run.
            resets: Optional number of resets.
        """
        self.id = id
        self.guid = guid
        self.resets = resets
        self.level_scores: list[float] = []
        self.levels_completed: int = 0
        self.actions: int = 0
        self.environments: set[str] = set()
        self.state: Optional[GameState] = state
        self.completed: Optional[bool] = None
        self.level_actions: list[int] = []
        self.level_baseline_actions: list[int] = []

    def add_level(
        self,
        completed: bool,
        actions_taken: int,
        baseline_actions: int,
        game_id: Optional[str] = None,
    ) -> None:
        """Add a level to the score calculation.

        Args:
            completed: Whether the level was completed.
            actions_taken: Number of actions taken to complete the level.
            baseline_actions: Baseline number of actions for the level.
        """
        self.actions += actions_taken

        if game_id:
            self.environments.add(game_id)

        if completed:
            self.levels_completed += 1
            # Calculate score as ((baseline_actions / actions_taken) * 100) max 100
            if actions_taken > 0:
                score = (baseline_actions / actions_taken) * 100
                score = min(score, 100.0)  # Cap at 100
            else:
                score = 0.0
            self.level_scores.append(score)
            self.level_actions.append(actions_taken)
            self.level_baseline_actions.append(baseline_actions)
        else:
            # Not completed, append 0
            self.level_scores.append(0.0)
            self.level_actions.append(actions_taken)
            self.level_baseline_actions.append(baseline_actions)

    def to_score(self, include_levels: bool = True) -> EnvironmentScore:
        """Convert the calculator to an EnvironmentScore.

        Returns:
            EnvironmentScore with average of level_scores as the score.
        """
        # Calculate average of level_scores
        if len(self.level_scores) > 0:
            score = sum(self.level_scores) / len(self.level_scores)
        else:
            score = 0.0

        return EnvironmentScore(
            id=self.id,
            guid=self.guid,
            score=score,
            levels_completed=self.levels_completed,
            actions=self.actions,
            resets=self.resets,
            state=self.state,
            completed=self.completed,
            level_scores=self.level_scores if include_levels else None,
            level_actions=self.level_actions if include_levels else None,
            level_baseline_actions=self.level_baseline_actions
            if include_levels
            else None,
            number_of_levels=len(self.level_scores) if not include_levels else None,
            number_of_environments=len(self.environments)
            if not include_levels
            else None,
        )


class EnvironmentScoreList(BaseModel):
    """List of EnvironmentScore objects."""

    id: str
    runs: List[EnvironmentScore] = Field(default_factory=list)

    @computed_field(return_type=float)  # type: ignore[prop-decorator]# type:
    @property
    def score(self) -> float:
        """Return the average score of the runs."""
        return max(run.score for run in self.runs)

    @computed_field(return_type=int)  # type: ignore[prop-decorator]# type:
    @property
    def actions(self) -> int:
        """Return the total number of actions."""
        return sum(run.actions for run in self.runs)

    @computed_field(return_type=int)  # type: ignore[prop-decorator]# type:
    @property
    def levels_completed(self) -> int:
        """Return the total number of levels completed."""
        return max(run.levels_completed for run in self.runs)

    @computed_field(return_type=bool)  # type: ignore[prop-decorator]# type:
    @property
    def completed(self) -> bool:
        """Return True if all runs are completed."""
        return any(run.completed for run in self.runs)

    @computed_field(return_type=int)  # type: ignore[prop-decorator]# type:
    @property
    def level_count(self) -> int:
        """Return the total number of levels."""
        return max(
            len(run.level_scores) if run.level_scores else 0 for run in self.runs
        )

    @computed_field(return_type=int)  # type: ignore[prop-decorator]# type:
    @property
    def resets(self) -> int:
        """Return the total number of resets."""
        return sum(run.resets if run.resets else 0 for run in self.runs)


class EnvironmentScorecard(BaseModel):
    """Scorecard with computed environment scores."""

    source_url: Optional[str] = None
    tags: Optional[list[str]] = None
    opaque: Optional[Any] = None
    card_id: str
    api_key: Optional[str] = None
    score: float = 0.0
    environments: List[EnvironmentScoreList] = Field(default_factory=list)
    tags_scores: List[EnvironmentScore] = Field(default_factory=list)
    open_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        exclude=True,
    )
    last_update: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        exclude=True,
    )

    def get(self, game_id: Optional[str] = None) -> dict[str, Any]:
        if game_id is not None:
            for environment in self.environments:
                for run in environment.runs:
                    if run.id == game_id:
                        return run.model_dump()
            return {}
        return self.model_dump()

    def __str__(self) -> str:
        return self.model_dump_json(indent=2)

    @computed_field(return_type=int)
    def total_environments_completed(self) -> int:
        """Return the number of environments that are completed."""
        return sum(1 if env.completed else 0 for env in self.environments)

    @computed_field(return_type=int)
    def total_environments(self) -> int:
        """Return the total number of environments."""
        return len(self.environments)

    @computed_field(return_type=int)
    def total_levels_completed(self) -> int:
        """Return the total number of levels completed."""
        return sum(env.levels_completed for env in self.environments)

    @computed_field(return_type=int)
    def total_levels(self) -> int:
        """Return the total number of levels."""
        return sum(env.level_count for env in self.environments)

    @computed_field(return_type=int)
    def total_actions(self) -> int:
        """Return the total number of resets."""
        return sum(env.actions for env in self.environments)

    def model_dump_json(self, *, exclude_none: bool = True, **kwargs: Any) -> str:
        """Serialize to JSON string, excluding None fields by default.

        Args:
            exclude_none: If True, exclude fields that are None. Defaults to True.
            **kwargs: Additional arguments passed to parent model_dump_json.

        Returns:
            JSON string representation of the model.
        """
        return super().model_dump_json(exclude_none=exclude_none, **kwargs)

    @classmethod
    def _raw_scores_from_card(
        self, card: "Card", idx: int
    ) -> tuple[list[int], list[float], list[int]]:
        """Return the raw score from the card."""
        actions_by_level = (
            card.actions_by_level[idx] if idx < len(card.actions_by_level) else []
        )
        prev_actions = 0
        actions: list[int] = []
        scores: list[float] = []
        baseline_actions: list[int] = []
        print(f"actions_by_level: {actions_by_level}")
        for level_idx in range(len(actions_by_level)):
            actions_at_level = actions_by_level[level_idx]
            level_actions = actions_at_level[1] - prev_actions
            actions.append(level_actions)
            scores.append(0.0)
            baseline_actions.append(-1)  # indicate not available
            prev_actions = actions_at_level[1]

        if card.states[idx] != GameState.WIN:
            actions.append(card.actions[idx] - prev_actions)
            scores.append(0.0)
            baseline_actions.append(-1)  # indicate not available

        return actions, scores, baseline_actions

    @classmethod
    def _calculate_score(
        cls,
        card: "Card",
        game_id: str,
        idx: int,
        env_info: EnvironmentInfo | None,
        tags_scores: dict[str, EnvironmentScoreCalculator] | None,
    ) -> EnvironmentScore:
        """Calculate the score for a single card."""
        levels_completed = card.levels_completed[idx]
        guid = card.guids[idx]
        actions = card.actions[idx] if idx < len(card.actions) else 0
        resets = card.resets[idx] if idx < len(card.resets) else 0
        state = card.states[idx] if idx < len(card.states) else GameState.NOT_PLAYED
        completed = state == GameState.WIN

        # Find matching EnvironmentInfo
        if not env_info:
            only_level_actions, scores, baseline_actions = cls._raw_scores_from_card(
                card, idx
            )
            return EnvironmentScore(
                id=card.game_id,
                guid=guid,
                score=0.0,
                levels_completed=levels_completed,
                actions=actions,
                resets=resets,
                state=state,
                completed=completed,
                level_actions=only_level_actions,
                level_baseline_actions=baseline_actions,
                level_scores=scores,
                message=f"No Matching EnvironmentInfo found for {game_id}",
            )

        # Check if baseline_actions are available
        if env_info.baseline_actions is None or len(env_info.baseline_actions) == 0:
            # No baseline actions available
            only_level_actions, scores, baseline_actions = cls._raw_scores_from_card(
                card, idx
            )
            return EnvironmentScore(
                id=card.game_id,
                guid=guid,
                score=0.0,
                levels_completed=levels_completed,
                actions=actions,
                resets=resets,
                state=state,
                completed=completed,
                level_actions=only_level_actions,
                level_baseline_actions=baseline_actions,
                level_scores=scores,
                message="Human baseline actions are not available for this environment",
            )
        elif len(env_info.baseline_actions) < len(card.actions_by_level[idx]):
            # No baseline actions available
            only_level_actions, scores, baseline_actions = cls._raw_scores_from_card(
                card, idx
            )
            return EnvironmentScore(
                id=card.game_id,
                guid=guid,
                score=0.0,
                levels_completed=levels_completed,
                actions=actions,
                resets=resets,
                state=state,
                completed=completed,
                level_actions=only_level_actions,
                level_baseline_actions=baseline_actions,
                level_scores=scores,
                message="Human baseline actions size mismatch",
            )
        else:
            # Calculate score using EnvironmentScoreCalculator
            calculator = EnvironmentScoreCalculator(
                resets=resets, guid=guid, state=state
            )
            calculator.completed = completed

            # Process each level
            # We need to determine how many levels were attempted and completed
            # The actions_by_level list contains tuples of (level, actions) when level changed
            actions_by_level = (
                card.actions_by_level[idx] if idx < len(card.actions_by_level) else []
            )

            # If we have actions_by_level, use that to determine level progression
            # if actions_by_level:
            # actions_by_level contains (level_completed, actions_at_that_point)
            # We need to calculate actions per level
            prev_actions = 0
            for level_idx in range(len(env_info.baseline_actions)):
                baseline = env_info.baseline_actions[level_idx]
                if level_idx < len(actions_by_level):
                    level, actions_at_level = actions_by_level[level_idx]
                    level_actions = actions_at_level - prev_actions
                    level_completed = level_idx < len(actions_by_level) or completed
                    prev_actions = actions_at_level
                else:
                    level_completed = False
                    level_actions = card.actions[idx] - prev_actions
                    prev_actions = card.actions[idx]
                calculator.add_level(
                    completed=level_completed,
                    actions_taken=level_actions,
                    baseline_actions=baseline,
                )
                if tags_scores is not None and env_info.tags:
                    for tag in env_info.tags:
                        tag_score = tags_scores.get(tag)
                        if not tag_score:
                            tag_score = EnvironmentScoreCalculator(id=tag)
                            tags_scores[tag] = tag_score
                        tag_score.add_level(
                            completed=level_completed,
                            actions_taken=level_actions,
                            baseline_actions=baseline,
                            game_id=game_id,
                        )

            return calculator.to_score()

    @classmethod
    def from_scorecard(
        cls,
        scorecard: "Scorecard",
        environment_infos: List[EnvironmentInfo],
    ) -> "EnvironmentScorecard":
        """Create EnvironmentScorecard from Scorecard and EnvironmentInfos.

        Args:
            scorecard: The Scorecard to compute from.
            environment_infos: List of EnvironmentInfo objects to match against.

        Returns:
            EnvironmentScorecard with computed scores.
        """
        # Create a mapping of game_id to EnvironmentInfo
        # Match by full game_id (which may include version)
        env_info_map: dict[str, EnvironmentInfo] = {}
        for env_info in environment_infos:
            # Use full game_id as key (e.g., "bt11" or "bt11-fd9df0622a1a")
            env_info_map[env_info.game_id] = env_info

        # Compute environment scores from cards
        # For each game_id, we'll track the best score (highest levels_completed)
        game_scores: dict[str, EnvironmentScoreList] = {}
        tags_scores: dict[str, EnvironmentScoreCalculator] = {}

        for game_id, card in scorecard.cards.items():
            # Find the idx with the highest levels_completed
            best_idx = -1
            best_levels_completed = -1
            for idx, levels_completed in enumerate(card.levels_completed):
                if levels_completed > best_levels_completed:
                    best_levels_completed = levels_completed
                    best_idx = idx

            # If no valid play found, skip this card
            if best_idx == -1 or best_idx >= len(card.guids):
                continue

            all_scores: List[EnvironmentScore] = []
            for idx, levels_completed in enumerate(card.levels_completed):
                if idx == best_idx:
                    score = cls._calculate_score(
                        card, game_id, best_idx, env_info_map.get(game_id), tags_scores
                    )
                else:
                    score = cls._calculate_score(
                        card, game_id, idx, env_info_map.get(game_id), None
                    )
                all_scores.append(score)

            if all_scores and len(all_scores) > 0:
                game_scores[game_id] = EnvironmentScoreList(id=game_id, runs=all_scores)

        # Convert dict to list
        environment_list = list(game_scores.values())
        tags_list = [
            calculator.to_score(include_levels=False)
            for calculator in tags_scores.values()
        ]

        # Calculate average score
        if len(environment_list) > 0:
            avg_score = sum(env_score.score for env_score in environment_list) / len(
                environment_list
            )
        else:
            avg_score = 0.0

        return cls(
            source_url=scorecard.source_url,
            tags=scorecard.tags,
            opaque=scorecard.opaque,
            card_id=scorecard.card_id,
            api_key=scorecard.api_key,
            score=avg_score,
            environments=environment_list,
            tags_scores=tags_list,
            open_at=scorecard.open_at,
            last_update=scorecard.last_update,
        )


class Card(BaseModel):
    """
    A single scorecard for a single game. A game can be played more than
    once, we track each play with lists of card properties (scores, states, actions)
    """

    game_id: str
    total_plays: int = 0

    guids: list[str] = Field(default_factory=list)
    levels_completed: list[int] = Field(default_factory=list)
    states: list[GameState] = Field(default_factory=list)
    actions: list[int] = Field(default_factory=list)
    actions_by_level: list[list[tuple[int, int]]] = Field(
        default_factory=list, exclude=False
    )
    resets: list[int] = Field(default_factory=list)

    @property
    def idx(self) -> int:
        # lists are zero indexed by play_count starts at 1
        return self.total_plays - 1

    @property
    def started(self) -> bool:
        return self.total_plays > 0

    @property
    def level_completed(self) -> Optional[int]:
        return self.levels_completed[self.idx] if self.started else None

    @property
    def most_levels_completed(self) -> int:
        return max(self.levels_completed) if self.started else 0

    @property
    def state(self) -> GameState:
        return self.states[self.idx] if self.started else GameState.NOT_PLAYED

    @property
    def action_count(self) -> Optional[int]:
        return self.actions[self.idx] if self.started else None

    @computed_field(return_type=int)
    def total_actions(self) -> int:
        return sum(self.actions)

    def get_total_actions(self) -> int:
        return sum(self.actions)

    def index_of_guid(self, match: str) -> int:
        # Iterate backwards since a guid can be reused and we want the most recent
        for idx in range(len(self.guids) - 1, -1, -1):
            if self.guids[idx] == match:
                return idx
        return self.total_plays - 1

    def inc_play_count(self, guid: str) -> None:
        self.total_plays += 1
        self.guids.append(guid)
        self.levels_completed.append(0)
        self.states.append(GameState.NOT_FINISHED)
        self.actions.append(0)
        self.resets.append(0)
        self.actions_by_level.append([])

    def inc_reset_count(self, guid: str) -> None:
        if self.started:
            self.resets[self.index_of_guid(guid)] += 1
            self.actions[self.index_of_guid(guid)] += 1

    def set_levels_completed(self, guid: str, current_levels_completed: int) -> None:
        if self.started:
            index = self.index_of_guid(guid)
            existing_levels_completed = self.levels_completed[index]
            if current_levels_completed != existing_levels_completed:
                self.actions_by_level[index].append(
                    (current_levels_completed, self.actions[index])
                )
            self.levels_completed[index] = current_levels_completed

    def set_state(self, guid: str, state: GameState) -> None:
        if self.started:
            self.states[self.index_of_guid(guid)] = state

    def inc_action_count(self, guid: str) -> None:
        if self.started:
            self.actions[self.index_of_guid(guid)] += 1

    # def to_json(self) -> dict[str, Union[str, int, list[int], list[str]]]:
    #     return {
    #         "game_id": self.game_id,
    #         "total_plays": self.play_count,
    #         "total_actions": self.total_action_count,
    #         "scores": self.scores,
    #         "states": [s.name for s in self.states],
    #         "actions": self.action_counts,
    #     }


class Scorecard(BaseModel):
    """
    Tracks and holds the scorecard for all games
    """

    games: list[str] = Field(default_factory=list, exclude=True)
    cards: dict[str, Card] = Field(default_factory=dict)
    source_url: Optional[str] = None
    tags: Optional[list[str]] = None
    opaque: Optional[Any] = Field(default=None)
    card_id: str = ""
    api_key: str = ""
    open_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        exclude=True,
    )

    last_update: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        exclude=True,
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.cards:
            self.cards = {}

    def new_play(self, game_id: str, guid: str) -> None:
        if game_id not in self.cards:
            self.cards[game_id] = Card.model_validate({"game_id": game_id})
        if game_id in self.cards:
            self.cards[game_id].inc_play_count(guid)

    def reset(self, game_id: str, guid: str) -> None:
        if game_id in self.cards:
            self.cards[game_id].inc_reset_count(guid)

    def take_action(self, game_id: str, guid: str) -> None:
        if game_id in self.cards:
            self.cards[game_id].inc_action_count(guid)

    def win(self, game_id: str, guid: str) -> None:
        if game_id in self.cards:
            self.cards[game_id].set_state(
                guid,
                GameState.WIN,
            )

    def game_over(self, game_id: str, guid: str) -> None:
        if game_id in self.cards:
            self.cards[game_id].set_state(guid, GameState.GAME_OVER)

    def set_levels_completed(
        self, game_id: str, guid: str, level_completed: int
    ) -> None:
        if game_id in self.cards:
            self.cards[game_id].set_levels_completed(guid, level_completed)

    def get(self, game_id: Optional[str] = None) -> dict[str, Any]:
        if game_id is not None:
            card = self.cards.get(game_id)
            return {game_id: card.model_dump()} if card else {}
        return {k: v.model_dump() for k, v in self.cards.items()}

    def get_card(self, game_id: str) -> Card:
        return self.cards[game_id]

    @computed_field(return_type=int)
    def won(self) -> int:
        return sum([GameState.WIN in g.states for k, g in self.cards.items()])

    @computed_field(return_type=int)
    def played(self) -> int:
        return sum([len(g.states) > 0 for k, g in self.cards.items()])

    @computed_field(return_type=int)
    def total_actions(self) -> int:
        return sum([g.get_total_actions() for k, g in self.cards.items()])

    @computed_field(return_type=int)
    def levels_completed(self) -> int:
        return sum([g.most_levels_completed for k, g in self.cards.items()])

    def get_json_for(self, game_id: str) -> dict[str, Any]:
        card = self.cards.get(game_id)
        return {
            "won": self.won,
            "played": self.played,
            "total_actions": self.total_actions,
            "levels_completed": self.levels_completed,
            "cards": {game_id: card.model_dump()} if card else {},
        }

    def update_scorecard(
        self, guid: str, data: FrameDataRaw, full_reset: bool
    ) -> GameState:
        game_id = data.game_id
        # Needs to happen first
        if data.action_input and data.action_input.id.value in [0]:
            if full_reset:
                self.new_play(game_id, guid)
            else:
                self.reset(game_id, guid)
        if data.action_input and data.action_input.id.value in [1, 2, 3, 4, 5, 6, 7]:
            self.take_action(game_id, guid)
        if data.state:
            if data.state == GameState.GAME_OVER:
                self.game_over(game_id, guid)
            elif data.state == GameState.WIN:
                self.win(game_id, guid)
        self.set_levels_completed(game_id, guid, data.levels_completed)

        self.last_update = datetime.now(timezone.utc)

        card = self.cards.get(game_id)
        return (
            card.states[card.index_of_guid(guid)]
            if card and card.started
            else GameState.NOT_PLAYED
        )


class ScorecardManager:
    """
    Manages the scorecard for all games
    """

    scorecards: dict[str, Scorecard]
    guids: dict[str, str]
    games: list[str]

    def __init__(self, games: list[str] = []) -> None:
        self.scorecards = {}
        self.guids = {}
        self.games = games

    def get_stale_cards(self) -> List[str]:
        idle_for = timedelta(minutes=STALE_MINUTES)
        now = datetime.now(timezone.utc)
        stale_ids = [
            cid
            for cid, sc in self.scorecards.items()
            if now - sc.last_update >= idle_for
        ]
        return stale_ids

    def new_scorecard(
        self,
        source_url: Optional[str],
        tags: Optional[list[str]],
        api_key: str,
        opaque: Any | None,
    ) -> str:
        card_id = str(uuid.uuid4())
        self.scorecards[card_id] = Scorecard.model_validate(
            {
                "games": self.games,
                "source_url": source_url,
                "tags": tags,
                "card_id": card_id,
                "api_key": api_key,
                "opaque": opaque,
            }
        )
        return card_id

    def get_dummy_scorecard(self) -> Scorecard:
        return Scorecard.model_validate({"games": self.games})

    def close_scorecard(
        self, card_id: str, api_key: str | None
    ) -> Tuple[Scorecard, list[str], list[str]] | Tuple[None, None, None]:
        guids: list[str] = []
        game_id_with_guids: list[str] = []
        scorecard = self.scorecards.get(card_id)
        if scorecard and (api_key is None or scorecard.api_key == api_key):
            for card in scorecard.cards.values():
                guids.extend(card.guids)
                game_id_with_guids.extend(f"{g}.{card.game_id}" for g in card.guids)
            del self.scorecards[card_id]
            for guid in guids:
                if guid in self.guids:
                    del self.guids[guid]

            return scorecard, guids, list(set(game_id_with_guids))

        return None, None, None

    def get_scorecard(self, card_id: str, api_key: str) -> Scorecard | None:
        scorecard = self.scorecards.get(card_id)
        if scorecard and scorecard.api_key == api_key:
            return scorecard
        return None

    def get_scorecard_from_guid(self, guid: str) -> Scorecard | None:
        card_id = self.guids.get(guid)
        if card_id is not None:
            return self.scorecards.get(card_id)
        return None

    def add_game(self, card_id: str, guid: str) -> None:
        scorecard = self.scorecards.get(card_id)
        if scorecard:
            self.guids[guid] = card_id

    def update_scorecard(
        self, guid: str, data: FrameDataRaw, full_reset: bool = True
    ) -> GameState:
        card_id = self.guids.get(guid)
        if not card_id:
            return GameState.NOT_PLAYED
        scorecard = self.scorecards.get(card_id)
        if scorecard is None:
            return GameState.NOT_PLAYED
        return scorecard.update_scorecard(guid, data, full_reset)
