from sqlmodel import SQLModel, create_engine, select, Session
from fastapi import FastAPI, Request, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.player import Player
from models.thing import Thing
from models.location import Location
from models.playerlocation import PlayerLocation
from models.locationexit import LocationExit
from models.session import PlayerSession
from datetime import datetime, timezone
from typing import Annotated
import uuid
import secrets
import hashlib


def initialize_database():
    sqlite_file_name = "plurludanta.db"
    sqlite_url = "sqlite:///" + sqlite_file_name
    engine = create_engine(sqlite_url, echo=True)
    SQLModel.metadata.create_all(engine)
    return engine


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_current_player(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: SessionDep,
) -> Player | None:
    """Get the current authenticated player from the bearer token."""
    if credentials is None:
        return None
    token = credentials.credentials
    player_session = session.exec(
        select(PlayerSession).where(PlayerSession.token == token)
    ).first()
    if player_session is None:
        return None
    # Update last_seen
    player_session.last_seen = datetime.now(timezone.utc)
    session.add(player_session)
    session.commit()
    return session.get(Player, player_session.player)


CurrentPlayer = Annotated[Player | None, Depends(get_current_player)]


def require_auth(player: CurrentPlayer) -> Player:
    """Dependency that requires authentication."""
    if player is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return player


AuthenticatedPlayer = Annotated[Player, Depends(require_auth)]


def initialize_world():
    with Session(engine) as session:
        # Check if world already initialized
        existing = session.exec(select(Location)).first()
        if existing:
            return

        # Create Limbo, the first location
        limbo = Location(
            name="Limbo",
            description="In the beginning, there was Limbo. It is a formless void, "
            "waiting to be shaped into something more.",
        )
        session.add(limbo)
        session.commit()

        # Create a second location
        garden = Location(
            name="Garden",
            description="A peaceful garden with colorful flowers and a gentle breeze.",
        )
        session.add(garden)
        session.commit()

        # Create exits between locations
        exit_to_garden = LocationExit(
            name="garden",
            location=limbo.id,
            destination=garden.id,
            description="A shimmering portal leads to a garden.",
        )
        exit_to_limbo = LocationExit(
            name="void",
            location=garden.id,
            destination=limbo.id,
            description="A dark portal leads back to the void.",
        )
        session.add(exit_to_garden)
        session.add(exit_to_limbo)
        session.commit()

        # Create a thing in the garden
        flower = Thing(
            name="flower",
            description="A beautiful red flower.",
            location=garden.id,
        )
        session.add(flower)
        session.commit()


engine = initialize_database()
app = FastAPI(title="Plurludanta", description="A multiplayer game server")


