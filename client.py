#!/usr/bin/env python3
"""
Plurludanta Text Client

A command-line client for the Plurludanta multiplayer game server.

Commands:
  look          - Look around the current location
  go <exit>     - Move through an exit (e.g., "go north")
  take <item>   - Pick up an item
  drop <item>   - Drop an item from inventory
  inventory     - List items you're carrying
  say <message> - Say something to others in the room
  who           - List all players online
  quit          - Exit the game
"""

import argparse
import asyncio
import sys
import httpx
import websockets
import json
from typing import Any


class GameClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self.token: str | None = None
        self.player_name: str | None = None
        self.ws_task: asyncio.Task | None = None

    async def register(self, name: str, password: str) -> bool:
        """Register a new player."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.server_url}/auth/register",
                    params={"player_name": name, "password": password},
                )
                if response.status_code == 200:
                    print(f"Registered as {name}!")
                    return True
                else:
                    print(f"Registration failed: {response.json().get('detail', 'Unknown error')}")
                    return False
            except httpx.RequestError as e:
                print(f"Connection error: {e}")
                return False

    async def login(self, name: str, password: str) -> bool:
        """Login to the server."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.server_url}/auth/login",
                    params={"player_name": name, "password": password},
                )
                if response.status_code == 200:
                    data = response.json()
                    self.token = data["token"]
                    self.player_name = name
                    print(f"Logged in as {name}!")
                    return True
                else:
                    print(f"Login failed: {response.json().get('detail', 'Unknown error')}")
                    return False
            except httpx.RequestError as e:
                print(f"Connection error: {e}")
                return False

    async def logout(self) -> None:
        """Logout from the server."""
        if not self.token:
            return
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{self.server_url}/auth/logout",
                    headers={"Authorization": f"Bearer {self.token}"},
                )
            except httpx.RequestError:
                pass
        self.token = None
        self.player_name = None

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any] | None:
        """Make an authenticated request to the server."""
        if not self.token:
            print("Not logged in!")
            return None

        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {self.token}"}
                if method == "GET":
                    response = await client.get(
                        f"{self.server_url}{endpoint}",
                        headers=headers,
                        params=kwargs.get("params"),
                    )
                else:
                    response = await client.post(
                        f"{self.server_url}{endpoint}",
                        headers=headers,
                        params=kwargs.get("params"),
                    )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    print("Session expired. Please login again.")
                    self.token = None
                    return None
                else:
                    detail = response.json().get("detail", "Unknown error")
                    print(f"Error: {detail}")
                    return None
            except httpx.RequestError as e:
                print(f"Connection error: {e}")
                return None

    async def look(self) -> None:
        """Look around the current location."""
        data = await self._request("GET", "/player/look")
        if not data:
            return

        location = data["location"]
        print(f"\n=== {location['name']} ===")
        print(location["description"])

        if data["players"]:
            print("\nPlayers here:")
            for p in data["players"]:
                print(f"  - {p['name']}")

        if data["things"]:
            print("\nYou see:")
            for t in data["things"]:
                print(f"  - {t['name']}: {t['description']}")

        if data["exits"]:
            print("\nExits:")
            for e in data["exits"]:
                print(f"  - {e['name']}: {e['description']}")
        print()

    async def move(self, exit_name: str) -> None:
        """Move through an exit."""
        data = await self._request("POST", f"/player/move/{exit_name}")
        if data:
            print(data["message"])
            await self.look()

    async def inventory(self) -> None:
        """List inventory."""
        data = await self._request("GET", "/player/inventory")
        if data is None:
            return

        if not data:
            print("You aren't carrying anything.")
        else:
            print("You are carrying:")
            for item in data:
                print(f"  - {item['name']}: {item['description']}")

    async def pickup(self, thing_name: str) -> None:
        """Pick up an item."""
        data = await self._request("POST", f"/player/pickup/{thing_name}")
        if data:
            print(data["message"])

    async def drop(self, thing_name: str) -> None:
        """Drop an item."""
        data = await self._request("POST", f"/player/drop/{thing_name}")
        if data:
            print(data["message"])

    async def say(self, message: str) -> None:
        """Say something."""
        data = await self._request("POST", "/player/say", params={"message": message})
        if data:
            print(data["message"])

    async def who(self) -> None:
        """List all players."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.server_url}/player/list")
                if response.status_code == 200:
                    players = response.json()
                    print("Players:")
                    for p in players:
                        print(f"  - {p['name']}")
                else:
                    print("Could not get player list")
            except httpx.RequestError as e:
                print(f"Connection error: {e}")

    async def handle_websocket(self) -> None:
        """Handle WebSocket connection for real-time updates."""
        if not self.token:
            return

        ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://")
        try:
            async with websockets.connect(f"{ws_url}/ws/{self.token}") as ws:
                while True:
                    try:
                        message = await ws.recv()
                        data = json.loads(message)
                        event = data.get("event")

                        if event == "player_arrived":
                            print(f"\n{data['player']} has arrived.")
                        elif event == "player_left":
                            print(f"\n{data['player']} left via {data['exit']}.")
                        elif event == "say":
                            print(f"\n{data['player']} says: \"{data['message']}\"")
                        elif event == "thing_taken":
                            print(f"\n{data['player']} picks up the {data['thing']}.")
                        elif event == "thing_dropped":
                            print(f"\n{data['player']} drops the {data['thing']}.")

                        print("> ", end="", flush=True)
                    except websockets.ConnectionClosed:
                        break
        except Exception:
            pass  # WebSocket connection failed, continue without real-time updates

    async def run(self) -> None:
        """Main game loop."""
        print("Welcome to Plurludanta!")
        print("Type 'help' for a list of commands.\n")

        # Start WebSocket listener
        self.ws_task = asyncio.create_task(self.handle_websocket())

        # Initial look
        await self.look()

        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("> ")
                )
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            line = line.strip()
            if not line:
                continue

            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "quit" or cmd == "exit":
                print("Goodbye!")
                break
            elif cmd == "help":
                print(__doc__)
            elif cmd == "look" or cmd == "l":
                await self.look()
            elif cmd == "go" or cmd == "move":
                if arg:
                    await self.move(arg)
                else:
                    print("Go where? Usage: go <exit>")
            elif cmd in ["n", "north", "s", "south", "e", "east", "w", "west", "up", "down"]:
                # Direction shortcuts
                await self.move(cmd)
            elif cmd == "take" or cmd == "get" or cmd == "pickup":
                if arg:
                    await self.pickup(arg)
                else:
                    print("Take what? Usage: take <item>")
            elif cmd == "drop":
                if arg:
                    await self.drop(arg)
                else:
                    print("Drop what? Usage: drop <item>")
            elif cmd == "inventory" or cmd == "inv" or cmd == "i":
                await self.inventory()
            elif cmd == "say":
                if arg:
                    await self.say(arg)
                else:
                    print("Say what? Usage: say <message>")
            elif cmd == "who":
                await self.who()
            else:
                print(f"Unknown command: {cmd}. Type 'help' for a list of commands.")

        # Cleanup
        if self.ws_task:
            self.ws_task.cancel()
        await self.logout()


async def main():
    parser = argparse.ArgumentParser(description="Plurludanta game client")
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="Server URL (default: http://localhost:8000)",
    )
    parser.add_argument("--register", action="store_true", help="Register a new account")
    args = parser.parse_args()

    client = GameClient(args.server)

    # Get credentials
    print("=" * 40)
    print("  PLURLUDANTA - Multiplayer Game")
    print("=" * 40)

    name = input("Player name: ").strip()
    if not name:
        print("Name cannot be empty!")
        sys.exit(1)

    password = input("Password: ").strip()
    if not password:
        print("Password cannot be empty!")
        sys.exit(1)

    if args.register:
        if not await client.register(name, password):
            sys.exit(1)

    if not await client.login(name, password):
        sys.exit(1)

    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
