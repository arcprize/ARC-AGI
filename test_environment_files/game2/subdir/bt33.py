from arcengine import (
    ARCBaseGame,
    Camera,
    GameAction,
    Level,
    Sprite,
)

# Create sprites dictionary with all sprite definitions
sprites = {
    "bad": Sprite(
        pixels=[
            [8],
        ],
        name="bad",
        visible=True,
        collidable=True,
        scale=1,
    ),
    "good": Sprite(
        pixels=[
            [14],
        ],
        name="good",
        visible=True,
        collidable=True,
        scale=1,
    ),
    "left": Sprite(
        pixels=[
            [14, 14],
            [14, -1],
        ],
        name="left",
        visible=True,
        collidable=True,
        tags=["sys_click"],
    ),
    "right": Sprite(
        pixels=[
            [8, 8],
            [-1, 8],
        ],
        name="right",
        visible=True,
        collidable=True,
        tags=["sys_click"],
    ),
}

# Create levels array with all level definitions
levels = [
    # Level 1
    Level(
        sprites=[],
        grid_size=(8, 8),
    ),
    # Level 2
    Level(
        sprites=[],
        grid_size=(16, 16),
    ),
    # Level 3
    Level(
        sprites=[],
        grid_size=(32, 32),
    ),
    # Level 4
    Level(
        sprites=[],
        grid_size=(40, 40),
    ),
    # Level 5
    Level(
        sprites=[],
        grid_size=(48, 48),
    ),
]

BACKGROUND_COLOR = 5

PADDING_COLOR = 3


class Bt33(ARCBaseGame):
    _won: bool = True
    _depth: int = 0
    _placement: int = 0

    def __init__(self) -> None:
        # Create camera
        camera = Camera(
            background=BACKGROUND_COLOR,
            letter_box=PADDING_COLOR,
        )

        # Initialize the base game
        super().__init__(
            game_id="bt33", levels=levels, camera=camera, available_actions=[6]
        )

    def step(self) -> None:
        # Add here any logic you want
        if self.action.id == GameAction.ACTION6:
            x = self.action.data.get("x", 0)
            y = self.action.data.get("y", 0)

            coords = self.camera.display_to_grid(x, y)
            if coords:
                sprite = self.current_level.get_sprite_at(coords[0], coords[1])
                if sprite and sprite.name == "left":
                    if self._depth > 0:
                        self._placement -= 1
                    sprite_name = "good"
                    if not self._won:
                        sprite_name = "bad"
                    self.current_level.add_sprite(
                        sprites[sprite_name]
                        .clone()
                        .set_position(self._placement, self._depth)
                    )

                    self._depth += 1
                elif sprite and sprite.name == "right":
                    self._placement += 1
                    self.current_level.add_sprite(
                        sprites["bad"]
                        .clone()
                        .set_position(self._placement, self._depth)
                    )
                    self._won = False
                    self._depth += 1

        if self._depth >= self.camera.width // 2:
            if self._won:
                self.next_level()
            else:
                self.lose()

        self.complete_action()

    def on_set_level(self, level: Level) -> None:
        self._depth = 0
        self._placement = self.camera.width // 2 - 1
        self._won = True
        scale = self._current_level_index
        if scale == 0:
            self.current_level.add_sprite(
                sprites["left"].clone().set_position(0, 0).set_scale(1)
            )
            self.current_level.add_sprite(
                sprites["right"]
                .clone()
                .set_position(self.camera.width - 2, 0)
                .set_scale(1)
            )
        else:
            self.current_level.add_sprite(
                sprites["left"].clone().set_position(0, 0).set_scale(scale)
            )
            self.current_level.add_sprite(
                sprites["right"]
                .clone()
                .set_position(self.camera.width - (2 * scale), 0)
                .set_scale(scale)
            )
