#!/usr/bin/env python3
"""
gamatrix
Show and compare between games owned by multiple users.

Usage:
    gamatrix --help
    gamatrix --version
    gamatrix [--config-file=CFG] [--debug] [--all-games] [--interface=IFC] [--installed-only] [--include-single-player] [--port=PORT] [--server] [--update-cache] [--userid=UID ...]

Options:
  -h, --help                   Show this help message and exit.
  -v, --version                Print version and exit.
  -c CFG, --config-file=CFG    The config file to use.
  -d, --debug                  Print out verbose debug output.
  -a, --all-games              List all games owned by the selected users (doesn't include single player unless -S is used).
  -i IFC, --interface=IFC      The network interface to use if running in server mode; default is 0.0.0.0.
  -I, --installed-only         Only show games installed by all users.
  -p PORT, --port=PORT         The network port to use if running in server mode; default is 8080.
  -s, --server                 Run in server mode.
  -S, --include-single-player  Include single player games.
  -U, --update-cache           Update cache entries that have incomplete info.
  -u USERID, --userid=USERID   The GOG user IDs to compare, there can be multiples of this switch.
"""

import docopt
import logging
import os
from importlib import metadata
import random
import sys
import time

from flask import Flask, render_template, request
from ipaddress import IPv4Address, IPv4Network
import yaml
from typing import Any, Dict, List
from werkzeug.utils import secure_filename

import gamatrix.helpers.constants as constants
from gamatrix.helpers.cache_helper import Cache
from gamatrix.helpers.gogdb_helper import gogDB, is_sqlite3
from gamatrix.helpers.igdb_helper import IGDBHelper
from gamatrix.helpers.misc_helper import get_slug_from_title
from gamatrix.helpers.network_helper import check_ip_is_authorized
from gamatrix.helpers.data_store_helper import DataStoreHelper
from gamatrix.helpers.ingestion_helper import IngestionHelper

app = Flask(__name__)


@app.route("/")
def root():
    check_ip_is_authorized(request.remote_addr, config["allowed_cidrs"])

    return render_template(
        "index.html.jinja",
        users=config["users"],
        uploads_enabled=config["uploads_enabled"],
        platforms=constants.PLATFORMS,
        version=version,
    )


# https://flask.palletsprojects.com/en/2.0.x/patterns/fileuploads/
@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    check_ip_is_authorized(request.remote_addr, config["allowed_cidrs"])

    if request.method == "POST":
        message = "Upload failed: "

        # Check if the post request has the file part
        if "file" not in request.files:
            message += "no file part in post request"
        else:
            # Until we use a prod server, files that are too large will just hang :-(
            # See the flask site above for deets
            file = request.files["file"]

            # If user does not select file, the browser submits an empty part without filename
            if file.filename == "":
                message += "no file selected"
            elif not allowed_file(file.filename):
                message += "unsupported file extension"
            else:
                # Name the file according to who uploaded it
                user, target_filename = get_db_name_from_ip(request.remote_addr)
                if target_filename is None:
                    message += "failed to determine target filename from your IP; is it in the config file?"
                elif not is_sqlite3(file.read(16)):
                    message += "file is not an SQLite database"
                else:
                    log.info(f"Uploading {target_filename} from {request.remote_addr}")
                    filename = secure_filename(target_filename)

                    # Back up the previous file
                    full_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    backup_filename = f"{filename}.bak"
                    full_backup_path = os.path.join(
                        app.config["UPLOAD_FOLDER"], backup_filename
                    )

                    if os.path.exists(full_path):
                        os.replace(full_path, full_backup_path)

                    # Put the cursor back to the start after the above file.read()
                    file.seek(0)
                    file.save(full_path)
                    # Could call get_db_mtime() here but this is less expensive
                    config["users"][user]["db_mtime"] = time.strftime(
                        constants.TIME_FORMAT, time.localtime()
                    )

                    # NEW: Extract and store game data immediately
                    try:
                        log.info(f"Extracting game data for user {user}")

                        # Initialize data store helper
                        data_store_path = config.get(
                            "data_store_path",
                            os.path.join(config["db_path"], "gamatrix_data_store.json"),
                        )
                        data_store_helper = DataStoreHelper(
                            data_store_path, config.get("max_backups", 3)
                        )

                        # Load existing data store
                        data_store = data_store_helper.load_data_store()

                        # Extract data for the uploaded user
                        ingestion_helper = IngestionHelper(config)
                        user_data, user_games = ingestion_helper.extract_user_data(
                            user, full_path
                        )

                        # Update data store with new user data
                        data_store = data_store_helper.update_user_data(
                            data_store, user, user_data, user_games
                        )

                        # Save updated data store
                        if data_store_helper.save_data_store(data_store):
                            log.info(f"Successfully updated data store for user {user}")
                            message = f"Great success! File uploaded as {filename} and data extracted"
                        else:
                            log.error(f"Failed to save data store for user {user}")
                            message = f"File uploaded as {filename} but data extraction failed"

                    except Exception as e:
                        log.error(f"Error during data extraction for user {user}: {e}")
                        message = f"File uploaded as {filename} but data extraction failed: {e}"

        return render_template("upload_status.html.jinja", message=message)
    else:
        return """
        <!doctype html>
        <title>Upload DB</title>
        <h1>Upload DB</h1>
        GOG DBs are usually in C:\\ProgramData\\GOG.com\\Galaxy\\storage\\galaxy-2.0.db
        <br><br>
        <form method=post enctype=multipart/form-data>
        <input type=file name=file>
        <input type=submit value=Upload>
        </form>
        """


