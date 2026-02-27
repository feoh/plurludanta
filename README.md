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

