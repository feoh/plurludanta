
from sqlmodel import Field, SQLModel
import uuid

class LocationExit(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str  # e.g., "north", "door", "stairs"
    location: uuid.UUID = Field(foreign_key="location.id")
    destination: uuid.UUID = Field(foreign_key="location.id")
    description: str = "An exit."

