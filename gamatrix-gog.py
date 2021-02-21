#!/usr/bin/env python3
"""
gamatrix-gog
Show and compare between games owned by multiple users.

Usage:
    gamatrix-gog.py --help
    gamatrix-gog.py --version
    gamatrix-gog.py [--config-file=CFG] [--debug] [--all-games] [--interface=IFC] [--include-single-player] [--port=PORT] [--server] [--userid=UID ...] [--include-zero-players] [<db> ... ]

Options:
  -h, --help                   show this help message and exit
  -v, --version                print version and exit
  -c CFG --config-file=CFG     the config file to use
  -d, --debug                  debug output
  -a, --all-games              list all games owned by the selected users (doesn't include single player unless -I is used)
  -i IFC, --interface=IFC      the network interface to use if running in server mode; default is 0.0.0.0.
  -I, --include-single-player  include single player games
  -p PORT, --port=PORT         the network port to use if running in server mode; default is 8080.
  -s, --server                 run in server mode
  -u USERID, --userid=USERID   the GOG user IDs to compare, there can be multiples of this switch
  -z, --include-zero-players   show games with unknown max players

Positional Arguments:
  <db>                         the GOG DB for a user, multiple can be listed
"""

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List

import docopt
from flask import Flask, render_template, request
import pytest
from ruamel.yaml import YAML

from helpers.cache_helper import Cache
from helpers.constants import ALPHANUM_PATTERN, IGDB_GAME_MODE
from helpers.gogdb_helper import gogDB
from helpers.igdb_helper import IGDBHelper
from version import VERSION

app = Flask(__name__)


@app.route("/")
def root():
    log.info("Request from {}".format(request.remote_addr))
    return render_template(
        "index.html",
        users=config["users"],
        platforms=["epic", "gog", "origin", "steam", "uplay", "xboxone"],
    )


@app.route("/compare", methods=["GET", "POST"])
def compare_libraries():
    log.info("Request from {}".format(request.remote_addr))

    opts = init_opts()

    # Check boxes get passed in as "on" if checked, or not at all if unchecked
    for k in request.args.keys():
        # Only user IDs are ints
        try:
            int(k)
            opts["user_ids_to_compare"].append(int(k))
        except ValueError:
            if k.startswith("exclude_platform_"):
                opts["exclude_platforms"].append(k.split("_")[-1])
            else:
                opts[k] = True

    # If no users were selected, just refresh the page
    if not opts["user_ids_to_compare"]:
        return root()

    gog = gogDB(config, opts)

    if request.args["option"] == "grid":
        gog.config["all_games"] = True
        template = "game_grid.html"
    else:
        template = "game_list.html"

    users = gog.get_usernames_from_ids(gog.config["user_ids_to_compare"])
    common_games = gog.get_common_games()
    set_max_players(common_games, cache.data)

    if not gog.config["all_games"]:
        common_games = gog.filter_games(common_games)

    for release_key in list(common_games.keys()):
        igdb.get_igdb_id(release_key)
        igdb.get_game_info(release_key)
        igdb.get_multiplayer_info(release_key)

    debug_str = ""
    return render_template(
        template,
        debug_str=debug_str,
        games=common_games,
        users=users,
        caption=gog.get_caption(len(common_games)),
        show_keys=opts["show_keys"],
    )


def init_opts():
    """Initializes the options to pass to the gogDB class. Since the
    config is only read once, we need to be able to reinit any options
    that can be passed from the web UI
    """

    return {
        "include_single_player": False,
        "include_zero_players": False,
        "exclusive": False,
        "show_keys": False,
        "user_ids_to_compare": [],
        "exclude_platforms": [],
    }


