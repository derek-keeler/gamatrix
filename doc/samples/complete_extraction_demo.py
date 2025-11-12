#!/usr/bin/env python3
"""
Complete GOG Galaxy Data Extraction Demo

This script demonstrates the complete data extraction process used by Gamatrix,
from identifying the user to building the full game data structure. It replicates
the core logic of gogdb_helper.py in a standalone, educational format.

Usage:
    python complete_extraction_demo.py /path/to/galaxy-2.0.db [output.json]

Arguments:
    db_path: Path to GOG Galaxy database file
    output.json: (Optional) JSON file to write extracted data

Output:
    - Complete game data structure
    - User information
    - Statistics and summary
    - Optional JSON export
"""

import sqlite3
import sys
import os
import json
from datetime import datetime


def connect_to_database(db_path):
    """Connect to the GOG Galaxy database."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    return sqlite3.connect(db_path)


def get_user_info(conn):
    """Extract user information from the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users")
    users = cursor.fetchall()
    
    if not users:
        raise ValueError("No users found in database")
    
    if len(users) > 1:
        print(f"[INFO] Multiple users found, using first one")
    
    user = users[0]
    return {
        'user_id': user[0],
        'username': user[1] if len(user) > 1 else 'Unknown'
    }


def get_gamepiecetype_id(conn, type_name):
    """Get the numeric ID for a GamePieceType."""
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM GamePieceTypes WHERE type=?', (type_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    raise ValueError(f"GamePieceType '{type_name}' not found")


def get_owned_games(conn):
    """
    Extract owned games using the view-based approach.
    
    Returns:
        List of tuples: (comma_separated_release_keys, title_json)
    """
    cursor = conn.cursor()
    
    # Get type IDs
    original_title_id = get_gamepiecetype_id(conn, 'originalTitle')
    title_id = get_gamepiecetype_id(conn, 'title')
    all_releases_id = get_gamepiecetype_id(conn, 'allGameReleases')
    
    # Create MasterList view
    cursor.execute("""
        CREATE TEMP VIEW MasterList AS
        SELECT GamePieces.releaseKey, 
               GamePieces.gamePieceTypeId, 
               GamePieces.value 
        FROM ProductPurchaseDates
        JOIN GamePieces ON ProductPurchaseDates.gameReleaseKey = GamePieces.releaseKey
    """)
    
    # Create MasterDB view
    cursor.execute(f"""
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
    """)
    
    # Query unique games
    cursor.execute("""
        SELECT GROUP_CONCAT(DISTINCT MasterDB.releaseKey), 
               MasterDB.title
        FROM MasterDB 
        GROUP BY MasterDB.platformList 
        ORDER BY MasterDB.title
    """)
    
    return cursor.fetchall()


