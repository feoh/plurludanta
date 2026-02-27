import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from plurludanta import app, get_session, initialize_world


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(engine):
    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="seeded_client")
def seeded_client_fixture(engine):
    """Client with initialized world (Limbo, Garden, exits, flower)."""
    # Manually seed the database
    from models import Location, LocationExit, Thing

    with Session(engine) as session:
        limbo = Location(
            name="Limbo",
            description="A formless void.",
        )
        session.add(limbo)
        session.commit()
        session.refresh(limbo)

        garden = Location(
            name="Garden",
            description="A peaceful garden.",
        )
        session.add(garden)
        session.commit()
        session.refresh(garden)

        exit_to_garden = LocationExit(
            name="garden",
            location=limbo.id,
            destination=garden.id,
            description="A portal to the garden.",
        )
        exit_to_limbo = LocationExit(
            name="void",
            location=garden.id,
            destination=limbo.id,
            description="A portal to the void.",
        )
        session.add(exit_to_garden)
        session.add(exit_to_limbo)
        session.commit()

        flower = Thing(
            name="flower",
            description="A red flower.",
            location=garden.id,
        )
        session.add(flower)
        session.commit()

    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# === Player CRUD Tests ===


class TestPlayerCRUD:
    def test_list_players_empty(self, client: TestClient):
        response = client.get("/player/list")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_player(self, client: TestClient):
        response = client.post("/player/create/TestPlayer")
        assert response.status_code == 200
        player_id = response.json()
        assert player_id is not None

    def test_create_duplicate_player(self, client: TestClient):
        client.post("/player/create/TestPlayer")
        response = client.post("/player/create/TestPlayer")
        assert response.status_code == 400
        assert "already taken" in response.json()["detail"]

    def test_get_player(self, client: TestClient):
        response = client.post("/player/create/TestPlayer")
        player_id = response.json()

        response = client.get(f"/player/get/{player_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "TestPlayer"

    def test_get_nonexistent_player(self, client: TestClient):
        response = client.get("/player/get/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_delete_player(self, client: TestClient):
        response = client.post("/player/create/TestPlayer")
        player_id = response.json()

        response = client.delete(f"/player/delete/{player_id}")
        assert response.status_code == 200

        response = client.get(f"/player/get/{player_id}")
        assert response.status_code == 404

    def test_list_players(self, client: TestClient):
        client.post("/player/create/Player1")
        client.post("/player/create/Player2")

        response = client.get("/player/list")
        assert response.status_code == 200
        players = response.json()
        assert len(players) == 2
        names = [p["name"] for p in players]
        assert "Player1" in names
        assert "Player2" in names


# === Authentication Tests ===


class TestAuthentication:
    def test_register(self, seeded_client: TestClient):
        response = seeded_client.post(
            "/auth/register",
            params={"player_name": "NewPlayer", "password": "secret123"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "NewPlayer"

    def test_register_duplicate(self, seeded_client: TestClient):
        seeded_client.post(
            "/auth/register",
            params={"player_name": "NewPlayer", "password": "secret123"},
        )
        response = seeded_client.post(
            "/auth/register",
            params={"player_name": "NewPlayer", "password": "other"},
        )
        assert response.status_code == 400

    def test_login(self, seeded_client: TestClient):
        seeded_client.post(
            "/auth/register",
            params={"player_name": "TestUser", "password": "mypassword"},
        )
        response = seeded_client.post(
            "/auth/login",
            params={"player_name": "TestUser", "password": "mypassword"},
        )
        assert response.status_code == 200
        assert "token" in response.json()

    def test_login_wrong_password(self, seeded_client: TestClient):
        seeded_client.post(
            "/auth/register",
            params={"player_name": "TestUser", "password": "mypassword"},
        )
        response = seeded_client.post(
            "/auth/login",
            params={"player_name": "TestUser", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, seeded_client: TestClient):
        response = seeded_client.post(
            "/auth/login",
            params={"player_name": "NoSuchUser", "password": "password"},
        )
        assert response.status_code == 401

    def test_logout(self, seeded_client: TestClient):
        seeded_client.post(
            "/auth/register",
            params={"player_name": "TestUser", "password": "password"},
        )
        login_response = seeded_client.post(
            "/auth/login",
            params={"player_name": "TestUser", "password": "password"},
        )
        token = login_response.json()["token"]

        response = seeded_client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


# === Thing CRUD Tests ===


class TestThingCRUD:
    def test_create_thing(self, client: TestClient):
        response = client.post("/thing/create/Sword")
        assert response.status_code == 200

    def test_list_things(self, client: TestClient):
        client.post("/thing/create/Sword")
        client.post("/thing/create/Shield")

        response = client.get("/thing/list")
        assert response.status_code == 200
        things = response.json()
        assert len(things) == 2

    def test_get_thing(self, client: TestClient):
        response = client.post("/thing/create/Sword")
        thing_id = response.json()

        response = client.get(f"/thing/get/{thing_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Sword"

    def test_delete_thing(self, client: TestClient):
        response = client.post("/thing/create/Sword")
        thing_id = response.json()

        response = client.delete(f"/thing/delete/{thing_id}")
        assert response.status_code == 200

        response = client.get(f"/thing/get/{thing_id}")
        assert response.status_code == 404


# === Location CRUD Tests ===


class TestLocationCRUD:
    def test_create_location(self, client: TestClient):
        response = client.post("/location/create/Forest/A dark forest")
        assert response.status_code == 200

    def test_list_locations(self, client: TestClient):
        client.post("/location/create/Forest/A dark forest")
        client.post("/location/create/Cave/A damp cave")

        response = client.get("/location/list")
        assert response.status_code == 200
        locations = response.json()
        assert len(locations) == 2

    def test_get_location(self, client: TestClient):
        response = client.post("/location/create/Forest/A dark forest")
        location_id = response.json()

        response = client.get(f"/location/get/{location_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Forest"
        assert response.json()["description"] == "A dark forest"

    def test_delete_location(self, client: TestClient):
        response = client.post("/location/create/Forest/A dark forest")
        location_id = response.json()

        response = client.delete(f"/location/delete/{location_id}")
        assert response.status_code == 200

        response = client.get(f"/location/get/{location_id}")
        assert response.status_code == 404


# === Exit CRUD Tests ===


class TestExitCRUD:
    def test_create_exit(self, client: TestClient):
        loc1 = client.post("/location/create/Room1/First room").json()
        loc2 = client.post("/location/create/Room2/Second room").json()

        response = client.post(
            "/exit/create",
            params={
                "name": "north",
                "location_id": loc1,
                "destination_id": loc2,
                "description": "A door to the north",
            },
        )
        assert response.status_code == 200

    def test_list_exits(self, client: TestClient):
        loc1 = client.post("/location/create/Room1/First room").json()
        loc2 = client.post("/location/create/Room2/Second room").json()

        client.post(
            "/exit/create",
            params={
                "name": "north",
                "location_id": loc1,
                "destination_id": loc2,
                "description": "North door",
            },
        )
        client.post(
            "/exit/create",
            params={
                "name": "east",
                "location_id": loc1,
                "destination_id": loc2,
                "description": "East door",
            },
        )

        response = client.get(f"/exit/list/{loc1}")
        assert response.status_code == 200
        exits = response.json()
        assert len(exits) == 2

    def test_delete_exit(self, client: TestClient):
        loc1 = client.post("/location/create/Room1/First room").json()
        loc2 = client.post("/location/create/Room2/Second room").json()

        exit_id = client.post(
            "/exit/create",
            params={
                "name": "north",
                "location_id": loc1,
                "destination_id": loc2,
                "description": "North door",
            },
        ).json()

        response = client.delete(f"/exit/delete/{exit_id}")
        assert response.status_code == 200


# === Game Action Tests ===


class TestGameActions:
    def _get_auth_token(self, client: TestClient, name: str = "TestPlayer") -> str:
        """Helper to register, login, and return token."""
        client.post(
            "/auth/register",
            params={"player_name": name, "password": "password"},
        )
        response = client.post(
            "/auth/login",
            params={"player_name": name, "password": "password"},
        )
        return response.json()["token"]

    def test_look(self, seeded_client: TestClient):
        token = self._get_auth_token(seeded_client)

        response = seeded_client.get(
            "/player/look",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "location" in data
        assert data["location"]["name"] == "Limbo"
        assert "exits" in data
        assert "things" in data
        assert "players" in data

    def test_look_unauthorized(self, seeded_client: TestClient):
        response = seeded_client.get("/player/look")
        assert response.status_code == 401

    def test_move(self, seeded_client: TestClient):
        token = self._get_auth_token(seeded_client)

        # Start in Limbo, move to Garden
        response = seeded_client.post(
            "/player/move/garden",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["location"] == "Garden"

        # Verify we're now in Garden
        response = seeded_client.get(
            "/player/look",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.json()["location"]["name"] == "Garden"

    def test_move_invalid_exit(self, seeded_client: TestClient):
        token = self._get_auth_token(seeded_client)

        response = seeded_client.post(
            "/player/move/nonexistent",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_inventory_empty(self, seeded_client: TestClient):
        token = self._get_auth_token(seeded_client)

        response = seeded_client.get(
            "/player/inventory",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_pickup_and_drop(self, seeded_client: TestClient):
        token = self._get_auth_token(seeded_client)

        # Move to Garden where the flower is
        seeded_client.post(
            "/player/move/garden",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Pick up the flower
        response = seeded_client.post(
            "/player/pickup/flower",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        # Check inventory
        response = seeded_client.get(
            "/player/inventory",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = response.json()
        assert len(items) == 1
        assert items[0]["name"] == "flower"

        # Flower should not be in the room anymore
        response = seeded_client.get(
            "/player/look",
            headers={"Authorization": f"Bearer {token}"},
        )
        things = response.json()["things"]
        assert len(things) == 0

        # Drop the flower
        response = seeded_client.post(
            "/player/drop/flower",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        # Check inventory is empty
        response = seeded_client.get(
            "/player/inventory",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.json() == []

        # Flower should be back in the room
        response = seeded_client.get(
            "/player/look",
            headers={"Authorization": f"Bearer {token}"},
        )
        things = response.json()["things"]
        assert len(things) == 1

    def test_pickup_nonexistent(self, seeded_client: TestClient):
        token = self._get_auth_token(seeded_client)

        response = seeded_client.post(
            "/player/pickup/nosuchitem",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_drop_not_owned(self, seeded_client: TestClient):
        token = self._get_auth_token(seeded_client)

        response = seeded_client.post(
            "/player/drop/flower",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_say(self, seeded_client: TestClient):
        token = self._get_auth_token(seeded_client)

        response = seeded_client.post(
            "/player/say",
            params={"message": "Hello, world!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "Hello, world!" in response.json()["message"]

    def test_see_other_players(self, seeded_client: TestClient):
        token1 = self._get_auth_token(seeded_client, "Player1")
        token2 = self._get_auth_token(seeded_client, "Player2")

        # Both players should see each other in Limbo
        response = seeded_client.get(
            "/player/look",
            headers={"Authorization": f"Bearer {token1}"},
        )
        players = response.json()["players"]
        assert len(players) == 1
        assert players[0]["name"] == "Player2"

        response = seeded_client.get(
            "/player/look",
            headers={"Authorization": f"Bearer {token2}"},
        )
        players = response.json()["players"]
        assert len(players) == 1
        assert players[0]["name"] == "Player1"


# === Utility Route Tests ===


class TestUtilityRoutes:
    def test_list_routes(self, client: TestClient):
        response = client.get("/listroutes")
        assert response.status_code == 200
        routes = response.json()
        assert len(routes) > 0
        paths = [r["path"] for r in routes]
        assert "/player/list" in paths
        assert "/player/look" in paths
