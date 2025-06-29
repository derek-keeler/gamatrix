"""
Data store helper for managing ingested game data.

This module provides functionality to:
- Store extracted game data from GOG Galaxy databases
- Manage backup rotation of data store files
- Provide structured access to game information for the UX
"""

import json
import logging
import os
import shutil
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class GameData:
    """Represents a single game with all its metadata."""

    release_key: str
    title: str
    slug: str
    platforms: List[str]
    owners: List[int]  # User IDs who own this game
    installed: List[int]  # User IDs who have this game installed
    igdb_key: str
    multiplayer: bool = False
    max_players: Optional[int] = None
    comment: Optional[str] = None
    url: Optional[str] = None


@dataclass
class UserData:
    """Represents a user and their game library metadata."""

    user_id: int
    username: str
    db_filename: str
    db_mtime: str
    total_games: int
    installed_games: int


@dataclass
class DataStore:
    """Complete data store containing all user and game information."""

    users: Dict[int, UserData]
    games: Dict[str, GameData]  # Keyed by release_key
    last_updated: str
    version: str = "1.0"


class DataStoreHelper:
    """Manages the ingested data store file with backup rotation."""

    def __init__(self, data_store_path: str, max_backups: int = 3):
        """
        Initialize the data store helper.

        Args:
            data_store_path: Path to the main data store file
            max_backups: Maximum number of backup files to keep (default: 3)
        """
        self.data_store_path = data_store_path
        self.max_backups = max_backups
        self.log = logging.getLogger(__name__)

        # Ensure the directory exists
        os.makedirs(os.path.dirname(data_store_path), exist_ok=True)

    def load_data_store(self) -> Optional[DataStore]:
        """
        Load the current data store from disk.

        Returns:
            DataStore object if file exists and is valid, None otherwise
        """
        if not os.path.exists(self.data_store_path):
            self.log.info(
                f"Data store file {self.data_store_path} does not exist"
            )  # noqa: E501
            return None

        try:
            with open(self.data_store_path, "r") as f:
                data = json.load(f)

            # Convert dictionaries back to dataclass objects
            users = {
                int(user_id): UserData(**user_data)
                for user_id, user_data in data["users"].items()
            }

            games = {
                release_key: GameData(**game_data)
                for release_key, game_data in data["games"].items()
            }

            return DataStore(
                users=users,
                games=games,
                last_updated=data["last_updated"],
                version=data.get("version", "1.0"),
            )

        except Exception as e:
            self.log.error(f"Error loading data store: {e}")
            return None

    def save_data_store(self, data_store: DataStore) -> bool:
        """
        Save the data store to disk with backup rotation.

        Args:
            data_store: DataStore object to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create backup of existing file
            if os.path.exists(self.data_store_path):
                self._rotate_backups()

            # Update timestamp
            data_store.last_updated = datetime.now().isoformat()

            # Convert to JSON-serializable format
            data_dict = {
                "users": {
                    str(k): asdict(v) for k, v in data_store.users.items()
                },  # noqa: E501
                "games": {k: asdict(v) for k, v in data_store.games.items()},
                "last_updated": data_store.last_updated,
                "version": data_store.version,
            }

            # Write to temporary file first, then move to avoid corruption
            temp_path = f"{self.data_store_path}.tmp"
            with open(temp_path, "w") as f:
                json.dump(data_dict, f, indent=2)

            # Atomic move
            shutil.move(temp_path, self.data_store_path)

            self.log.info(
                f"Data store saved successfully to {self.data_store_path}"
            )  # noqa: E501
            return True

        except Exception as e:
            self.log.error(f"Error saving data store: {e}")
            return False

    def _rotate_backups(self):
        """Rotate backup files, keeping only max_backups versions."""
        try:
            # Rotate existing backups
            for i in range(self.max_backups - 1, 0, -1):
                old_backup = f"{self.data_store_path}.backup.{i}"
                new_backup = f"{self.data_store_path}.backup.{i + 1}"

                if os.path.exists(old_backup):
                    if i == self.max_backups - 1:
                        # Remove the oldest backup
                        os.remove(old_backup)
                        self.log.debug(f"Removed old backup: {old_backup}")
                    else:
                        # Move to next backup number
                        shutil.move(old_backup, new_backup)
                        self.log.debug(
                            f"Rotated backup: {old_backup} -> {new_backup}"
                        )  # noqa: E501

            # Create new backup from current file
            if os.path.exists(self.data_store_path):
                backup_path = f"{self.data_store_path}.backup.1"
                shutil.copy2(self.data_store_path, backup_path)
                self.log.debug(f"Created backup: {backup_path}")

        except Exception as e:
            self.log.warning(f"Error during backup rotation: {e}")

    def update_user_data(
        self,
        data_store: DataStore,
        user_id: int,
        user_data: UserData,
        games: Dict[str, GameData],
    ) -> DataStore:
        """
        Update data store with new user data and their games.

        Args:
            data_store: Current data store (or new one if None)
            user_id: User ID being updated
            user_data: User metadata
            games: Dictionary of games owned by this user

        Returns:
            Updated DataStore object
        """
        if data_store is None:
            data_store = DataStore(users={}, games={}, last_updated="")

        # Update user data
        data_store.users[user_id] = user_data

        # Update games - merge with existing games or add new ones
        for release_key, game_data in games.items():
            if release_key in data_store.games:
                # Merge with existing game data
                existing_game = data_store.games[release_key]

                # Add user to owners if not already there
                if user_id not in existing_game.owners:
                    existing_game.owners.append(user_id)

                # Update installed status
                if (
                    user_id in game_data.installed
                    and user_id not in existing_game.installed
                ):
                    existing_game.installed.append(user_id)
                elif (
                    user_id not in game_data.installed
                    and user_id in existing_game.installed
                ):
                    existing_game.installed.remove(user_id)

                # Merge platforms
                for platform in game_data.platforms:
                    if platform not in existing_game.platforms:
                        existing_game.platforms.append(platform)

                # Update other metadata if not set
                if not existing_game.multiplayer and game_data.multiplayer:
                    existing_game.multiplayer = game_data.multiplayer

                if (
                    existing_game.max_players is None
                    and game_data.max_players is not None
                ):
                    existing_game.max_players = game_data.max_players
                elif (
                    game_data.max_players is not None
                    and existing_game.max_players is not None
                    and game_data.max_players > existing_game.max_players
                ):
                    existing_game.max_players = game_data.max_players

            else:
                # Add new game
                data_store.games[release_key] = game_data

        return data_store

    def remove_user_data(
        self, data_store: DataStore, user_id: int
    ) -> DataStore:  # noqa: E501
        """
        Remove a user's data from the data store.

        Args:
            data_store: Current data store
            user_id: User ID to remove

        Returns:
            Updated DataStore object
        """
        if data_store is None:
            return DataStore(users={}, games={}, last_updated="")

        # Remove user
        if user_id in data_store.users:
            del data_store.users[user_id]

        # Remove user from all games
        games_to_remove = []
        for release_key, game_data in data_store.games.items():
            if user_id in game_data.owners:
                game_data.owners.remove(user_id)
            if user_id in game_data.installed:
                game_data.installed.remove(user_id)

            # If no users own this game anymore, remove it
            if not game_data.owners:
                games_to_remove.append(release_key)

        for release_key in games_to_remove:
            del data_store.games[release_key]

        return data_store
