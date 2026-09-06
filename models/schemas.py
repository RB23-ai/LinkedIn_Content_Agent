from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class Workspace(BaseModel):
    id: int
    name: str
    industry: Optional[str] = ""
    created_at: datetime


class Idea(BaseModel):
    id: int
    workspace_id: int
    title: str
    description: str
    score: int = 0
    status: str = Field(default="pending", pattern="^(pending|approved|rejected)$")


class Post(BaseModel):
    id: int
    workspace_id: int
    idea_id: Optional[int] = None
    topic: Optional[str] = ""
    content: str
    status: str = Field(default="draft", pattern="^(draft|scheduled|published)$")
    scheduled_date: Optional[str] = None
    linkedin_post_urn: Optional[str] = None
    likes: int = 0
    comments: int = 0
    impressions: int = 0


class Competitor(BaseModel):
    id: int
    workspace_id: int
    name: str
    profile_urn: Optional[str] = ""
    profile_url: Optional[str] = ""


class Lead(BaseModel):
    id: int
    workspace_id: int
    post_id: Optional[int] = None
    commenter_name: Optional[str] = ""
    comment_text: str
    matched_keyword: str
    status: str = Field(default="new", pattern="^(new|contacted|converted|ignored)$")