# WebSocket connection manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[uuid.UUID, WebSocket] = {}

    async def connect(self, player_id: uuid.UUID, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[player_id] = websocket

    def disconnect(self, player_id: uuid.UUID):
        self.active_connections.pop(player_id, None)

    async def send_to_player(self, player_id: uuid.UUID, message: dict):
        if player_id in self.active_connections:
            await self.active_connections[player_id].send_json(message)

    async def broadcast_to_location(
        self, location_id: uuid.UUID, message: dict, exclude: uuid.UUID | None = None
    ):
        with Session(engine) as session:
            players_in_location = session.exec(
                select(PlayerLocation).where(PlayerLocation.location == location_id)
            ).all()
            for pl in players_in_location:
                if pl.player != exclude and pl.player in self.active_connections:
                    await self.active_connections[pl.player].send_json(message)


manager = ConnectionManager()


# === Utility Routes ===


@app.get("/listroutes")
def get_all_urls_from_request(request: Request):
    url_list = [
        {"path": route.path, "name": route.name} for route in request.app.routes
    ]
    return url_list


# === Authentication Routes ===


@app.post("/auth/register")
def register_player(player_name: str, password: str, session: SessionDep):
    """Register a new player with a password."""
    existing = session.exec(select(Player).where(Player.name == player_name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Player name already taken")

    player = Player(name=player_name, password_hash=hash_password(password))
    session.add(player)
    session.commit()
    session.refresh(player)

    # Place new player in Limbo
    limbo = session.exec(select(Location).where(Location.name == "Limbo")).first()
    if limbo:
        player_location = PlayerLocation(player=player.id, location=limbo.id)
        session.add(player_location)
        session.commit()

    return {"id": player.id, "name": player.name}


@app.post("/auth/login")
def login_player(player_name: str, password: str, session: SessionDep):
    """Login and receive a session token."""
    player = session.exec(select(Player).where(Player.name == player_name)).first()
    if not player or player.password_hash != hash_password(password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create session token
    token = secrets.token_urlsafe(32)
    player_session = PlayerSession(player=player.id, token=token)
    session.add(player_session)
    session.commit()

    return {"token": token, "player_id": player.id}


@app.post("/auth/logout")
def logout_player(player: AuthenticatedPlayer, session: SessionDep):
    """Logout and invalidate the session token."""
    # Delete the session
    player_sessions = session.exec(
        select(PlayerSession).where(PlayerSession.player == player.id)
    ).all()
    for ps in player_sessions:
        session.delete(ps)
    session.commit()
    return {"message": "Logged out"}


# === Player Routes ===


@app.post("/player/create/{player_name}")
def create_player(player_name: str, session: SessionDep):
    """Create a player without authentication (for backwards compatibility)."""
    existing = session.exec(select(Player).where(Player.name == player_name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Player name already taken")

    player = Player(name=player_name)
    session.add(player)
    session.commit()
    session.refresh(player)
    return player.id


@app.get("/player/list")
def list_players(session: SessionDep):
    statement = select(Player)
    players = session.exec(statement)
    return players.all()


@app.delete("/player/delete/{player_id}")
def delete_player(player_id: uuid.UUID, session: SessionDep):
    player = session.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    session.delete(player)
    session.commit()
    return player_id


@app.get("/player/get/{player_id}")
def get_player(player_id: uuid.UUID, session: SessionDep):
    player = session.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@app.get("/player/me")
def get_current_player_info(player: AuthenticatedPlayer):
    """Get the current authenticated player's info."""
    return {"id": player.id, "name": player.name}


# === Game Action Routes ===


@app.get("/player/look")
def look(player: AuthenticatedPlayer, session: SessionDep):
    """Look around the current location."""
    player_location = session.exec(
        select(PlayerLocation).where(PlayerLocation.player == player.id)
    ).first()

    if not player_location:
        raise HTTPException(status_code=404, detail="Player has no location")

    location = session.get(Location, player_location.location)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    # Get other players in this location
    other_players_locations = session.exec(
        select(PlayerLocation).where(
            PlayerLocation.location == location.id, PlayerLocation.player != player.id
        )
    ).all()
    other_players = []
    for pl in other_players_locations:
        p = session.get(Player, pl.player)
        if p:
            other_players.append({"id": p.id, "name": p.name})

    # Get things in this location
    things = session.exec(
        select(Thing).where(Thing.location == location.id)
    ).all()
    things_list = [{"id": t.id, "name": t.name, "description": t.description} for t in things]

    # Get exits from this location
    exits = session.exec(
        select(LocationExit).where(LocationExit.location == location.id)
    ).all()
    exits_list = [{"id": e.id, "name": e.name, "description": e.description} for e in exits]

    return {
        "location": {
            "id": location.id,
            "name": location.name,
            "description": location.description,
        },
        "players": other_players,
        "things": things_list,
        "exits": exits_list,
    }


@app.post("/player/move/{exit_name}")
async def move_player(exit_name: str, player: AuthenticatedPlayer, session: SessionDep):
    """Move through an exit to another location."""
    player_location = session.exec(
        select(PlayerLocation).where(PlayerLocation.player == player.id)
    ).first()

    if not player_location:
        raise HTTPException(status_code=404, detail="Player has no location")

    # Find the exit
    exit = session.exec(
        select(LocationExit).where(
            LocationExit.location == player_location.location,
            LocationExit.name == exit_name,
        )
    ).first()

    if not exit:
        raise HTTPException(status_code=404, detail=f"No exit named '{exit_name}' here")

    old_location_id = player_location.location
    new_location = session.get(Location, exit.destination)

    # Update player location
    player_location.location = exit.destination
    session.add(player_location)
    session.commit()

    # Broadcast to old location
    await manager.broadcast_to_location(
        old_location_id,
        {"event": "player_left", "player": player.name, "exit": exit_name},
        exclude=player.id,
    )

    # Broadcast to new location
    await manager.broadcast_to_location(
        exit.destination,
        {"event": "player_arrived", "player": player.name},
        exclude=player.id,
    )

    return {
        "message": f"You move through the {exit_name}.",
        "location": new_location.name if new_location else "Unknown",
    }


@app.get("/player/inventory")
def get_inventory(player: AuthenticatedPlayer, session: SessionDep):
    """List items in the player's inventory."""
    things = session.exec(select(Thing).where(Thing.owner == player.id)).all()
    return [{"id": t.id, "name": t.name, "description": t.description} for t in things]


@app.post("/player/pickup/{thing_name}")
async def pickup_thing(thing_name: str, player: AuthenticatedPlayer, session: SessionDep):
    """Pick up a thing from the current location."""
    player_location = session.exec(
        select(PlayerLocation).where(PlayerLocation.player == player.id)
    ).first()

    if not player_location:
        raise HTTPException(status_code=404, detail="Player has no location")

    # Find the thing in this location
    thing = session.exec(
        select(Thing).where(
            Thing.location == player_location.location, Thing.name == thing_name
        )
    ).first()

    if not thing:
        raise HTTPException(
            status_code=404, detail=f"No '{thing_name}' here to pick up"
        )

    # Move thing to player's inventory
    thing.location = None
    thing.owner = player.id
    session.add(thing)
    session.commit()

    # Broadcast to location
    await manager.broadcast_to_location(
        player_location.location,
        {"event": "thing_taken", "player": player.name, "thing": thing_name},
        exclude=player.id,
    )

    return {"message": f"You pick up the {thing_name}."}


@app.post("/player/drop/{thing_name}")
async def drop_thing(thing_name: str, player: AuthenticatedPlayer, session: SessionDep):
    """Drop a thing from inventory into the current location."""
    player_location = session.exec(
        select(PlayerLocation).where(PlayerLocation.player == player.id)
    ).first()

    if not player_location:
        raise HTTPException(status_code=404, detail="Player has no location")

    # Find the thing in player's inventory
    thing = session.exec(
        select(Thing).where(Thing.owner == player.id, Thing.name == thing_name)
    ).first()

    if not thing:
        raise HTTPException(
            status_code=404, detail=f"You don't have a '{thing_name}'"
        )

    # Drop thing in current location
    thing.owner = None
    thing.location = player_location.location
    session.add(thing)
    session.commit()

    # Broadcast to location
    await manager.broadcast_to_location(
        player_location.location,
        {"event": "thing_dropped", "player": player.name, "thing": thing_name},
        exclude=player.id,
    )

    return {"message": f"You drop the {thing_name}."}


@app.post("/player/say")
async def say_message(message: str, player: AuthenticatedPlayer, session: SessionDep):
    """Say something to everyone in the current location."""
    player_location = session.exec(
        select(PlayerLocation).where(PlayerLocation.player == player.id)
    ).first()

    if not player_location:
        raise HTTPException(status_code=404, detail="Player has no location")

    # Broadcast to location
    await manager.broadcast_to_location(
        player_location.location,
        {"event": "say", "player": player.name, "message": message},
        exclude=player.id,
    )

    return {"message": f'You say "{message}"'}


# === Thing Routes ===


@app.post("/thing/create/{thing_name}")
def create_thing(thing_name: str, session: SessionDep):
    thing = Thing(name=thing_name)
    session.add(thing)
    session.commit()
    return thing.id


@app.delete("/thing/delete/{thing_id}")
def delete_thing(thing_id: uuid.UUID, session: SessionDep):
    thing = session.get(Thing, thing_id)
    if not thing:
        raise HTTPException(status_code=404, detail="Thing not found")
    session.delete(thing)
    session.commit()
    return thing_id


@app.get("/thing/get/{thing_id}")
def get_thing(thing_id: uuid.UUID, session: SessionDep):
    thing = session.get(Thing, thing_id)
    if not thing:
        raise HTTPException(status_code=404, detail="Thing not found")
    return thing


@app.get("/thing/list")
def list_things(session: SessionDep):
    statement = select(Thing)
    things = session.exec(statement)
    return things.all()


# === Location Routes ===


@app.post("/location/create/{location_name}/{description}")
def create_location(location_name: str, description: str, session: SessionDep):
    location = Location(name=location_name, description=description)
    session.add(location)
    session.commit()
    return location.id


@app.delete("/location/delete/{location_id}")
def delete_location(location_id: uuid.UUID, session: SessionDep):
    location = session.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    session.delete(location)
    session.commit()
    return location_id


@app.get("/location/get/{location_id}")
def get_location(location_id: uuid.UUID, session: SessionDep):
    location = session.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@app.get("/location/list")
def list_locations(session: SessionDep):
    statement = select(Location)
    locations = session.exec(statement)
    return locations.all()


# === Location Exit Routes ===


@app.post("/exit/create")
def create_exit(
    name: str,
    location_id: uuid.UUID,
    destination_id: uuid.UUID,
    description: str,
    session: SessionDep,
):
    """Create an exit from one location to another."""
    # Verify both locations exist
    location = session.get(Location, location_id)
    destination = session.get(Location, destination_id)
    if not location:
        raise HTTPException(status_code=404, detail="Source location not found")
    if not destination:
        raise HTTPException(status_code=404, detail="Destination location not found")

    exit = LocationExit(
        name=name,
        location=location_id,
        destination=destination_id,
        description=description,
    )
    session.add(exit)
    session.commit()
    return exit.id


@app.get("/exit/list/{location_id}")
def list_exits(location_id: uuid.UUID, session: SessionDep):
    """List all exits from a location."""
    exits = session.exec(
        select(LocationExit).where(LocationExit.location == location_id)
    ).all()
    return exits


@app.delete("/exit/delete/{exit_id}")
def delete_exit(exit_id: uuid.UUID, session: SessionDep):
    exit = session.get(LocationExit, exit_id)
    if not exit:
        raise HTTPException(status_code=404, detail="Exit not found")
    session.delete(exit)
    session.commit()
    return exit_id


# === PlayerLocation Routes ===


@app.post("/playerlocation/create/{player_id}/{location_id}")
def create_playerlocation(
    player_id: uuid.UUID, location_id: uuid.UUID, session: SessionDep
):
    playerlocation = PlayerLocation(player=player_id, location=location_id)
    session.add(playerlocation)
    session.commit()
    return playerlocation.id


@app.delete("/playerlocation/delete/{playerlocation_id}")
def delete_playerlocation(playerlocation_id: uuid.UUID, session: SessionDep):
    playerlocation = session.get(PlayerLocation, playerlocation_id)
    if not playerlocation:
        raise HTTPException(status_code=404, detail="PlayerLocation not found")
    session.delete(playerlocation)
    session.commit()
    return playerlocation_id


@app.get("/playerlocation/get/{playerlocation_id}")
def get_playerlocation(playerlocation_id: uuid.UUID, session: SessionDep):
    playerlocation = session.get(PlayerLocation, playerlocation_id)
    if not playerlocation:
        raise HTTPException(status_code=404, detail="PlayerLocation not found")
    return playerlocation


# === WebSocket Route ===


@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocket connection for real-time updates."""
    with Session(engine) as session:
        player_session = session.exec(
            select(PlayerSession).where(PlayerSession.token == token)
        ).first()
        if not player_session:
            await websocket.close(code=4001)
            return
        player_id = player_session.player
        player = session.get(Player, player_id)
        if not player:
            await websocket.close(code=4001)
            return

    await manager.connect(player_id, websocket)
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_json()
            # Could handle client-initiated messages here
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(player_id)


if __name__ == "__main__":
    initialize_world()