@app.route("/compare", methods=["GET", "POST"])
def compare_libraries():
    check_ip_is_authorized(request.remote_addr, config["allowed_cidrs"])

    if request.args["option"] == "upload":
        return upload_file()

    opts = init_opts()

    # Check boxes get passed in as "on" if checked, or not at all if unchecked
    for k in request.args.keys():
        # Only user IDs are ints
        try:
            i = int(k)
            opts["user_ids_to_compare"][i] = config["users"][i]
        except ValueError:
            if k.startswith("exclude_platform_"):
                opts["exclude_platforms"].append(k.split("_")[-1])
            else:
                opts[k] = True

    # If no users were selected, just refresh the page
    if not opts["user_ids_to_compare"]:
        return root()

    if request.args["option"] == "grid":
        config["all_games"] = True
        template = "game_grid.html.jinja"
    elif request.args["option"] == "list":
        template = "game_list.html.jinja"
    else:
        return root()

    # NEW: Try to get games from data store first
    common_games = get_common_games_from_data_store(opts)

    if common_games is None:
        # Fallback to original method if data store is not available
        log.info("Falling back to original DB parsing method")
        gog = gogDB(config, opts)
        common_games = gog.get_common_games()
    else:
        log.info(
            f"Using data store for game comparison, found {len(common_games)} games"
        )

    if not igdb.access_token:
        igdb.get_access_token()

    for k in list(common_games.keys()):
        log.debug(f'{k}: using igdb_key {common_games[k]["igdb_key"]}')
        # Get the IGDB ID by release key if possible, otherwise try by title
        igdb.get_igdb_id(common_games[k]["igdb_key"]) or igdb.get_igdb_id_by_slug(
            common_games[k]["igdb_key"],
            common_games[k]["slug"],
            config["update_cache"],
        )  # type: ignore
        igdb.get_game_info(common_games[k]["igdb_key"])
        igdb.get_multiplayer_info(common_games[k]["igdb_key"])

    cache.save()
    set_multiplayer_status(common_games, cache.data)
    common_games = gog.merge_duplicate_titles(common_games)

    common_games = gog.filter_games(common_games, gog.config["all_games"])
    num_games = len(common_games)

    log.debug(f'user_ids_to_compare = {opts["user_ids_to_compare"]}')

    if opts["randomize"]:
        key = random.choice(list(common_games))
        log.debug(f"Chose random release key {key}")
        common_games = {key: common_games[key]}

    debug_str = ""
    return render_template(
        template,
        debug_str=debug_str,
        games=common_games,
        users=opts["user_ids_to_compare"],
        caption=gog.get_caption(num_games, opts["randomize"]),
        show_keys=opts["show_keys"],
        randomize=opts["randomize"],
        platforms=constants.PLATFORMS,
    )


def get_db_name_from_ip(ip):
    """Returns the userid and DB filename based on the IP of the user"""
    ip = IPv4Address(ip)

    for user in config["users"]:
        if "cidrs" in config["users"][user]:
            for cidr in config["users"][user]["cidrs"]:
                if ip in cidr:
                    return user, config["users"][user]["db"]

    return None, None


def allowed_file(filename):
    """Returns True if filename has an allowed extension"""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in constants.UPLOAD_ALLOWED_EXTENSIONS
    )


def init_opts():
    """Initializes the options to pass to the gogDB class. Since the
    config is only read once, we need to be able to reinit any options
    that can be passed from the web UI
    """

    return {
        "include_single_player": False,
        "exclusive": False,
        "show_keys": False,
        "randomize": False,
        "user_ids_to_compare": {},
        "exclude_platforms": [],
    }


