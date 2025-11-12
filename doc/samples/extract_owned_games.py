#!/usr/bin/env python3
"""
Extract Owned Games from GOG Galaxy Database

This script extracts and displays the list of games owned by a user,
following the same approach used by Gamatrix. It demonstrates how to
query the database using temporary views for efficient data extraction.

Usage:
    python extract_owned_games.py /path/to/galaxy-2.0.db

Output:
    - User identification
    - List of owned games with titles and platform information
    - Release keys for each game
"""

import sqlite3
import sys
import os
import json


def connect_to_database(db_path):
    """Connect to the GOG Galaxy database."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    return sqlite3.connect(db_path)


def get_user_info(conn):
    """
    Get user information from the database.

    Returns:
        Tuple of (user_id, username) or None if no user found
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users")
    users = cursor.fetchall()

    if not users:
        return None

    if len(users) > 1:
        print("[INFO] Multiple users found, using first one")

    # Typically: (userId, username, ...)
    return users[0]


def get_gamepiecetype_id(conn, type_name):
    """
    Get the numeric ID for a GamePieceType.

    Args:
        conn: Database connection
        type_name: Type name (e.g., 'originalTitle', 'title', 'allGameReleases')

    Returns:
        Integer type ID
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM GamePieceTypes WHERE type=?", (type_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    raise ValueError(f"GamePieceType '{type_name}' not found")


def get_owned_games(conn):
    """
    Extract owned games using Gamatrix's view-based approach.

    This replicates the query logic from gogdb_helper.py:
    1. Create a MasterList view joining purchases with game pieces
    2. Create a MasterDB view with titles and platform lists
    3. Query and group games by platform

    Returns:
        List of tuples: (comma_separated_release_keys, title_json)
    """
    cursor = conn.cursor()

    # Get type IDs
    original_title_id = get_gamepiecetype_id(conn, "originalTitle")
    title_id = get_gamepiecetype_id(conn, "title")
    all_releases_id = get_gamepiecetype_id(conn, "allGameReleases")

    # Step 1: Create MasterList view
    # This joins purchased games with their metadata
    master_list_query = """
        CREATE TEMP VIEW MasterList AS
        SELECT GamePieces.releaseKey, 
               GamePieces.gamePieceTypeId, 
               GamePieces.value 
        FROM ProductPurchaseDates
        JOIN GamePieces ON ProductPurchaseDates.gameReleaseKey = GamePieces.releaseKey
    """
    cursor.execute(master_list_query)

    # Step 2: Create MasterDB view
    # This filters to just titles and platform information
    master_db_query = f"""
        CREATE TEMP VIEW MasterDB AS 
        SELECT DISTINCT(MasterList.releaseKey) AS releaseKey, 
               MasterList.value AS title, 
               PLATFORMS.value AS platformList
        FROM MasterList, MasterList AS PLATFORMS
        WHERE ((MasterList.gamePieceTypeId={original_title_id}) OR 
               (MasterList.gamePieceTypeId={title_id})) 
          AND ((PLATFORMS.releaseKey=MasterList.releaseKey) AND 
               (PLATFORMS.gamePieceTypeId={all_releases_id}))
        ORDER BY title
    """
    cursor.execute(master_db_query)

    # Step 3: Query unique games grouped by platform list
    final_query = """
        SELECT GROUP_CONCAT(DISTINCT MasterDB.releaseKey), 
               MasterDB.title
        FROM MasterDB 
        GROUP BY MasterDB.platformList 
        ORDER BY MasterDB.title
    """
    cursor.execute(final_query)

    return cursor.fetchall()


def parse_game_data(owned_games):
    """
    Parse the raw query results into a more readable format.

    Args:
        owned_games: List of tuples from get_owned_games()

    Returns:
        List of dicts with game information
    """
    parsed_games = []

    for release_keys_str, title_json in owned_games:
        # Parse the title JSON
        try:
            title_data = json.loads(title_json)
            title = title_data.get("title", "Unknown Title")
        except (json.JSONDecodeError, TypeError):
            title = "Unknown Title"

        # Split release keys (comma-separated if owned on multiple platforms)
        release_keys = release_keys_str.split(",") if release_keys_str else []

        # Extract platforms from release keys
        platforms = []
        for key in release_keys:
            platform = key.split("_")[0] if "_" in key else "unknown"
            if platform not in platforms:
                platforms.append(platform)

        parsed_games.append(
            {
                "title": title,
                "release_keys": release_keys,
                "platforms": platforms,
                "num_platforms": len(release_keys),
            }
        )

    return parsed_games


def display_owned_games(games):
    """Display owned games in a human-readable format."""
    print(f"\n{'='*70}")
    print(f"OWNED GAMES ({len(games)} found)")
    print(f"{'='*70}\n")

    for i, game in enumerate(games, 1):
        print(f"{i}. {game['title']}")
        print(f"   Release Keys: {', '.join(game['release_keys'])}")
        print(f"   Platforms: {', '.join(game['platforms'])}")

        if game["num_platforms"] > 1:
            print(f"   [Multi-platform: owned on {game['num_platforms']} platforms]")

        print()


def main():
    """Main function to extract and display owned games."""
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    db_path = sys.argv[1]

    print("=" * 70)
    print("GOG Galaxy Owned Games Extractor")
    print("=" * 70)
    print(f"Database: {db_path}\n")

    try:
        # Connect to database
        conn = connect_to_database(db_path)

        # Get user info
        user_info = get_user_info(conn)
        if not user_info:
            print("ERROR: No users found in database", file=sys.stderr)
            sys.exit(1)

        user_id = user_info[0]
        print(f"User ID: {user_id}")

        # Extract owned games
        print("\nExtracting owned games...")
        owned_games = get_owned_games(conn)

        # Parse and display
        parsed_games = parse_game_data(owned_games)
        display_owned_games(parsed_games)

        # Summary statistics
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total Games: {len(parsed_games)}")

        # Count by platform
        platform_counts = {}
        for game in parsed_games:
            for platform in game["platforms"]:
                platform_counts[platform] = platform_counts.get(platform, 0) + 1

        print("\nGames by Platform:")
        for platform, count in sorted(platform_counts.items()):
            print(f"  {platform}: {count}")

        # Multi-platform games
        multi_platform = [g for g in parsed_games if g["num_platforms"] > 1]
        print(f"\nMulti-platform games: {len(multi_platform)}")

        conn.close()

    except FileNotFoundError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"\nDatabase Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