def get_installed_games(conn):
    """
    Extract list of installed game release keys.
    
    Returns:
        List of release keys
    """
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT trim(GamePieces.releaseKey) 
        FROM GamePieces
        JOIN GamePieceTypes ON GamePieces.gamePieceTypeId = GamePieceTypes.id
        WHERE releaseKey IN (
            SELECT platforms.name || '_' || InstalledExternalProducts.productId
            FROM InstalledExternalProducts
            JOIN Platforms ON InstalledExternalProducts.platformId = Platforms.id
            
            UNION
            
            SELECT 'gog_' || productId FROM InstalledProducts
        )
        AND GamePieceTypes.type = 'originalTitle'
    """)
    
    installed = []
    for result in cursor.fetchall():
        for release_key in result:
            installed.append(release_key)
    
    return installed


def get_all_release_keys(conn, release_key):
    """
    Get all platform release keys for a game.
    
    This is used to find the best key for IGDB lookups.
    Steam keys are most reliable, followed by GOG.
    
    Returns:
        Dict with 'releases' list or empty dict
    """
    cursor = conn.cursor()
    gamepiecetype_id = get_gamepiecetype_id(conn, 'allGameReleases')
    
    cursor.execute("""
        SELECT value FROM GamePieces 
        WHERE releaseKey=? AND gamePieceTypeId=?
    """, (release_key, gamepiecetype_id))
    
    result = cursor.fetchone()
    if result:
        try:
            return json.loads(result[0])
        except (json.JSONDecodeError, TypeError):
            pass
    
    return {}


def get_best_igdb_key(conn, release_key):
    """
    Determine the best release key to use for IGDB lookups.
    
    Priority: Steam > GOG > Original key
    
    Returns:
        Best release key for IGDB lookup
    """
    platform = release_key.split('_')[0] if '_' in release_key else 'unknown'
    
    # Steam keys are already the best
    if platform == 'steam':
        return release_key
    
    # For other platforms, try to find a Steam or GOG alternative
    all_releases = get_all_release_keys(conn, release_key)
    
    if 'releases' not in all_releases:
        return release_key
    
    # Look for Steam key (but not steam_steam_* duplicates)
    for key in all_releases['releases']:
        if key.startswith('steam_') and not key.startswith('steam_steam_'):
            return key
    
    # Look for GOG key
    for key in all_releases['releases']:
        if key.startswith('gog_'):
            return key
    
    # Fall back to original key
    return release_key


def build_game_list(conn, user_info):
    """
    Build the complete game data structure used by Gamatrix.
    
    Returns:
        Dict of game data keyed by release_key
    """
    owned_games = get_owned_games(conn)
    installed_games = get_installed_games(conn)
    
    game_list = {}
    
    for release_keys_str, title_json in owned_games:
        # Parse title
        try:
            title_data = json.loads(title_json)
            title = title_data.get('title', 'Unknown Title')
        except (json.JSONDecodeError, TypeError):
            title = 'Unknown Title'
        
        # Skip games with no title
        if title is None:
            continue
        
        # Process each release key
        release_keys = release_keys_str.split(',') if release_keys_str else []
        
        for release_key in release_keys:
            release_key = release_key.strip()
            
            # Extract platform
            platform = release_key.split('_')[0] if '_' in release_key else 'unknown'
            
            # Create slug (simplified version)
            slug = title.lower().replace(' ', '-').replace(':', '').replace("'", '')
            
            # Determine if installed
            is_installed = release_key in installed_games
            
            # Get best IGDB key
            igdb_key = get_best_igdb_key(conn, release_key)
            
            # Add to game list
            game_list[release_key] = {
                'title': title,
                'slug': slug,
                'platforms': [platform],
                'owners': [user_info['user_id']],
                'installed': [user_info['user_id']] if is_installed else [],
                'igdb_key': igdb_key,
                'multiplayer': False,  # Would be enriched by IGDB
                'max_players': None    # Would be enriched by IGDB
            }
    
    return game_list


def generate_statistics(game_list, user_info):
    """Generate summary statistics about the game data."""
    total_games = len(game_list)
    installed_count = sum(1 for g in game_list.values() if g['installed'])
    
    # Count by platform
    platform_counts = {}
    for game in game_list.values():
        for platform in game['platforms']:
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
    
    # Multi-platform games
    multi_platform = sum(1 for g in game_list.values() if len(g['platforms']) > 1)
    
    # IGDB key distribution
    igdb_platforms = {}
    for game in game_list.values():
        igdb_platform = game['igdb_key'].split('_')[0] if '_' in game['igdb_key'] else 'unknown'
        igdb_platforms[igdb_platform] = igdb_platforms.get(igdb_platform, 0) + 1
    
    return {
        'total_games': total_games,
        'installed_games': installed_count,
        'not_installed': total_games - installed_count,
        'installation_rate': f"{installed_count/total_games*100:.1f}%" if total_games > 0 else "0%",
        'platforms': platform_counts,
        'multi_platform_games': multi_platform,
        'igdb_key_platforms': igdb_platforms,
        'user_id': user_info['user_id'],
        'username': user_info['username']
    }


def display_summary(game_list, stats):
    """Display a summary of the extracted data."""
    print(f"\n{'='*70}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*70}")
    print(f"User: {stats['username']} (ID: {stats['user_id']})")
    print(f"Total Games: {stats['total_games']}")
    print(f"Installed: {stats['installed_games']} ({stats['installation_rate']})")
    print(f"Not Installed: {stats['not_installed']}")
    print(f"Multi-platform: {stats['multi_platform_games']}")
    
    print(f"\nGames by Platform:")
    for platform, count in sorted(stats['platforms'].items()):
        print(f"  {platform}: {count}")
    
    print(f"\nIGDB Key Distribution:")
    for platform, count in sorted(stats['igdb_key_platforms'].items()):
        print(f"  {platform}: {count}")
    
    # Show a few example games
    print(f"\nSample Games (first 5):")
    for i, (release_key, game) in enumerate(list(game_list.items())[:5], 1):
        print(f"\n  {i}. {game['title']}")
        print(f"     Release Key: {release_key}")
        print(f"     Platforms: {', '.join(game['platforms'])}")
        print(f"     Installed: {'Yes' if game['installed'] else 'No'}")
        print(f"     IGDB Key: {game['igdb_key']}")


def export_to_json(game_list, stats, output_file):
    """Export the extracted data to a JSON file."""
    export_data = {
        'metadata': {
            'extraction_date': datetime.now().isoformat(),
            'user_id': stats['user_id'],
            'username': stats['username'],
            'total_games': stats['total_games'],
            'installed_games': stats['installed_games']
        },
        'statistics': stats,
        'games': game_list
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nData exported to: {output_file}")


def main():
    """Main function to perform complete extraction."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    db_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("="*70)
    print("GOG Galaxy Complete Data Extraction Demo")
    print("="*70)
    print(f"Database: {db_path}")
    if output_file:
        print(f"Output: {output_file}")
    print()
    
    try:
        # Connect to database
        conn = connect_to_database(db_path)
        
        # Step 1: Get user info
        print("Step 1: Extracting user information...")
        user_info = get_user_info(conn)
        print(f"  User: {user_info['username']} (ID: {user_info['user_id']})")
        
        # Step 2: Build game list
        print("\nStep 2: Building game list...")
        game_list = build_game_list(conn, user_info)
        print(f"  Extracted: {len(game_list)} games")
        
        # Step 3: Generate statistics
        print("\nStep 3: Generating statistics...")
        stats = generate_statistics(game_list, user_info)
        
        # Display summary
        display_summary(game_list, stats)
        
        # Export to JSON if requested
        if output_file:
            print(f"\nStep 4: Exporting to JSON...")
            export_to_json(game_list, stats, output_file)
        
        print(f"\n{'='*70}")
        print("Extraction complete!")
        print(f"{'='*70}")
        
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