def build_config(args: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a config dict created from the config file and
    command-line arguments, with the latter taking precedence
    """
    if args.get("--config-file", None) is not None:
        yaml = YAML(typ="safe")
        with open(args["--config-file"], "r") as config_file:
            config = yaml.load(config_file)
    else:
        # We didn't get a config file, so populate from args
        config = {}

    # TODO: allow using both IDs and DBs (use one arg and detect if it's an int)
    # TODO: should be able to use unambiguous partial names
    if not args.get("<db>", []) and "users" not in config:
        raise ValueError("You must use -u, have users in the config file, or list DBs")

    # Command-line args override values in the config file
    # TODO: maybe we can do this directly in argparse, or otherwise better

    # This can't be given as an argument as it wouldn't make much sense;
    #  provide a sane default if it's missing from the config file
    if "db_path" not in config:
        config["db_path"] = "."

    config["all_games"] = args.get("--all-games", False)

    config["include_single_player"] = args.get("--include-single-player", False)

    if args.get("--server", True):  # Note that the --server opt is False unless present
        config["mode"] = "server"

    if args.get("--interface"):
        config["interface"] = args["--interface"]
    if "interface" not in config:
        config["interface"] = "0.0.0.0"

    if args.get("--port"):
        config["port"] = int(args["--port"])
    if "port" not in config:
        config["port"] = 8080

    # DBs and user IDs can be in the config file and/or passed in as args
    config["db_list"] = []
    if "users" not in config:
        config["users"] = {}

    for userid in config["users"]:
        config["db_list"].append(
            "{}/{}".format(config["db_path"], config["users"][userid]["db"])
        )

    for db in args.get("<db>", []):
        if os.path.abspath(db) not in config["db_list"]:
            config["db_list"].append(os.path.abspath(db))

    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    print(config["users"])
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

    for userid_str in args.get("--userid", []):
        userid = int(userid_str)
        if userid not in config["users"]:
            raise ValueError(
                "User ID {} isn't defined in the config file".format(userid)
            )
        elif "db" not in config["users"][userid]:
            raise ValueError(
                "User ID {} is missing the db key in the config file".format(userid)
            )
        elif (
            "{}/{}".format(config["db_path"], config["users"][userid]["db"])
            not in config["db_list"]
        ):
            config["db_list"].append(
                "{}/{}".format(config["db_path"], config["users"][userid]["db"])
            )

    if "hidden" not in config:
        config["hidden"] = []

    # Lowercase and remove non-alphanumeric characters for better matching
    for i in range(len(config["hidden"])):
        config["hidden"][i] = ALPHANUM_PATTERN.sub("", config["hidden"][i]).lower()

    sanitized_metadata = {}
    for title in config["metadata"]:
        sanitized_title = ALPHANUM_PATTERN.sub("", title).lower()
        sanitized_metadata[sanitized_title] = config["metadata"][title]

    config["metadata"] = sanitized_metadata

    return config


def OLD_build_config(args):
    """Returns a config dict created from the config file and
    command-line arguments, with the latter taking precedence
    """
    if args.version:
        print("{} version {}".format(os.path.basename(__file__), VERSION))
        sys.exit(0)

    if args.config_file:
        yaml = YAML(typ="safe")
        with open(args.config_file) as config_file:
            config = yaml.load(config_file)
    else:
        # We didn't get a config file, so populate from args
        config = {}

    # TODO: allow using both IDs and DBs (use one arg and detect if it's an int)
    # TODO: should be able to use unambiguous partial names
    if not args.db and "users" not in config:
        raise ValueError("You must use -u, have users in the config file, or list DBs")

    # Command-line args override values in the config file
    # TODO: maybe we can do this directly in argparse, or otherwise better

    # This can't be given as an argument as it wouldn't make much sense;
    #  provide a sane default if it's missing from the config file
    if "db_path" not in config:
        config["db_path"] = "."

    config["all_games"] = False
    if args.all_games:
        config["all_games"] = True

    config["include_single_player"] = False
    if args.include_single_player:
        config["include_single_player"] = True

    if args.server:
        config["mode"] = "server"

    if args.interface:
        config["interface"] = args.interface
    if "interface" not in config:
        config["interface"] = "0.0.0.0"

    if args.port:
        config["port"] = args.port
    if "port" not in config:
        config["port"] = 8080

    # DBs and user IDs can be in the config file and/or passed in as args
    config["db_list"] = []
    if "users" not in config:
        config["users"] = {}

    for userid in config["users"]:
        config["db_list"].append(
            "{}/{}".format(config["db_path"], config["users"][userid]["db"])
        )

    for db in args.db:
        if os.path.abspath(db) not in config["db_list"]:
            config["db_list"].append(os.path.abspath(db))

    if args.userid:
        for userid in args.userid:
            if userid not in config["users"]:
                raise ValueError(
                    "User ID {} isn't defined in the config file".format(userid)
                )
            elif "db" not in config["users"][userid]:
                raise ValueError(
                    "User ID {} is missing the db key in the config file".format(userid)
                )
            elif (
                "{}/{}".format(config["db_path"], config["users"][userid]["db"])
                not in config["db_list"]
            ):
                config["db_list"].append(
                    "{}/{}".format(config["db_path"], config["users"][userid]["db"])
                )

    if "hidden" not in config:
        config["hidden"] = []

    # Lowercase and remove non-alphanumeric characters for better matching
    for i in range(len(config["hidden"])):
        config["hidden"][i] = ALPHANUM_PATTERN.sub("", config["hidden"][i]).lower()

    sanitized_metadata = {}
    for title in config["metadata"]:
        sanitized_title = ALPHANUM_PATTERN.sub("", title).lower()
        sanitized_metadata[sanitized_title] = config["metadata"][title]

    config["metadata"] = sanitized_metadata

    return config


def set_max_players(game_list, cache):
    """Sets the max_players for each release key; precedence is:
    - max_players in the config yaml
    - max_players from IGDB
    - 1 if the above aren't available and the only game mode from IGDB is single player
    - 0 (unknown) otherwise
    """
    for k in game_list:
        max_players = 0

        if "max_players" in game_list[k]:
            log.debug(
                f'{k}: max players {game_list[k]["max_players"]} from config file'
            )
            continue

        if k not in cache["igdb"]["games"]:
            reason = "no IGDB info in cache, did you call get_igdb_id()?"
            log.warning(f"{k}: {reason}")

        elif "max_players" not in cache["igdb"]["games"][k]:
            reason = "IGDB max_players not found, did you call get_multiplayer_info()?"
            log.warning(f"{k}: {reason}")

        elif cache["igdb"]["games"][k]["max_players"] > 0:
            max_players = cache["igdb"]["games"][k]["max_players"]
            reason = "from IGDB cache"

        elif (
            "info" in cache["igdb"]["games"][k]
            and cache["igdb"]["games"][k]["info"]
            and "game_modes" in cache["igdb"]["games"][k]["info"][0]
            and (
                cache["igdb"]["games"][k]["info"][0]["game_modes"]
                == [IGDB_GAME_MODE["singleplayer"]]
            )
        ):
            max_players = 1
            reason = "as IGDB has single player as the only game mode"

        else:
            reason = "as we have no max player info"

        log.debug(f"{k}: max players {max_players} {reason}")
        game_list[k]["max_players"] = max_players


def parse_cmdline(argv: List[str]) -> Dict[str, object]:
    return docopt.docopt(__doc__, help=True, version=VERSION, options_first=True)


def OLD_parse_cmdline(argv: List[str]) -> Any:
    parser = argparse.ArgumentParser(description="Show games owned by multiple users.")
    parser.add_argument(
        "db", type=str, nargs="*", help="the GOG DB for a user; multiple can be listed"
    )
    parser.add_argument(
        "-a",
        "--all-games",
        action="store_true",
        help="list all games owned by the selected users (doesn't include single player unless -I is used)",
    )
    parser.add_argument("-c", "--config-file", type=str, help="the config file to use")
    parser.add_argument("-d", "--debug", action="store_true", help="debug output")
    parser.add_argument(
        "-i",
        "--interface",
        type=str,
        help="the network interface to use if running in server mode; defaults to 0.0.0.0",
    )
    parser.add_argument(
        "-I",
        "--include-single-player",
        action="store_true",
        help="Include single player games",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        help="the network port to use if running in server mode; defaults to 8080",
    )
    parser.add_argument(
        "-s", "--server", action="store_true", help="run in server mode"
    )
    parser.add_argument(
        "-u", "--userid", type=int, nargs="*", help="the GOG user IDs to compare"
    )
    parser.add_argument(
        "-v", "--version", action="store_true", help="print version and exit"
    )
    parser.add_argument(
        "-z",
        "--include-zero-players",
        action="store_true",
        help="Show games with unknown max players",
    )

    return parser.parse_args(argv)


## Test for command line switches affecting the config.
#
# Currently, these are the values you can affect via the command line:
#
# mode: client | server # default is client, use -s
# interface: (valid interface address) # default is 0.0.0.0, use -i
# port: (valid port) # default is 8080, use -p
# include_single_player: True | False # use -I
@pytest.mark.parametrize(
    "description,commandline,config_fields,expected_values",
    [
        # [
        #     "No switches",  # Description, should this test pass fail.
        #     [
        #         "./gamatrix-gog.py",  # standard, just left here to simulate actual command line argv list...
        #         "--config-file",  # use long switch names, more descriptive this way
        #         "./config-sample.yaml",  # use the sample yaml as a test data source
        #     ],
        #     [
        #         "mode",  # names of the top-level field in the config file, in this case mode
        #         "interface",
        #         "port",
        #         "include_single_player",
        #         "all_games",
        #     ],
        #     [
        #         "server",  # values that are expected, this list is arranged to coincide with fields in the same order as the list above
        #         "0.0.0.0",
        #         8080,
        #         False,
        #         False,
        #     ],
        # ],
        # [
        #     "Assorted values all in one",
        #     [
        #         "./gamatrix-gog.py",  # just here to simulate actual command line argv list...
        #         "--config-file",
        #         "./config-sample.yaml",
        #         "--server",
        #         "--interface",
        #         "1.2.3.4",
        #         "--port",
        #         "62500",
        #         "--include-single-player",
        #         "--all-games",
        #     ],
        #     ["mode", "interface", "port", "include_single_player", "all_games"],
        #     [
        #         "server",
        #         "1.2.3.4",
        #         62500,
        #         True,
        #         True,
        #     ],
        # ],
        [
            "Only set the mode to server",
            [
                "./gamatrix-gog.py",
                "--config-file",
                "./config-sample.yaml",
                "--server",
            ],
            ["mode"],
            ["server"],
        ],
    ],
)
def test_cmdline_handling(
    description: str,
    commandline: List[str],
    config_fields: List[str],
    expected_values: List[Any],
):
    """Parse the command line and build the config file, checking for problems."""
    args = OLD_parse_cmdline(commandline)
    config = OLD_build_config(args)
    for i in range(len(config_fields)):
        assert (
            config[config_fields[i]] == expected_values[i]
        ), f"Failure for pass: '{description}'"

    args2 = parse_cmdline(commandline)
    config2 = build_config(args2)
    for i2 in range(len(config_fields)):
        assert (
            config2[config_fields[i2]] == expected_values[i2]
        ), f"Failure for pass: '{description}'"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger()

    print("=========================================")
    print(sys.argv)
    print("=========================================")

    args = OLD_parse_cmdline(sys.argv[1:])
    print("OLD DONE")
    opts = parse_cmdline(sys.argv)
    print("NEW DONE")

    print("+OLD COMMANDLINE+++++++++++++++++++++++++")
    print(args)

    print("/NEW COMMANDLINE/////////////////////////")
    print(opts)

    OLD_config = OLD_build_config(args)
    config = build_config(opts)

    with open("old_config.json", "w") as of_:
        of_.write(json.dumps(OLD_config))

    with open("new_config.json", "w") as nf_:
        nf_.write(json.dumps(config))

    exit()

    if args.debug:
        log.setLevel(logging.DEBUG)

    try:
        config = build_config(args)
        log.debug(f"config = {config}")
    except ValueError as e:
        print(e)
        sys.exit(1)

    cache = Cache(config["cache"])
    # Get multiplayer info from IGDB and save it to the cache
    igdb = IGDBHelper(
        config["igdb_client_id"], config["igdb_client_secret"], cache.data
    )

    if "mode" in config and config["mode"] == "server":
        # Start Flask to run in server mode until killed
        app.run(host=config["interface"], port=config["port"])
        sys.exit(0)

    if args.userid is None:
        user_ids_to_compare = [u for u in config["users"].keys()]
    else:
        user_ids_to_compare = args.userid

    # init_opts() is meant for server mode; any CLI options that are also
    # web UI options need to be overridden
    opts = init_opts()
    opts["include_single_player"] = args.include_single_player
    opts["include_zero_players"] = args.include_zero_players
    opts["user_ids_to_compare"] = user_ids_to_compare

    gog = gogDB(config, opts)
    common_games = gog.get_common_games()
    set_max_players(common_games, cache.data)

    if not config["all_games"]:
        common_games = gog.filter_games(common_games)

    # TODO: handle not getting an access token
    for release_key in list(common_games.keys()):
        igdb.get_igdb_id(release_key)
        igdb.get_game_info(release_key)
        igdb.get_multiplayer_info(release_key)

    cache.save()

    for key in common_games:
        print(
            "{} ({})".format(
                common_games[key]["title"],
                ", ".join(common_games[key]["platforms"]),
            ),
            end="",
        )
        if "max_players" in common_games[key]:
            print(" Players: {}".format(common_games[key]["max_players"]), end="")
        if "comment" in common_games[key]:
            print(" Comment: {}".format(common_games[key]["comment"]), end="")
        print("")

    print(gog.get_caption(len(common_games)))


## NOTES:
# Setting `--debug` on the command line doesn't affect config["debug"], should it?
# Adding <db> files at the end of the command line causes errors in the old mechanism (it works in the new docopt but since it didn't work before I think we might want to scrap it?)
# Command line arg `--include-zero-players` doesn't seem to get used anywhere, nor affect the config?
#
## Things that we might want to affect via the command line but currently do not:
#
# db_path: C:\Users\derek\Documents\Dev\github\derek-keeler\gamatrix-gog-dbs
# cache: C:\Users\derek\Documents\Dev\github\derek-keeler\gamatrix-gog\my-cache-file
# log_level: info
# igdb_client_secret: wqeogozgq6pmq3cuxzbsm0he8eieng
# igdb_client_id: l5mrkvb1af96pjnsdhr76z69ty9amp
