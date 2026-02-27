import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from plurludanta import app, get_session
from sqlmodel.pool import StaticPool

@pytest.fixture(name="session")  
def session_fixture():  
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session  


@pytest.fixture(name="client")  
def client_fixture(session: Session):  
    def get_session_override():  
        return session
    app.dependency_overrides[get_session] = get_session_override  

    client = TestClient(app)  
    yield client  
    app.dependency_overrides.clear()  


def test_players(client: TestClient):
    response = client.get("/player/list")
    assert response.status_code == 200
    assert response.json() == []



