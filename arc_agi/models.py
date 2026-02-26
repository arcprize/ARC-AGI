"""Pydantic models for ARC-AGI-3 environments."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class APIError(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    GAME_NOT_AVAILABLE_ERROR = "GAME_NOT_AVAILABLE_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    GAME_NOT_STARTED_ERROR = "GAME_NOT_STARTED_ERROR"


class EnvironmentInfo(BaseModel):
    """Information about an ARC-AGI-3 environment.

    This class can be serialized to and deserialized from JSON.
    Note: local_dir is excluded from JSON serialization as it's runtime-only.
    """

    game_id: str
    title: Optional[str] = None
    default_fps: Optional[int] = None
    tags: Optional[list[str]] = None
    baseline_actions: Optional[list[int]] = None
    date_downloaded: Optional[datetime] = None
    class_name: Optional[str] = None
    local_dir: Optional[str] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def set_defaults(self) -> "EnvironmentInfo":
        """Set default values for date_downloaded and class_name if not provided."""
        # Set date_downloaded to now if not provided
        if self.date_downloaded is None:
            self.date_downloaded = datetime.now(timezone.utc)

        if self.default_fps is None:
            self.default_fps = 5

        # Set class_name from game_id if not provided
        if self.class_name is None:
            # Take first 4 characters and capitalize first letter only
            if len(self.game_id) >= 4:
                first_four = self.game_id[:4]
                self.class_name = first_four[0].upper() + first_four[1:]
            else:
                # If game_id is shorter than 4 characters, capitalize first letter only
                if self.game_id:
                    self.class_name = self.game_id[0].upper() + self.game_id[1:]
                else:
                    self.class_name = ""

        return self

    def model_dump_json(self, **kwargs: Any) -> str:
        """Serialize to JSON string.

        Note: local_dir is automatically excluded from serialization.
        """
        return super().model_dump_json(**kwargs)

    @classmethod
    def model_validate_json(
        cls,
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> "EnvironmentInfo":
        """Deserialize from JSON string."""
        return super().model_validate_json(
            json_data,
            strict=strict,
            context=context,
            by_alias=by_alias,
            by_name=by_name,
        )
