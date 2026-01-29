#!/usr/bin/env python3
"""Main entry point for ARC-AGI"""

import random

from arcengine import FrameDataRaw, GameState

import arc_agi
from arc_agi.rendering import render_frames_terminal


def simple_renderer(steps: int, frame_data: FrameDataRaw) -> None:
    """Simple renderer that prints step and high-level info to the screen.

    Args:
        steps: Current step number.
        frame_data: FrameDataRaw object containing game state information.
    """
    render_frames_terminal(steps, frame_data)
    print(f"\n{'=' * 60}")
    print(f"Step: {steps}")
    print(f"Game ID: {frame_data.game_id}")
    print(f"State: {frame_data.state.name}")
    print(f"Levels Completed: {frame_data.levels_completed}")
    print(f"Win Levels: {frame_data.win_levels}")
    if frame_data.action_input:
        action_name = (
            frame_data.action_input.id.name
            if hasattr(frame_data.action_input.id, "name")
            else str(frame_data.action_input.id)
        )
        print(f"Last Action: {action_name}")
        if frame_data.action_input.data:
            print(f"Action Data: {frame_data.action_input.data}")
    print(f"Available Actions: {len(frame_data.available_actions)}")
    print(f"{'=' * 60}\n")


def main() -> None:
    arc = arc_agi.Arcade()

    # for env_info in arc.get_environments():
    #     print(f"Environment: {env_info.game_id} - {env_info.tags}")

    # env = arc.make("ls20", renderer=simple_renderer)
    env = arc.make("ls20", render_mode="terminal-fast")  # or human, terminal-fast
    # env = arc.make("ls20")
    if env is None:
        print("Failed to create environment")
        return

    # print("Environment Info: ", env.info.model_dump_json())

    max_steps = 1000

    for i in range(max_steps):
        # Choose a random action
        random_action = random.choice(env.action_space)
        action_data = (
            {}
            if random_action.is_complex()
            else {
                "x": random.randint(0, 63),
                "y": random.randint(0, 63),
            }
        )
        # Perform the action
        obv = env.step(random_action, data=action_data)

        # Can also use env.observation_space
        if obv is not None and obv.state == GameState.WIN:
            print(f"Game won at step {i}")
            break
        elif obv is not None and obv.state == GameState.GAME_OVER:
            print(f"Game over at step {i}, Resetting Environment")
            env.reset()

    scorecard = arc.close_scorecard()
    if scorecard:
        print("Scorecard: ", scorecard.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
