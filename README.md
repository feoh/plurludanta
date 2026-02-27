# Plurludanta

## Overview

Plurludanta - "multiplayer game" in Esperanto, is a Python library that makes it easy to create simple multiplayer games
using [FastAPI](https://fastapi.tiangolo.com) - the brilliant REST API library,
and [SQLModel](https://sqlmodel.tiangolo.com) from the same author to model
game objects.

## Implementation

### Server
All communication between clients and server happens using a REST API over
HTTP or HTTPS.

Game objects are modeled using SQLMOdel as are their dependencies.

The server will be able to maintain and update state for all connected players as near to real time as is possible.


### Clients
The REST based architecture of the server means that we can support many different kinds of clients.

An initial client implementation that would be very straight forward would be a simple text input based command parser
that would allow the player to move around and interact with the defined game objects.

## Tests

There should be unit and integration tests for everything.

## Usage

### Running the Server

```bash
# Install dependencies
uv sync

# Start the server
uv run fastapi dev plurludanta.py

# Initialize the world (creates Limbo, Garden, and sample objects)
uv run python plurludanta.py
```

### Running the Client

```bash
# Register a new player and connect
uv run python client.py --register

# Connect with existing player
uv run python client.py
```

### Client Commands

- `look` (or `l`) - Look around the current location
- `go <exit>` - Move through an exit (e.g., `go garden`)
- `take <item>` - Pick up an item
- `drop <item>` - Drop an item from inventory
- `inventory` (or `i`) - List items you're carrying
- `say <message>` - Say something to others in the room
- `who` - List all players
- `quit` - Exit the game

### API Endpoints

#### Authentication
- `POST /auth/register` - Register a new player
- `POST /auth/login` - Login and receive a session token
- `POST /auth/logout` - Logout and invalidate session

#### Game Actions (require authentication)
- `GET /player/look` - Look around current location
- `POST /player/move/{exit_name}` - Move through an exit
- `GET /player/inventory` - List items in inventory
- `POST /player/pickup/{thing_name}` - Pick up an item
- `POST /player/drop/{thing_name}` - Drop an item
- `POST /player/say?message=...` - Say something

#### CRUD Operations
- Players: `/player/create`, `/player/list`, `/player/get/{id}`, `/player/delete/{id}`
- Things: `/thing/create`, `/thing/list`, `/thing/get/{id}`, `/thing/delete/{id}`
- Locations: `/location/create`, `/location/list`, `/location/get/{id}`, `/location/delete/{id}`
- Exits: `/exit/create`, `/exit/list/{location_id}`, `/exit/delete/{id}`

#### Real-time Updates
- `WebSocket /ws/{token}` - Connect for real-time notifications (player arrivals, departures, chat)

## Running Tests

```bash
uv run pytest -v
```

## Architecture

### Models

- **Player** - Game players with optional authentication
- **Location** - Places in the game world
- **LocationExit** - Connections between locations
- **Thing** - Objects that can be picked up and dropped
- **PlayerLocation** - Tracks where each player is
- **PlayerSession** - Authentication sessions with tokens

### Features

- REST API server using FastAPI
- SQLite database with SQLModel ORM
- Bearer token authentication
- WebSocket support for real-time events
- Text-based command-line client
- 35 comprehensive tests

