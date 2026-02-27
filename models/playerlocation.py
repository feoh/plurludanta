from sqlmodel import Field, SQLModel
import uuid

class PlayerLocation(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    player: uuid.UUID = Field(unique=True, foreign_key="player.id")
    location: uuid.UUID = Field(foreign_key="location.id")
    description: str = "A nondescript player."