def get_common_games_from_data_store(opts):
    """
    Get common games from the data store instead of parsing raw DB files.

    Args:
        opts: Options dictionary with user_ids_to_compare and filtering options

    Returns:
        Dictionary of common games in the same format as the original get_common_games
    """
    log.debug("Getting common games from data store")

    # Load data store
    data_store_path = config.get(
        "data_store_path", os.path.join(config["db_path"], "gamatrix_data_store.json")
    )
    data_store_helper = DataStoreHelper(data_store_path)
    data_store = data_store_helper.load_data_store()

    if data_store is None:
        log.warning("No data store found, falling back to raw DB parsing")
        return None

    user_ids_to_compare = list(opts["user_ids_to_compare"].keys())
    exclude_platforms = opts.get("exclude_platforms", [])
    include_single_player = opts.get("include_single_player", False)
    exclusive = opts.get("exclusive", False)
    all_games = config.get("all_games", False)

    log.debug(f"Comparing users: {user_ids_to_compare}")
    log.debug(f"Exclusive mode: {exclusive}")
    log.debug(f"Include single player: {include_single_player}")
    log.debug(f"All games: {all_games}")

    # Filter games based on criteria
    filtered_games = {}

    for release_key, game_data in data_store.games.items():
        # Check if users own this game
        game_owners = set(game_data.owners)
        comparing_users = set(user_ids_to_compare)

        if exclusive:
            # Exclusive mode: only games owned by selected users and not by others
            all_users = set(data_store.users.keys())
            non_comparing_users = all_users - comparing_users
            non_comparing_owners = game_owners & non_comparing_users

            if non_comparing_owners:
                # Game is owned by non-selected users, skip it
                continue

            # Must be owned by at least one selected user
            if not (game_owners & comparing_users):
                continue
        else:
            # Normal mode: games owned by all selected users
            if not comparing_users.issubset(game_owners):
                continue

        # Filter by platform
        if exclude_platforms:
            game_platforms = set(game_data.platforms)
            if game_platforms.issubset(set(exclude_platforms)):
                # All platforms are excluded
                continue

        # Filter single player games
        if not include_single_player and not game_data.multiplayer:
            continue

        # Convert to the expected format
        filtered_games[release_key] = {
            "title": game_data.title,
            "slug": game_data.slug,
            "platforms": game_data.platforms,
            "owners": game_data.owners,
            "installed": game_data.installed,
            "igdb_key": game_data.igdb_key,
            "multiplayer": game_data.multiplayer,
            "max_players": game_data.max_players,
        }

        # Add optional fields if present
        if game_data.comment:
            filtered_games[release_key]["comment"] = game_data.comment
        if game_data.url:
            filtered_games[release_key]["url"] = game_data.url

    log.debug(f"Found {len(filtered_games)} games matching criteria")
    return filtered_games


def get_db_mtime(db):
    """Returns the modification time of DB in local time"""
    try:
        mtime = time.strftime(
            constants.TIME_FORMAT, time.localtime(os.path.getmtime(db))
        )
    except Exception:
        mtime = "unavailable"
    return mtime


