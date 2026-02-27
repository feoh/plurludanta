from sqlmodel import SQLModel, create_engine, select, Session
from fastapi import FastAPI, Request, Depends
from models.player import Player
from models.thing import Thing
from models.location import Location
from models.playerlocation import PlayerLocation
import uuid


def initialize_database():
    sqlite_file_name='plurludanta.db'
    sqlite_url='sqlite:///' + sqlite_file_name

    engine = create_engine(sqlite_url, echo=True)

    SQLModel.metadata.create_all(engine)
    return engine

def get_session():
    with Session(engine) as session:
        yield session

def initialize_world():
    with Session(engine) as session:
        # Create the Limbo location
        wizard = Player(name="Wizard")
        session.add(wizard)
        session.commit()

        # Create a thing
        thing = Thing(name="Veeblefetzer")
        session.add(thing)
        session.commit()

        # Create Limbo, the first location!
        limbo = Location(name="Limbo", description="""
                         In the beginning, there was Limbo. It is a dark,
                         """)
        session.add(limbo)
        session.commit()

        wizardlocation = PlayerLocation(
                player = wizard.id,
                location = limbo.id,
        )
        session.add(wizardlocation)
        session.commit()



engine = initialize_database()
app = FastAPI()

@app.get("/listroutes")
def get_all_urls_from_request(request: Request):
    url_list = [
        {"path": route.path, "name": route.name} for route in request.app.routes
    ]
    return url_list

@app.post("/player/create/{player_name}")
def create_player(player_name: str, session: Session = Depends(get_session)):
    player = Player(name=player_name)
    session.add(player)
    session.commit()
    return player.id

@app.get("/player/list")
def list_players(session: Session = Depends(get_session)):
    statement = select(Player)
    players = session.exec(statement)
    return players.all()


@app.delete("/player/delete/{player_id}")
def delete_player(player_id: uuid.UUID, session: Session = Depends(get_session)):
    player = session.get(Player, player_id)
    session.delete(player)
    session.commit()
    return(player_id)


@app.get("/player/get/{player_id}")
def get_player(player_id: uuid.UUID, session: Session = Depends(get_session)):
    player = session.get(Player, player_id)
    return player

@app.post("/thing/create/{thing_name}")
def create_thing(thing_name: str, session: Session = Depends(get_session)):
    thing = Thing(name=thing_name)
    session.add(thing)
    session.commit()
    return thing.id

@app.delete("/thing/delete/{thing_id}")
def delete_thing(thing_id: uuid.UUID, session: Session = Depends(get_session)):
    thing = session.get(Thing, thing_id)
    session.delete(thing)
    session.commit()
    return(thing_id)

@app.get("/thing/get/{thing_id}")
def get_thing(thing_id: uuid.UUID, session: Session = Depends(get_session)):
    thing = session.get(Thing, thing_id)
    return thing

@app.get("/thing/list")
def list_things(session: Session = Depends(get_session)):
    statement = select(Thing)
    things = session.exec(statement)
    return things.all()

@app.post("/location/create/{location_name}/{description}")
def create_location(location_name: str, description: str, session: Session = Depends(get_session)):
    location = Location(name=location_name, description=description)
    session.add(location)
    session.commit()
    return location.id

@app.delete("/location/delete/{location_id}")
def delete_location(location_id: uuid.UUID, session: Session = Depends(get_session)):
    location = session.get(Location, location_id)
    session.delete(location)
    session.commit()
    return(location_id)

@app.get("/location/get/{location_id}")
def get_location(location_id: uuid.UUID, session: Session = Depends(get_session)):
    location = session.get(Location, location_id)
    return location

@app.get("/location/list")
def list_locations(session: Session = Depends(get_session)):
    statement = select(Location)
    locations = session.exec(statement)
    return locations.all()

@app.post("/playerlocation/create/{player_id}/{location_id}")
def create_playerlocation(player_id: uuid.UUID, location_id: uuid.UUID, session: Session = Depends(get_session)):
    playerlocation = PlayerLocation(player=player_id, location=location_id)
    session.add(playerlocation)
    session.commit()
    return playerlocation.id

@app.delete("/playerlocation/delete/{playerlocation_id}")
def delete_playerlocation(playerlocation_id: uuid.UUID, session: Session = Depends(get_session)):
    playerlocation = session.get(PlayerLocation, playerlocation_id)
    session.delete(playerlocation)
    session.commit()
    return(playerlocation_id)

@app.get("/playerlocation/get/{playerlocation_id}")
def get_playerlocation(playerlocation_id: uuid.UUID, session: Session = Depends(get_session)):
    playerlocation = session.get(PlayerLocation, playerlocation_id)
    return playerlocation

if __name__ == "__main__":
    initialize_world()


