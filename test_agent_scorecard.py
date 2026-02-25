import random
import time

from arc_agi import Arcade, OperationMode
from arcengine import GameState

# Initialize the ARC-AGI-3 client
arc = Arcade(operation_mode=OperationMode.ONLINE)

# Create an environment with terminal rendering

card_id = arc.create_scorecard()
print(card_id)

env = arc.make("am92", scorecard_id=card_id)

if env is None:
    print("Failed to create environment")
    exit(1)

# Play the game
for step in range(150):
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

    time.sleep(60)    

# Get and display scorecard
scorecard = arc.close_scorecard(card_id)
if scorecard:
    print(f"Final Score: {scorecard.score}, Actions: {scorecard.total_actions}")
    print(scorecard)