def build_config(args: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a config dict created from the config file and
    command-line arguments, with the latter taking precedence
    """
    config_file = args.get("--config-file", None)
    if config_file is not None:
        with open(config_file, "r") as config_file:
            config = yaml.safe_load(config_file)
    else:
        # We didn't get a config file, so populate from args
        config = {}

    # TODO: allow using user IDs
    # TODO: should be able to use unambiguous partial names
    if "users" not in config:
        raise ValueError("You must use -u or have users in the config file")

    # Command-line args override values in the config file

    # This can't be given as an argument as it wouldn't make much sense;
    #  provide a sane default if it's missing from the config file
    if "db_path" not in config:
        config["db_path"] = "."

    config["all_games"] = args.get("--all-games", False)
    config["include_single_player"] = args.get("--include-single-player", False)
    config["installed_only"] = args.get("--installed-only", False)

    if args.get(
        "--server", False
    ):  # Note that the --server opt is False unless present
        config["mode"] = "server"

    if args.get("--interface"):
        config["interface"] = args["--interface"]
    if "interface" not in config:
        config["interface"] = "0.0.0.0"

    if args.get("--port"):
        config["port"] = int(args["--port"])
    if "port" not in config:
        config["port"] = 8080

    # Convert allowed CIDRs into IPv4Network objects
    cidrs = []
    if "allowed_cidrs" in config:
        for cidr in config["allowed_cidrs"]:
            cidrs.append(IPv4Network(cidr))
    config["allowed_cidrs"] = cidrs

    # DBs and user IDs can be in the config file and/or passed in as args
    config["db_list"] = []
    if "users" not in config:
        config["users"] = {}

    for userid in config["users"]:
        full_db_path = f'{config["db_path"]}/{config["users"][userid]["db"]}'
        config["db_list"].append(full_db_path)
        config["users"][userid]["db_mtime"] = get_db_mtime(full_db_path)

        # Convert CIDRs into IPv4Network objects; if there are none, disable uploads
        config["uploads_enabled"] = False
        if "cidrs" in config["users"][userid]:
            for i in range(len(config["users"][userid]["cidrs"])):
                config["users"][userid]["cidrs"][i] = IPv4Network(
                    config["users"][userid]["cidrs"][i]
                )
                config["uploads_enabled"] = True

    for userid_str in args.get("--userid", []):
        userid = int(userid_str)
        if userid not in config["users"]:
            raise ValueError(f"User ID {userid} isn't defined in the config file")
        elif "db" not in config["users"][userid]:
            raise ValueError(
                f"User ID {userid} is missing the db key in the config file"
            )
        elif (
            f'{config["db_path"]}/{config["users"][userid]["db"]}'
            not in config["db_list"]
        ):
            config["db_list"].append(
                f'{config["db_path"]}/{config["users"][userid]["db"]}'
            )

    # Order users by username to avoid having to do it in the templates
    config["users"] = {
        k: v
        for k, v in sorted(
            config["users"].items(), key=lambda item: item[1]["username"].lower()
        )
    }

    if "hidden" not in config:
        config["hidden"] = []

    config["update_cache"] = args.get("--update-cache", False)

    # Lowercase and remove non-alphanumeric characters for better matching
    for i in range(len(config["hidden"])):
        config["hidden"][i] = get_slug_from_title(config["hidden"][i])

    slug_metadata = {}
    for title in config["metadata"]:
        slug = get_slug_from_title(title)
        slug_metadata[slug] = config["metadata"][title]

    config["metadata"] = slug_metadata

    return config


def set_multiplayer_status(game_list, cache):
    """
    Sets the max_players for each release key; precedence is:
      - max_players in the config yaml
      - max_players from IGDB
      - 1 if the above aren't available and the only game mode from IGDB is single player
      - 0 (unknown) otherwise
    Also sets multiplayer to True if any of the of the following are true:
      - max_players > 1
      - IGDB game modes includes a multiplayer mode
    """
    for k in game_list:
        igdb_key = game_list[k]["igdb_key"]
        max_players = 0
        multiplayer = False
        reason = "as we have no max player info and can't infer from game modes"

        if "max_players" in game_list[k]:
            max_players = game_list[k]["max_players"]
            reason = "from config file"
            multiplayer = max_players > 1

        elif igdb_key not in cache["igdb"]["games"]:
            reason = (
                f"no IGDB info in cache for {igdb_key}, did you call get_igdb_id()?"
            )

        elif "max_players" not in cache["igdb"]["games"][igdb_key]:
            reason = f"IGDB {igdb_key} max_players not found, did you call get_multiplayer_info()?"
            log.warning(f"{k}: something seems wrong, see next message")

        elif cache["igdb"]["games"][igdb_key]["max_players"] > 0:
            max_players = cache["igdb"]["games"][igdb_key]["max_players"]
            reason = "from IGDB cache"
            multiplayer = cache["igdb"]["games"][igdb_key]["max_players"] > 1

        # We don't have max player info, so try to infer it from game modes
        elif (
            "info" in cache["igdb"]["games"][igdb_key]
            and cache["igdb"]["games"][igdb_key]["info"]
            and "game_modes" in cache["igdb"]["games"][igdb_key]["info"][0]
        ):
            if cache["igdb"]["games"][igdb_key]["info"][0]["game_modes"] == [
                constants.IGDB_GAME_MODE["singleplayer"]
            ]:
                max_players = 1
                reason = "as IGDB has single player as the only game mode"
            else:
                for mode in cache["igdb"]["games"][igdb_key]["info"][0]["game_modes"]:
                    if mode in constants.IGDB_MULTIPLAYER_GAME_MODES:
                        multiplayer = True
                        reason = f"as game modes includes {mode}"
                        break

        log.debug(
            f"{k} ({game_list[k]['title']}, IGDB key {igdb_key}): "
            f"multiplayer {multiplayer}, max players {max_players} {reason}"
        )
        game_list[k]["multiplayer"] = multiplayer
        game_list[k]["max_players"] = max_players


def parse_cmdline(argv: List[str], docstr: str, version: str) -> Dict[str, Any]:
    """Get the docopt stuff out of the way because ugly."""
    return docopt.docopt(
        docstr,
        argv=argv,
        help=True,
        version=version,
        options_first=True,
    )


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log = logging.getLogger()

    version = metadata.version("gamatrix")

    opts = parse_cmdline(
        argv=sys.argv[1:],
        docstr=__doc__ if __doc__ is not None else "",
        version=version,
    )

    if opts.get("--debug", False):
        log.setLevel(logging.DEBUG)

    log.debug(f"Command line arguments: {sys.argv}")
    log.debug(f"Arguments after parsing: {opts}")

    config = build_config(opts)
    log.debug(f"config = {config}")

    cache = Cache(config["cache"])
    # Get multiplayer info from IGDB and save it to the cache
    igdb = IGDBHelper(
        config["igdb_client_id"], config["igdb_client_secret"], cache.data
    )

    if "mode" in config and config["mode"] == "server":
        # Start Flask to run in server mode until killed
        if os.name != "nt":
            time.tzset()  # type: ignore

        app.config["UPLOAD_FOLDER"] = config["db_path"]
        app.config["MAX_CONTENT_LENGTH"] = constants.UPLOAD_MAX_SIZE
        app.run(host=config["interface"], port=config["port"])
        sys.exit(0)

    user_ids_to_compare = opts.get("--userid", [])
    if user_ids_to_compare:
        user_ids_to_compare = [int(u) for u in user_ids_to_compare]
    else:
        user_ids_to_compare = [u for u in config["users"].keys()]

    # init_opts() is meant for server mode; any CLI options that are also
    # web UI options need to be overridden
    web_opts = init_opts()
    web_opts["include_single_player"] = opts.get("--include-single-player", False)

    for userid in user_ids_to_compare:
        web_opts["user_ids_to_compare"][userid] = config["users"][userid]

    log.debug(f'user_ids_to_compare = {web_opts["user_ids_to_compare"]}')

    # NEW: Try to get games from data store first for CLI mode too
    common_games = get_common_games_from_data_store(web_opts)

    if common_games is None:
        # Fallback to original method if data store is not available
        log.info("Data store not available, using original DB parsing method")
        gog = gogDB(config, web_opts)
        common_games = gog.get_common_games()

        # Apply original processing for IGDB data
        for k in list(common_games.keys()):
            log.debug(f'{k}: using igdb_key {common_games[k]["igdb_key"]}')
            # Get the IGDB ID by release key if possible, otherwise try by title
            igdb.get_igdb_id(
                common_games[k]["igdb_key"], config["update_cache"]
            ) or igdb.get_igdb_id_by_slug(
                common_games[k]["igdb_key"],
                common_games[k]["slug"],
                config["update_cache"],
            )  # type: ignore
            igdb.get_game_info(common_games[k]["igdb_key"], config["update_cache"])
            igdb.get_multiplayer_info(
                common_games[k]["igdb_key"], config["update_cache"]
            )

        cache.save()
        set_multiplayer_status(common_games, cache.data)
        common_games = gog.merge_duplicate_titles(common_games)
        common_games = gog.filter_games(common_games, config["all_games"])
    else:
        log.info(f"Using data store for CLI mode, found {len(common_games)} games")
        # Data store already has processed data, less processing needed
        # But we might still want to update IGDB info if requested
        if config.get("update_cache", False):
            for k in list(common_games.keys()):
                igdb.get_igdb_id(
                    common_games[k]["igdb_key"], config["update_cache"]
                ) or igdb.get_igdb_id_by_slug(
                    common_games[k]["igdb_key"],
                    common_games[k]["slug"],
                    config["update_cache"],
                )  # type: ignore
                igdb.get_game_info(common_games[k]["igdb_key"], config["update_cache"])
                igdb.get_multiplayer_info(
                    common_games[k]["igdb_key"], config["update_cache"]
                )
            cache.save()

    for key in common_games:
        usernames_with_game_installed = [
            config["users"][userid]["username"]
            for userid in common_games[key]["installed"]
        ]

        print(
            "{} ({})".format(
                common_games[key]["title"],
                ", ".join(common_games[key]["platforms"]),
            ),
            end="",
        )
        if "max_players" in common_games[key]:
            print(f' Players: {common_games[key]["max_players"]}', end="")
        if "comment" in common_games[key]:
            print(f' Comment: {common_games[key]["comment"]}', end="")
        if not usernames_with_game_installed:
            print(" Installed: (none)")
        else:
            print(f' Installed: {", ".join(usernames_with_game_installed)}')

    print(gog.get_caption(len(common_games)))
