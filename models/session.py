from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PlayerSession(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    player: uuid.UUID = Field(foreign_key="player.id")
    token: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    last_seen: datetime = Field(default_factory=utc_now)
