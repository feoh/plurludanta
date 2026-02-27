from sqlmodel import Field, SQLModel
import uuid

class Thing(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    description: str = "An ordinary thing."
    location: uuid.UUID | None = Field(default=None, foreign_key="location.id")
    owner: uuid.UUID | None = Field(default=None, foreign_key="player.id")
