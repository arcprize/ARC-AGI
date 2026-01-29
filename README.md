# ARG-AGI

ARC-AGI Toolkit is an open-sourced python interface (API) for ARC-AGI-3 interactive environments. It provides a consistent API and tooling layer that lets agents interact with ARC-AGI-3 environments, locally or via API.

## QuickStart

### Prerequisites

1. **Installation**:
   ```bash
   uv add arc-agi
   # or
   pip install arc-agi
   ```

2. **API Key**: You can optionally set the `ARC_API_KEY` environment variable with your API key. If no key is provided, an anonymous key will be used. However, registering for an API key will give you access to more games at release. [Register for an API key at https://three.arcprize.org](https://three.arcprize.org)
   
   The code supports loading from `.env` and `.env.example` files (using python-dotenv), or you can set it directly:
   ```bash
   export ARC_API_KEY="your-api-key-here"
   ```
   
   Or create a `.env` file in your project root:
   ```bash
   echo 'ARC_API_KEY=your-api-key-here' > .env
   ```

### REPL Example

Get up and running with arc-agi in just 4 lines:

```python
import arc_agi
from arcengine import GameAction
arc = arc_agi.Arcade()
env = arc.make("ls20", render_mode="terminal")
```

See the actions you can take, take one, and check your scorecard:

```python
print(env.action_space)
obs = env.step(GameAction.ACTION1)
print(arc.get_scorecard())
```

### Minimal Example

Here's a minimal example that plays a game and renders it in the terminal:

```python
import random

from arcengine import GameAction, GameState
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
    print(f"Final Score: {scorecard.score}")
```

### Rendering Options

You can render games in two ways:

1. **Terminal rendering** (text-based, default_fps bounded):
   ```python
   env = arc.make("ls20", render_mode="terminal")
   ```

2. **Terminal rendering** (text-based, unbounded):
   ```python
   env = arc.make("ls20", render_mode="terminal-fast")
   ```

3. **Human rendering** (matplotlib visualization, default_fps bounded):
   ```python
   env = arc.make("ls20", render_mode="human")
   ```

4. **Custom renderer** (provide your own function):
   ```python
   from arcengine import FrameDataRaw
   
   def my_renderer(steps: int, frame_data: FrameDataRaw) -> None:
       print(f"Step {steps}: {frame_data.state.name}")
   
   env = arc.make("ls20", renderer=my_renderer)
   ```

## API Reference

### Arcade Class

The `Arcade` class is the main entry point for interacting with ARC-AGI-3 environments. It handles configuration, environment discovery, and scorecard management.

#### Constructor Parameters

The `Arcade` constructor accepts the following parameters. All parameters can be overridden by environment variables, with constructor arguments taking precedence over environment variables.

| Parameter | Type | Default | Environment Variable | Description |
|-----------|------|---------|---------------------|-------------|
| `arc_api_key` | `str` | `""` | `ARC_API_KEY` | API key for ARC API. If empty and not in offline mode, an anonymous key will be automatically fetched. |
| `arc_base_url` | `str` | `"https://three.arcprize.org"` | `ARC_BASE_URL` | Base URL for the ARC API. |
| `operation_mode` | `OperationMode` | `OperationMode.NORMAL` | `OPERATION_MODE` | `NORMAL` (local + API), `ONLINE` (API only), or `OFFLINE` (local only). |
| `environments_dir` | `str` | `"environment_files"` | `ENVIRONMENTS_DIR` | Directory to scan for local `metadata.json` files. |
| `recordings_dir` | `str` | `"recordings"` | `RECORDINGS_DIR` | Directory to save game recordings (JSONL format). |
| `logger` | `logging.Logger` | `None` | - | Optional logger instance. If not provided, a default logger logging to STDOUT is created. |

**Example:**
```python
from arc_agi import Arcade, OperationMode

# Use defaults (loads from environment variables or uses defaults)
arc = Arcade()

# Override specific parameters
arc = Arcade(
    arc_api_key="my-key",
    operation_mode=OperationMode.OFFLINE,
    environments_dir="./my_games"
)
```

#### Methods

##### `make(game_id, seed=0, scorecard_id=None, save_recording=False, render_mode=None, renderer=None)`

Create and initialize an environment wrapper for a specific game.

**Parameters:**
- `game_id` (`str`): Game identifier in format `'ls20'` or `'ls20-1234abcd'`. The first 4 characters are the game_id, everything after `'-'` is the version.
- `seed` (`int`, optional): Random seed for the game. Defaults to `0`.
- `scorecard_id` (`str`, optional): Scorecard ID for tracking runs. If `None` is provided (the default), the system will create and maintain a single default scorecard that is automatically reused across all `make()` calls. This allows you to track multiple games in the same scorecard without explicitly managing scorecard IDs.
- `save_recording` (`bool`, optional): Whether to save recordings to JSONL file. Defaults to `False`.
- `render_mode` (`str`, optional): Render mode string (`"human"`, `"terminal"`, `"terminal-fast"`). If provided, creates a renderer automatically.
- `renderer` (`Callable[[int, FrameDataRaw], None]`, optional): Custom renderer function. If both `render_mode` and `renderer` are provided, `renderer` takes precedence.

**Returns:**
- `EnvironmentWrapper` or `None`: Returns an `EnvironmentWrapper` instance if successful, `None` otherwise.

**Example:**
```python
env = arc.make("ls20", render_mode="terminal")
env = arc.make("ls20-1234abcd", seed=42, save_recording=True)
```

##### `get_environments()`

Get the list of available environments (both local and remote).

**Returns:**
- `list[EnvironmentInfo]`: List of `EnvironmentInfo` objects representing available environments.

**Example:**
```python
envs = arc.get_environments()
for env in envs:
    print(f"{env.game_id}: {env.title}")
```

##### `create_scorecard(source_url=None, tags=None, opaque=None)`

Create a new scorecard for tracking game runs.

**Parameters:**
- `source_url` (`str`, optional): Optional source URL for the scorecard.
- `tags` (`list[str]`, optional): Optional list of tags for the scorecard. Defaults to `["wrapper"]`.
- `opaque` (`Any`, optional): Optional opaque data for the scorecard.

**Returns:**
- `str`: The ID of the newly created scorecard.

**Example:**
```python
scorecard_id = arc.create_scorecard(
    source_url="https://github.com/my/repo",
    tags=["experiment", "v1"]
)
```

##### `open_scorecard(source_url=None, tags=None, opaque=None)`

Alias for `create_scorecard()`. Opens a new scorecard.

**Parameters:** Same as `create_scorecard()`.

**Returns:**
- `str`: The ID of the newly created scorecard.

##### `get_scorecard(scorecard_id=None)`

Get a scorecard by ID, converted to `EnvironmentScorecard`.

**Parameters:**
- `scorecard_id` (`str`, optional): Scorecard ID. If `None` is provided (the default), returns the default scorecard that the system is currently using (the same one created automatically when `make()` is called with `scorecard_id=None`).

**Returns:**
- `EnvironmentScorecard` or `None`: Scorecard object if found, `None` otherwise.

**Example:**
```python
scorecard = arc.get_scorecard()
if scorecard:
    print(f"Score: {scorecard.score}")
    print(f"Games played: {len(scorecard.games)}")
```

##### `close_scorecard(scorecard_id=None)`

Close a scorecard and return the final scorecard data.

**Parameters:**
- `scorecard_id` (`str`, optional): Scorecard ID. If `None` is provided (the default), closes the default scorecard that the system is currently using (the same one created automatically when `make()` is called with `scorecard_id=None`). After closing, the default scorecard is cleared and a new one will be created on the next `make()` call.

**Returns:**
- `EnvironmentScorecard` or `None`: Final scorecard object if found, `None` otherwise.

**Example:**
```python
final_scorecard = arc.close_scorecard()
if final_scorecard:
    print(f"Final score: {final_scorecard.score}")
```

### EnvironmentWrapper Class

The `EnvironmentWrapper` class provides a common interface for interacting with environments, whether they are local (`LocalEnvironmentWrapper`) or remote (`RemoteEnvironmentWrapper`).

#### Properties

##### `observation_space`

Get the observation space (last response data).

**Returns:**
- `FrameDataRaw` or `None`: The `FrameDataRaw` object from the last response, or `None` if no response has been set yet.

**Example:**
```python
obs = env.observation_space
if obs:
    print(f"Game state: {obs.state}")
    print(f"Levels completed: {obs.levels_completed}")
```

##### `action_space`

Get the action space (available actions).

**Returns:**
- `list[GameAction]`: A list of `GameAction` objects representing available actions. Returns an empty list if no response has been set yet.

**Example:**
```python
actions = env.action_space
print(f"Available actions: {[a.name for a in actions]}")
```

##### `info`

Get the environment information.

**Returns:**
- `EnvironmentInfo`: The `EnvironmentInfo` object for this environment.

**Example:**
```python
info = env.info
print(f"Game ID: {info.game_id}")
print(f"Title: {info.title}")
print(f"Tags: {info.tags}")
```

#### Methods

##### `reset()`

Reset the environment and return the initial frame data.

**Returns:**
- `FrameDataRaw` or `None`: `FrameDataRaw` object with initial game state, or `None` if reset failed.

**Example:**
```python
obs = env.reset()
if obs:
    print("Environment reset successfully")
```

##### `step(action, data=None, reasoning=None)`

Perform a step in the environment.

**Parameters:**
- `action` (`GameAction`): The game action to perform (e.g., `GameAction.ACTION1`, `GameAction.ACTION2`).
- `data` (`dict[str, Any]`, optional): Optional action data dictionary. For complex actions, should contain `"x"` and `"y"` coordinates.
- `reasoning` (`dict[str, Any]`, optional): Optional reasoning dictionary to include in recordings.

**Returns:**
- `FrameDataRaw` or `None`: `FrameDataRaw` object with updated game state, or `None` if step failed.

**Example:**
```python
from arcengine import GameAction

# Simple action
obs = env.step(GameAction.ACTION1)

# Complex action with coordinates
obs = env.step(
    GameAction.ACTION6,
    data={"x": 32, "y": 32},
    reasoning={"thought": "clicking center of screen"}
)

# Check game state after step
if obs and obs.state == GameState.WIN:
    print("Game won!")
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

## Citation

If you use this project in your research, please cite it as:

```bibtex
@software{arc_agi,
  author       = {ARC Prize Foundation},
  title        = {ARC-AGI Toolkit},
  year         = {2026},
  url          = {https://github.com/arcprize/ARC-AGI},
  version      = {0.9.1}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
