"""
Ingestion helper for extracting data from GOG Galaxy databases.

This module handles the extraction of game data from uploaded GOG Galaxy
database files and converts it into structured data for the data store.
"""

import logging
import os
import time
from typing import Dict, List, Optional, Tuple

from gamatrix.helpers.gogdb_helper import gogDB
from gamatrix.helpers.data_store_helper import GameData, UserData
from gamatrix.helpers.misc_helper import get_slug_from_title
import gamatrix.helpers.constants as constants


class IngestionHelper:
    """Handles extraction of game data from GOG Galaxy databases."""
    
    def __init__(self, config):
        """
        Initialize the ingestion helper.
        
        Args:
            config: Application configuration dictionary
        """
        self.config = config
        self.log = logging.getLogger(__name__)
    
    def extract_user_data(self, user_id: int, db_path: str) -> Tuple[UserData, Dict[str, GameData]]:
        """
        Extract all relevant data for a user from their GOG database.
        
        Args:
            user_id: User ID
            db_path: Path to the user's GOG Galaxy database file
            
        Returns:
            Tuple of (UserData, dict of GameData keyed by release_key)
        """
        self.log.info(f"Extracting data for user {user_id} from {db_path}")
        
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
        
        # Create a minimal config for this user only
        user_config = {
            'users': {user_id: self.config['users'][user_id]},
            'db_path': self.config['db_path'],
            'db_list': [db_path],
            'metadata': self.config.get('metadata', {}),
            'user_ids_to_compare': {user_id: self.config['users'][user_id]},
            'exclusive': False,
            'all_games': True,  # We want all games for data extraction
        }
        
        # Create gogDB instance for this user
        opts = {
            'include_single_player': True,
            'exclusive': False,
            'show_keys': False,
            'randomize': False,
            'user_ids_to_compare': {user_id: self.config['users'][user_id]},
            'exclude_platforms': [],
        }
        
        gog = gogDB(user_config, opts)
        
        # Get all games for this user
        all_games = gog.get_common_games()
        
        # Get installed games
        gog.use_db(db_path)
        installed_games = set(gog.get_installed_games())
        gog.close_connection()
        
        # Convert to our data structure
        games_data = {}
        total_games = len(all_games)
        installed_count = 0
        
        for release_key, game_info in all_games.items():
            # Determine if game is installed
            is_installed = release_key in installed_games
            if is_installed:
                installed_count += 1
            
            # Create GameData object
            game_data = GameData(
                release_key=release_key,
                title=game_info['title'],
                slug=game_info['slug'],
                platforms=game_info['platforms'],
                owners=[user_id],
                installed=[user_id] if is_installed else [],
                igdb_key=game_info.get('igdb_key', release_key),
                multiplayer=game_info.get('multiplayer', False),
                max_players=game_info.get('max_players'),
                comment=game_info.get('comment'),
                url=game_info.get('url')
            )
            
            games_data[release_key] = game_data
        
        # Create UserData object
        user_data = UserData(
            user_id=user_id,
            username=self.config['users'][user_id]['username'],
            db_filename=self.config['users'][user_id]['db'],
            db_mtime=time.strftime(
                constants.TIME_FORMAT, 
                time.localtime(os.path.getmtime(db_path))
            ),
            total_games=total_games,
            installed_games=installed_count
        )
        
        self.log.info(
            f"Extracted {total_games} games for user {user_id} "
            f"({installed_count} installed)"
        )
        
        return user_data, games_data
    
    def process_all_users(self) -> Dict[str, GameData]:
        """
        Process all users' databases and extract game data.
        This is used for initial data store creation or full rebuild.
        
        Returns:
            Dictionary of all games keyed by release_key
        """
        self.log.info("Processing all users for data extraction")
        
        all_games = {}
        
        for user_id in self.config['users']:
            if 'db' not in self.config['users'][user_id]:
                self.log.warning(f"User {user_id} has no database file configured")
                continue
            
            db_path = f"{self.config['db_path']}/{self.config['users'][user_id]['db']}"
            
            if not os.path.exists(db_path):
                self.log.warning(f"Database file not found for user {user_id}: {db_path}")
                continue
            
            try:
                user_data, user_games = self.extract_user_data(user_id, db_path)
                
                # Merge games into the main collection
                for release_key, game_data in user_games.items():
                    if release_key in all_games:
                        # Merge with existing game
                        existing_game = all_games[release_key]
                        
                        # Add user to owners
                        if user_id not in existing_game.owners:
                            existing_game.owners.append(user_id)
                        
                        # Update installed status
                        if user_id in game_data.installed:
                            if user_id not in existing_game.installed:
                                existing_game.installed.append(user_id)
                        
                        # Merge platforms
                        for platform in game_data.platforms:
                            if platform not in existing_game.platforms:
                                existing_game.platforms.append(platform)
                        
                        # Update multiplayer info if better data available
                        if not existing_game.multiplayer and game_data.multiplayer:
                            existing_game.multiplayer = game_data.multiplayer
                        
                        if (existing_game.max_players is None and 
                            game_data.max_players is not None):
                            existing_game.max_players = game_data.max_players
                        elif (game_data.max_players is not None and 
                              existing_game.max_players is not None and 
                              game_data.max_players > existing_game.max_players):
                            existing_game.max_players = game_data.max_players
                    else:
                        # Add new game
                        all_games[release_key] = game_data
                        
            except Exception as e:
                self.log.error(f"Error processing user {user_id}: {e}")
                continue
        
        self.log.info(f"Processed all users, found {len(all_games)} unique games")
        return all_games