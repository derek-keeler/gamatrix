#!/usr/bin/env python3
"""
Extract Installed Games from GOG Galaxy Database

This script identifies which games are currently installed on the system
by querying both GOG and external platform installation tables.

Usage:
    python extract_installed_games.py /path/to/galaxy-2.0.db

Output:
    - List of installed games (GOG and external platforms)
    - Platform information for each installed game
    - Comparison with owned games
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


def get_gamepiecetype_id(conn, type_name):
    """Get the numeric ID for a GamePieceType."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM GamePieceTypes WHERE type=?", (type_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    raise ValueError(f"GamePieceType '{type_name}' not found")


def get_installed_games(conn):
    """
    Extract installed games using Gamatrix's query approach.

    This query:
    1. Gets installed GOG games from InstalledProducts
    2. Gets installed external platform games from InstalledExternalProducts
    3. Unions them together and matches with GamePieces to get release keys

    Returns:
        List of release keys for installed games
    """
    cursor = conn.cursor()

    # This query matches the one in gogdb_helper.py
    query = """
        SELECT trim(GamePieces.releaseKey) 
        FROM GamePieces
        JOIN GamePieceTypes ON GamePieces.gamePieceTypeId = GamePieceTypes.id
        WHERE releaseKey IN (
            -- External platform games (Steam, Epic, etc.)
            SELECT platforms.name || '_' || InstalledExternalProducts.productId
            FROM InstalledExternalProducts
            JOIN Platforms ON InstalledExternalProducts.platformId = Platforms.id
            
            UNION
            
            -- GOG games
            SELECT 'gog_' || productId FROM InstalledProducts
        )
        AND GamePieceTypes.type = 'originalTitle'
    """

    cursor.execute(query)
    installed_games = []

    # Each result is a tuple with one element (the release key)
    installed_games = [result[0] for result in cursor.fetchall()]

    return installed_games


def get_game_title(conn, release_key):
    """
    Get the title for a game given its release key.

    Args:
        conn: Database connection
        release_key: Release key (e.g., 'steam_730')

    Returns:
        Game title or None if not found
    """
    cursor = conn.cursor()

    # Try originalTitle first
    cursor.execute(
        """
        SELECT gp.value 
        FROM GamePieces gp
        JOIN GamePieceTypes gpt ON gp.gamePieceTypeId = gpt.id
        WHERE gp.releaseKey = ? AND gpt.type = 'originalTitle'
    """,
        (release_key,),
    )

    result = cursor.fetchone()
    if result:
        try:
            data = json.loads(result[0])
            return data.get("title", "Unknown")
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    # Try regular title as fallback
    cursor.execute(
        """
        SELECT gp.value 
        FROM GamePieces gp
        JOIN GamePieceTypes gpt ON gp.gamePieceTypeId = gpt.id
        WHERE gp.releaseKey = ? AND gpt.type = 'title'
    """,
        (release_key,),
    )

    result = cursor.fetchone()
    if result:
        try:
            data = json.loads(result[0])
            return data.get("title", "Unknown")
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    return "Unknown Title"


def get_platform_info(conn):
    """
    Get mapping of platform IDs to names.

    Returns:
        Dict mapping platform_id -> platform_name
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM Platforms")
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_installation_details(conn):
    """
    Get detailed installation information.

    Returns:
        Tuple of (gog_installed, external_installed)
        where each is a list of dicts with game details
    """
    cursor = conn.cursor()
    platform_map = get_platform_info(conn)

    # GOG installed games
    cursor.execute("SELECT productId FROM InstalledProducts")
    gog_installed = []
    for row in cursor.fetchall():
        product_id = row[0]
        release_key = f"gog_{product_id}"
        title = get_game_title(conn, release_key)
        gog_installed.append(
            {
                "product_id": product_id,
                "release_key": release_key,
                "platform": "gog",
                "title": title,
            }
        )

    # External platform installed games
    cursor.execute(
        """
        SELECT productId, platformId 
        FROM InstalledExternalProducts
    """
    )
    external_installed = []
    for row in cursor.fetchall():
        product_id, platform_id = row
        platform_name = platform_map.get(platform_id, "unknown")
        release_key = f"{platform_name}_{product_id}"
        title = get_game_title(conn, release_key)
        external_installed.append(
            {
                "product_id": product_id,
                "release_key": release_key,
                "platform": platform_name,
                "platform_id": platform_id,
                "title": title,
            }
        )

    return gog_installed, external_installed


def display_installed_games(installed_games, gog_details, external_details):
    """Display installed games in a human-readable format."""
    print(f"\n{'='*70}")
    print(f"INSTALLED GAMES ({len(installed_games)} found)")
    print(f"{'='*70}\n")

    # Group by platform
    by_platform = {}
    all_details = gog_details + external_details

    for detail in all_details:
        platform = detail["platform"]
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(detail)

    # Display by platform
    for platform in sorted(by_platform.keys()):
        games = by_platform[platform]
        print(f"\n{platform.upper()} ({len(games)} games)")
        print("-" * 70)
        for game in games:
            print(f"  • {game['title']}")
            print(f"    Release Key: {game['release_key']}")
            print(f"    Product ID: {game['product_id']}")
            print()


def main():
    """Main function to extract and display installed games."""
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    db_path = sys.argv[1]

    print("=" * 70)
    print("GOG Galaxy Installed Games Extractor")
    print("=" * 70)
    print(f"Database: {db_path}\n")

    try:
        # Connect to database
        conn = connect_to_database(db_path)

        # Get installed games (simple list)
        print("Extracting installed games...")
        installed_games = get_installed_games(conn)

        # Get detailed installation info
        gog_details, external_details = get_installation_details(conn)

        # Display results
        display_installed_games(installed_games, gog_details, external_details)

        # Summary
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total Installed: {len(installed_games)}")
        print(f"GOG Games: {len(gog_details)}")
        print(f"External Platform Games: {len(external_details)}")

        # Platform breakdown
        platform_counts = {}
        for detail in gog_details + external_details:
            platform = detail["platform"]
            platform_counts[platform] = platform_counts.get(platform, 0) + 1

        print("\nInstalled by Platform:")
        for platform, count in sorted(platform_counts.items()):
            print(f"  {platform}: {count}")

        # Compare with owned games
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ProductPurchaseDates")
        owned_count = cursor.fetchone()[0]

        print(f"\nOwned but Not Installed: {owned_count - len(installed_games)}")
        if owned_count > 0:
            print(f"Installation Rate: {len(installed_games)/owned_count*100:.1f}%")
        else:
            print("Installation Rate: N/A")

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
