"""Pydantic schemas for Quora lead extraction."""

from typing import List
from pydantic import BaseModel, Field


class QuoraUserInteractionSchema(BaseModel):
    """Schema for a single Quora user interaction (question or answer)."""

    username: str = Field(description="Username of poster")
    bio: str = Field(description="User bio")
    post_type: str = Field(description="Type: question/answer")
    timestamp: str = Field(description="Post time")
    upvotes: int = Field(default=0)
    profile_url: str = Field(default="", description="Link to user's Quora profile")


class QuoraPageSchema(BaseModel):
    """Schema for extracted data from a Quora page."""

    user_interactions: List[QuoraUserInteractionSchema] = Field(
        default_factory=list,
        description="List of user interactions found on the page",
    )


class FlattenedLead(BaseModel):
    """A single flattened lead record ready for export."""

    website_url: str = ""
    username: str = ""
    bio: str = ""
    post_type: str = ""
    timestamp: str = ""
    upvotes: int = 0
    profile_url: str = ""
