#!/usr/bin/env python3
"""
Data store management utility for gamatrix.

This utility provides commands to manage the gamatrix data store:
- rebuild: Rebuild the data store from all existing GOG database files
- verify: Verify the integrity of the data store
- backup: Create a manual backup of the data store
- restore: Restore from a backup

Usage:
    gamatrix-data-store.py rebuild [--config-file=CFG] [--force]
    gamatrix-data-store.py verify [--config-file=CFG]
    gamatrix-data-store.py backup [--config-file=CFG]
    gamatrix-data-store.py restore [--config-file=CFG] [--backup-number=N]
    gamatrix-data-store.py --help

Options:
  -h, --help                   Show this help message and exit.
  -c CFG, --config-file=CFG    The config file to use.
  -f, --force                  Force rebuild even if data store exists.
  -b N, --backup-number=N      Backup number to restore (1 is most recent).
"""

import sys
import os
import logging
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import docopt
import yaml

from gamatrix.helpers.data_store_helper import DataStoreHelper, DataStore
from gamatrix.helpers.ingestion_helper import IngestionHelper


def load_config(config_file):
    """Load configuration from YAML file."""
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading config file {config_file}: {e}")
        sys.exit(1)


def rebuild_data_store(config, force=False):
    """Rebuild the data store from all existing GOG database files."""
    data_store_path = config.get(
        "data_store_path", os.path.join(config["db_path"], "gamatrix_data_store.json")
    )

    if os.path.exists(data_store_path) and not force:
        print(f"Data store already exists at {data_store_path}")
        print("Use --force to rebuild anyway, or backup first with the backup command")
        return False

    print(f"Rebuilding data store at {data_store_path}")

    # Initialize helpers
    data_store_helper = DataStoreHelper(data_store_path, config.get("max_backups", 3))
    ingestion_helper = IngestionHelper(config)

    # Create new data store
    data_store = DataStore(users={}, games={}, last_updated="")

    # Process each user
    users_processed = 0
    for user_id in config["users"]:
        if "db" not in config["users"][user_id]:
            print(f"Warning: User {user_id} has no database file configured, skipping")
            continue

        db_path = f"{config['db_path']}/{config['users'][user_id]['db']}"

        if not os.path.exists(db_path):
            print(
                f"Warning: Database file not found for user {user_id}: {db_path}, skipping"
            )
            continue

        try:
            print(
                f"Processing user {user_id} ({config['users'][user_id]['username']})..."
            )
            user_data, user_games = ingestion_helper.extract_user_data(user_id, db_path)
            data_store = data_store_helper.update_user_data(
                data_store, user_id, user_data, user_games
            )
            users_processed += 1
            print(f"  Extracted {len(user_games)} games for user {user_id}")

        except Exception as e:
            print(f"Error processing user {user_id}: {e}")
            continue

    if users_processed == 0:
        print("No users were processed successfully")
        return False

    # Save the data store
    if data_store_helper.save_data_store(data_store):
        print(
            f"Successfully rebuilt data store with {len(data_store.users)} users and {len(data_store.games)} games"
        )
        return True
    else:
        print("Error saving data store")
        return False


def verify_data_store(config):
    """Verify the integrity of the data store."""
    data_store_path = config.get(
        "data_store_path", os.path.join(config["db_path"], "gamatrix_data_store.json")
    )

    if not os.path.exists(data_store_path):
        print(f"Data store does not exist at {data_store_path}")
        return False

    print(f"Verifying data store at {data_store_path}")

    data_store_helper = DataStoreHelper(data_store_path)
    data_store = data_store_helper.load_data_store()

    if data_store is None:
        print("Error: Data store could not be loaded")
        return False

    print(f"Data store loaded successfully")
    print(f"  Version: {data_store.version}")
    print(f"  Last updated: {data_store.last_updated}")
    print(f"  Users: {len(data_store.users)}")
    print(f"  Games: {len(data_store.games)}")

    # Verify data consistency
    issues_found = 0

    # Check users
    for user_id, user_data in data_store.users.items():
        if user_id not in config["users"]:
            print(f"Warning: User {user_id} in data store but not in config")
            issues_found += 1

    # Check games
    for release_key, game_data in data_store.games.items():
        # Check if all owners exist in users
        for owner_id in game_data.owners:
            if owner_id not in data_store.users:
                print(
                    f"Error: Game {release_key} owned by non-existent user {owner_id}"
                )
                issues_found += 1

        # Check if all installed users exist and own the game
        for installed_id in game_data.installed:
            if installed_id not in data_store.users:
                print(
                    f"Error: Game {release_key} installed by non-existent user {installed_id}"
                )
                issues_found += 1
            elif installed_id not in game_data.owners:
                print(
                    f"Error: Game {release_key} installed by user {installed_id} who doesn't own it"
                )
                issues_found += 1

    if issues_found == 0:
        print("Data store verification completed successfully - no issues found")
        return True
    else:
        print(f"Data store verification completed with {issues_found} issues found")
        return False


def create_backup(config):
    """Create a manual backup of the data store."""
    data_store_path = config.get(
        "data_store_path", os.path.join(config["db_path"], "gamatrix_data_store.json")
    )

    if not os.path.exists(data_store_path):
        print(f"Data store does not exist at {data_store_path}")
        return False

    data_store_helper = DataStoreHelper(data_store_path, config.get("max_backups", 3))
    data_store_helper._rotate_backups()

    print(f"Backup created successfully")
    return True


def restore_backup(config, backup_number=1):
    """Restore from a backup."""
    data_store_path = config.get(
        "data_store_path", os.path.join(config["db_path"], "gamatrix_data_store.json")
    )

    backup_path = f"{data_store_path}.backup.{backup_number}"

    if not os.path.exists(backup_path):
        print(f"Backup file does not exist: {backup_path}")
        return False

    try:
        import shutil

        shutil.copy2(backup_path, data_store_path)
        print(f"Successfully restored from backup {backup_number}")
        return True
    except Exception as e:
        print(f"Error restoring backup: {e}")
        return False


def main():
    """Main entry point."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    args = docopt.docopt(__doc__)

    config_file = args.get("--config-file", "config.yaml")
    config = load_config(config_file)

    if args["rebuild"]:
        force = args.get("--force", False)
        success = rebuild_data_store(config, force)
        sys.exit(0 if success else 1)
    elif args["verify"]:
        success = verify_data_store(config)
        sys.exit(0 if success else 1)
    elif args["backup"]:
        success = create_backup(config)
        sys.exit(0 if success else 1)
    elif args["restore"]:
        backup_number = int(args.get("--backup-number", 1))
        success = restore_backup(config, backup_number)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
