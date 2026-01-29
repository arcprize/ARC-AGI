import random

from arcengine import GameState

import arc_agi

# Initialize the ARC-AGI-3 client
arc = arc_agi.Arcade()

# Create an environment with terminal rendering
env = arc.make("ls20", render_mode="terminal")
if env is None:
    print("Failed to create environment")
    exit(1)

# Play the game
for step in range(100):
    # Choose a random action
    action = random.choice(env.action_space)
    action_data = {}
    if action.is_complex():
        action_data = {
            "x": random.randint(0, 63),
            "y": random.randint(0, 63),
        }

    # Perform the action (rendering happens automatically)
    obs = env.step(action, data=action_data)

    # Check game state
    if obs and obs.state == GameState.WIN:
        print(f"Game won at step {step}!")
        break
    elif obs and obs.state == GameState.GAME_OVER:
        env.reset()

# Get and display scorecard
scorecard = arc.get_scorecard()
if scorecard:
    print(f"Final Score: {scorecard.score}, Actions: {scorecard.total_actions}")
