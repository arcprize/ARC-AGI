"""Rendering utilities for ARC-AGI-3 environments."""

import sys
import time
from typing import Any, Optional, Tuple

try:
    import matplotlib.animation as animation
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except ImportError:
    plt = None
    animation = None
    HAS_MATPLOTLIB = False

from arcengine import FrameDataRaw
from numpy import ndarray

# Color mapping for frame values (0-15)
COLOR_MAP: dict[int, str] = {
    0: "#FFFFFFFF",  # White
    1: "#CCCCCCFF",  # Off-white
    2: "#999999FF",  # neutral Light
    3: "#666666FF",  # neutral
    4: "#333333FF",  # Off Black
    5: "#000000FF",  # Black
    6: "#E53AA3FF",  # Magenta
    7: "#FF7BCCFF",  # Magenta Light
    8: "#F93C31FF",  # Red
    9: "#1E93FFFF",  # Blue
    10: "#88D8F1FF",  # Blue Light
    11: "#FFDC00FF",  # Yellow
    12: "#FF851BFF",  # Orange
    13: "#921231FF",  # Maroon
    14: "#4FCC30FF",  # Green
    15: "#A356D6FF",  # Purple
}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple.

    Args:
        hex_color: Hex color string (e.g., "#FFFFFFFF").

    Returns:
        RGB tuple (r, g, b).
    """
    # Remove '#' and convert to int
    hex_color = hex_color.lstrip("#")
    # Parse RGBA hex (8 chars) or RGB hex (6 chars)
    if len(hex_color) == 8:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        # Alpha is ignored for display
    else:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    return (r, g, b)


def frame_to_rgb_array(
    steps: int,
    frame: ndarray,
    scale: int = 4,
    color_map: Optional[dict[int, str]] = None,
) -> ndarray:
    """Convert a frame to an RGB numpy array for matplotlib.

    Args:
        frame: 2D numpy array (64x64) with values 0-15.
        scale: Upscaling factor (default 4, so 64x64 -> 256x256).
        color_map: Optional color mapping dict. Uses default if None.

    Returns:
        3D numpy array (height, width, 3) with RGB values.
    """
    import numpy as np

    if color_map is None:
        color_map = COLOR_MAP

    height, width = frame.shape
    upscaled_height = height * scale
    upscaled_width = width * scale

    # Create RGB array
    rgb_array = np.zeros((upscaled_height, upscaled_width, 3), dtype=np.uint8)

    # Fill pixels
    for y in range(height):
        for x in range(width):
            value = int(frame[y, x])
            hex_color = color_map.get(value, "#000000FF")
            rgb = hex_to_rgb(hex_color)

            # Fill the scaled block
            for dy in range(scale):
                for dx in range(scale):
                    rgb_array[y * scale + dy, x * scale + dx] = rgb

    return rgb_array


def render_frames(
    steps: int,
    frame_data: FrameDataRaw,
    default_fps: Optional[int] = None,
    scale: int = 4,
    color_map: Optional[dict[int, str]] = None,
) -> None:
    """Render multiple frames with optional FPS control using matplotlib.

    Args:
        frame_data: FrameDataRaw object containing frame data and other information.
        default_fps: Optional FPS for frame timing. If None, displays immediately.
        scale: Upscaling factor (default 4, so 64x64 -> 256x256).
        color_map: Optional color mapping dict. Uses default if None.
    """
    if not HAS_MATPLOTLIB or plt is None or animation is None:
        raise ImportError(
            "matplotlib is required for rendering. Install with: pip install matplotlib"
        )

    frames = frame_data.frame
    if not frames:
        return

    # Convert frames to RGB arrays
    frame_images = [
        frame_to_rgb_array(steps, frame, scale, color_map) for frame in frames
    ]

    # Calculate interval between frames if FPS is specified
    interval = (1000.0 / default_fps) if default_fps and default_fps > 0 else 100

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.axis("off")
    ax.set_title("ARC-AGI-3 Environment")

    # Display first frame
    im = ax.imshow(frame_images[0], interpolation="nearest")
    plt.tight_layout()

    def update_frame(frame_num: int) -> Tuple[Any, ...]:
        """Update the displayed frame."""
        if frame_num < len(frame_images):
            im.set_array(frame_images[frame_num])
            return (im,)
        return (im,)

    # Create animation that plays automatically
    # Keep reference to prevent garbage collection
    anim = animation.FuncAnimation(
        fig,
        update_frame,
        frames=len(frame_images),
        interval=interval,
        blit=False,
        repeat=False,
    )

    # Show the plot - animation will play automatically
    # Use non-blocking mode so frames play and code continues
    plt.ion()  # Turn on interactive mode
    plt.show(block=False)

    # Wait for animation to complete (frames * interval + small buffer)
    if interval > 0:
        total_time = len(frame_images) * interval / 1000.0
    else:
        total_time = len(frame_images) * 0.1  # Default 100ms per frame

    # Small initial pause to ensure window appears and animation starts
    time.sleep(0.1)

    # Use plt.pause to process events and let animation play
    # This ensures the animation actually renders
    plt.pause(total_time + 0.1)

    # Keep animation reference alive until we're done
    # Close the figure after animation completes
    plt.close(fig)
    plt.ioff()  # Turn off interactive mode

    # Explicitly delete animation after closing to avoid warnings
    del anim


def rgb_to_ansi(rgb: tuple[int, int, int]) -> str:
    """Convert RGB tuple to ANSI color code.

    Args:
        rgb: RGB tuple (r, g, b).

    Returns:
        ANSI escape sequence for the color.
    """
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m"


def render_frames_terminal(
    steps: int,
    frame_data: FrameDataRaw,
    default_fps: Optional[int] = None,
    scale: int = 1,
    color_map: Optional[dict[int, str]] = None,
    skip_deplay: bool = False,
) -> None:
    """Render frames in the terminal using ANSI color codes, overwriting in place.

    Args:
        frame_data: FrameDataRaw object containing frame data and other information.
        default_fps: Optional FPS for frame timing. If None, displays immediately.
        scale: Scaling factor (default 1, terminal uses 2 chars per pixel for better visibility).
        color_map: Optional color mapping dict. Uses default if None.
    """
    frames = frame_data.frame
    if not frames:
        return

    if color_map is None:
        color_map = COLOR_MAP

    # Check if terminal supports colors
    if not sys.stdout.isatty():
        print(
            "Warning: Not a terminal, colors may not display correctly", file=sys.stderr
        )

    # Calculate delay between frames (default 5 FPS if not specified)
    fps = default_fps if default_fps and default_fps > 0 else 5
    delay = 1.0 / fps

    # ANSI codes
    RESET = "\033[0m"
    HOME = "\033[H"  # Move cursor to home position (top-left)
    HIDE_CURSOR = "\033[?25l"  # Hide cursor
    SHOW_CURSOR = "\033[?25h"  # Show cursor
    # Use block character for better visibility (2 chars wide)
    BLOCK = "██"

    # Get frame dimensions
    height, width = frames[0].shape

    # Build frame strings for all frames (as single strings to reduce flicker)
    frame_strings = []
    for frame_idx, frame in enumerate(frames):
        # Build entire frame as one string
        frame_str = f"Step: {steps} - State: {frame_data.state.name}\n\n"

        # Frame content - build all lines first, then join
        frame_lines = []
        for y in range(height):
            line_parts = []
            for x in range(width):
                value = int(frame[y, x])
                hex_color = color_map.get(value, "#000000FF")
                rgb = hex_to_rgb(hex_color)
                ansi_color = rgb_to_ansi(rgb)
                # Use block character (2 chars) for better visibility
                line_parts.append(f"{ansi_color}{BLOCK}{RESET}")
            frame_lines.append("".join(line_parts))

        frame_str += "\n".join(frame_lines)
        frame_strings.append(frame_str)

    # Hide cursor to reduce flicker
    print(HIDE_CURSOR, end="", flush=True)

    try:
        # First frame: clear screen and display in single operation to reduce flicker
        print(f"{HOME}\033[2J{frame_strings[0]}", end="", flush=True)

        # Update frames in place - single operation per frame to minimize flicker
        for frame_idx in range(1, len(frames)):
            # Single operation: move home + print new frame (no separate operations)
            print(f"{HOME}{frame_strings[frame_idx]}", end="", flush=True)
            # Sleep for 1/fps seconds between frames
            if not skip_deplay:
                time.sleep(delay)
    finally:
        # Always show cursor again
        print(SHOW_CURSOR, end="", flush=True)

    # Reset terminal colors and move cursor below the frame
    print(f"\n{RESET}", end="", flush=True)
    if not skip_deplay:
        time.sleep(delay)
