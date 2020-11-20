#!/usr/bin/env python3
import argparse
import copy
import json
import logging
import os
import re
import sqlite3
import sys
from flask import Flask, request, render_template
from ruamel.yaml import YAML
from version import VERSION

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
alphanum_pattern = re.compile("[^\s\w]+")

app = Flask(__name__)


@app.route("/")
def root():
    logger.info("Request from {}".format(request.remote_addr))
    return render_template(
        "index.html",
        users=config["users"],
        platforms=["epic", "gog", "origin", "steam", "uplay", "xboxone"],
    )


@app.route("/compare", methods=["GET", "POST"])
def compare_libraries():
    logger.info("Request from {}".format(request.remote_addr))

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
    debug_str = ""
    return render_template(
        template,
        debug_str=debug_str,
        games=common_games,
        users=users,
        caption=gog.get_caption(len(common_games)),
        show_keys=opts["show_keys"],
    )


class gogDB:
    def __init__(
        self,
        config,
        opts,
    ):
        # Server mode only reads the config once, so we don't want to modify it
        self.config = copy.deepcopy(config)
        for k in opts:
            self.config[k] = opts[k]
        self.config["user_ids_to_exclude"] = []

        # All DBs defined in the config file will be in db_list. Remove the DBs for
        # users that we don't want to compare, unless exclusive was specified, in
        # which case we need to look at all DBs
        for user in list(self.config["users"]):
            if user not in self.config["user_ids_to_compare"]:
                if self.config["exclusive"]:
                    self.config["user_ids_to_exclude"].append(user)
                elif (
                    "db" in self.config["users"][user]
                    and "{}/{}".format(
                        self.config["db_path"], self.config["users"][user]["db"]
                    )
                    in self.config["db_list"]
                ):
                    self.config["db_list"].remove(
                        "{}/{}".format(
                            self.config["db_path"], self.config["users"][user]["db"]
                        )
                    )

        if config["log_level"].lower() == "debug":
            level = logging.DEBUG
        else:
            level = logging.INFO

        self.logger = logging.getLogger("gogDB")
        self.logger.setLevel(level)
        self.logger.debug("db_list = {}".format(self.config["db_list"]))

    def use_db(self, db):
        if not os.path.exists(db):
            raise FileNotFoundError("DB {} doesn't exist".format(db))

        self.db = db
        self.conn = sqlite3.connect(db)
        self.cursor = self.conn.cursor()

    def close_connection(self):
        self.conn.close()

    def get_user(self):
        user_query = self.cursor.execute("select * from Users")
        if user_query.rowcount == 0:
            raise ValueError("No users found in the Users table in the DB")

        user = self.cursor.fetchall()[0]

        if user_query.rowcount > 1:
            self.logger.warning(
                "Found multiple users in the DB; using the first one ({})".format(user)
            )

        return user

    def id(self, name):
        """ Returns the numeric ID for the specified type """
        return self.cursor.execute(
            'SELECT id FROM GamePieceTypes WHERE type="{}"'.format(name)
        ).fetchone()[0]

    # Taken from https://github.com/AB1908/GOG-Galaxy-Export-Script/blob/master/galaxy_library_export.py
    def get_owned_games(self, userid):
        owned_game_database = """CREATE TEMP VIEW MasterList AS
            SELECT GamePieces.releaseKey, GamePieces.gamePieceTypeId, GamePieces.value FROM GameLinks
            JOIN GamePieces ON GameLinks.releaseKey = GamePieces.releaseKey;"""
        og_fields = [
            """CREATE TEMP VIEW MasterDB AS SELECT DISTINCT(MasterList.releaseKey) AS releaseKey, MasterList.value AS title, PLATFORMS.value AS platformList"""
        ]
        og_references = [""" FROM MasterList, MasterList AS PLATFORMS"""]
        og_conditions = [
            """ WHERE ((MasterList.gamePieceTypeId={}) OR (MasterList.gamePieceTypeId={})) AND ((PLATFORMS.releaseKey=MasterList.releaseKey) AND (PLATFORMS.gamePieceTypeId={}))""".format(
                self.id("originalTitle"), self.id("title"), self.id("allGameReleases")
            )
        ]
        og_order = """ ORDER BY title;"""
        og_resultFields = [
            "GROUP_CONCAT(DISTINCT MasterDB.releaseKey)",
            "MasterDB.title",
        ]
        og_resultGroupBy = ["MasterDB.platformList"]
        og_query = "".join(og_fields + og_references + og_conditions) + og_order

        # Display each game and its details along with corresponding release key grouped by releasesList
        unique_game_data = (
            """SELECT {} FROM MasterDB GROUP BY {} ORDER BY MasterDB.title;""".format(
                ", ".join(og_resultFields), ", ".join(og_resultGroupBy)
            )
        )

        for query in [owned_game_database, og_query, unique_game_data]:
            self.logger.debug("Running query: {}".format(query))
            self.cursor.execute(query)

        return self.cursor.fetchall()

    def get_common_games(self):
        game_list = {}
        self.owners_to_match = []

        # Loop through all the DBs and get info on all owned titles
        for db_file in self.config["db_list"]:
            self.logger.debug("Using DB {}".format(db_file))
            self.use_db(db_file)
            userid = self.get_user()[0]
            self.owners_to_match.append(userid)
            owned_games = self.get_owned_games(userid)
            self.logger.debug("owned games = {}".format(owned_games))
            # A row looks like (release_keys {"title": "Title Name"})
            for release_keys, title_json in owned_games:
                # If a game is owned on multiple platforms, the release keys will be comma-separated
                for release_key in release_keys.split(","):
                    if release_key not in game_list:
                        # Skip this key if it's for a platform we don't want
                        if (
                            release_key.split("_")[0]
                            in self.config["exclude_platforms"]
                        ):
                            continue

                        # This is the first we've seen this title, so add it
                        title = json.loads(title_json)["title"]
                        sanitized_title = alphanum_pattern.sub("", title).lower()
                        # Skip this title if it's hidden or single player and we didn't ask for them
                        if sanitized_title in self.config["hidden"] or (
                            not self.config["include_single_player"]
                            and sanitized_title not in self.config["multiplayer"]
                        ):
                            continue

                        game_list[release_key] = {
                            "title": title,
                            "sanitized_title": sanitized_title,
                            "owners": [],
                        }

                        # Add metadata from the config file if we have any
                        if sanitized_title in self.config["metadata"]:
                            for k in self.config["metadata"][sanitized_title]:
                                self.logger.debug(
                                    "Adding metadata {} to title {}".format(k, title)
                                )
                                game_list[release_key][k] = self.config["metadata"][
                                    sanitized_title
                                ][k]
                        # Set max players to 1 for single player games
                        elif sanitized_title not in self.config["multiplayer"]:
                            game_list[release_key]["max_players"] = 1

                    self.logger.debug("User {} owns {}".format(userid, release_key))
                    game_list[release_key]["owners"].append(userid)
                    # Release keys start with the platform
                    game_list[release_key]["platforms"] = [release_key.split("_")[0]]

            self.close_connection()

        # Sort by sanitized title to avoid headaches in the templates;
        # dicts maintain insertion order as of Python 3.7
        ordered_game_list = {
            k: v
            for k, v in sorted(
                game_list.items(), key=lambda item: item[1]["sanitized_title"]
            )
        }

        # Sort the owner lists so we can compare them easily
        for k in ordered_game_list:
            ordered_game_list[k]["owners"].sort()

        self.owners_to_match.sort()
        self.logger.debug("owners_to_match: {}".format(self.owners_to_match))

        deduped_game_list = self.merge_duplicate_titles(ordered_game_list)

        if self.config["all_games"]:
            return deduped_game_list

        return self.filter_games(deduped_game_list)

    def merge_duplicate_titles(self, game_list):
        working_game_list = copy.deepcopy(game_list)
        # Merge entries that have the same title and platforms
        keys = list(game_list)
        for k in keys:
            # Skip if we deleted this earlier, or we're at the end of the dict
            if k not in working_game_list or keys.index(k) >= len(keys) - 2:
                continue

            sanitized_title = game_list[k]["sanitized_title"]
            owners = game_list[k]["owners"]
            platforms = game_list[k]["platforms"]

            # Go through any subsequent keys with the same (sanitized) title
            next_key = keys[keys.index(k) + 1]
            while game_list[next_key]["sanitized_title"] == sanitized_title:
                self.logger.debug(
                    "Found duplicate title {} (sanitized: {}), keys {}, {}".format(
                        game_list[k]["title"], sanitized_title, k, next_key
                    )
                )
                if game_list[next_key]["owners"] == owners:
                    self.logger.debug(
                        "{}: owners are the same: {}, {}".format(
                            next_key, owners, game_list[next_key]["owners"]
                        )
                    )
                    platform = game_list[next_key]["platforms"][0]
                    if platform not in platforms:
                        self.logger.debug(
                            "{}: adding new platform {} to {}".format(
                                next_key, platform, platforms
                            )
                        )
                        platforms.append(platform)
                    else:
                        self.logger.debug(
                            "{}: platform {} already in {}".format(
                                next_key, platform, platforms
                            )
                        )

                    self.logger.debug(
                        "{}: deleting duplicate {} as it has been merged into {}".format(
                            next_key, game_list[next_key], game_list[k]
                        )
                    )
                    del working_game_list[next_key]
                    working_game_list[k]["platforms"] = sorted(platforms)
                else:
                    self.logger.debug(
                        "{}: owners are different: {} {}".format(
                            next_key, owners, game_list[next_key]["owners"]
                        )
                    )

                if keys.index(next_key) >= len(keys) - 2:
                    break

                next_key = keys[keys.index(next_key) + 1]

        return working_game_list

    def filter_games(self, game_list):
        working_game_list = copy.deepcopy(game_list)

        for k in game_list:
            # Delete any entries that aren't owned by all users we want
            for owner in self.config["user_ids_to_compare"]:
                if owner not in game_list[k]["owners"]:
                    self.logger.debug(
                        "Deleting {} as owners {} does not include {}".format(
                            game_list[k]["title"],
                            game_list[k]["owners"],
                            owner,
                        )
                    )
                    del working_game_list[k]
                    break
            # This only executes if the for loop didn't break
            else:
                for owner in self.config["user_ids_to_exclude"]:
                    if owner in game_list[k]["owners"]:
                        self.logger.debug(
                            "Deleting {} as owners {} includes {} and exclusive is true".format(
                                game_list[k]["title"],
                                game_list[k]["owners"],
                                owner,
                            )
                        )
                        del working_game_list[k]
                        break

        return working_game_list

    def get_caption(self, num_games):
        """Returns the caption string"""
        usernames = self.get_usernames_from_ids(self.config["user_ids_to_compare"])

        if self.config["all_games"]:
            caption_middle = "total games owned by"
        elif len(usernames) == 1:
            caption_middle = "games owned by"
        else:
            caption_middle = "games in common between"

        userids_excluded = ""
        if self.config["user_ids_to_exclude"]:
            usernames_to_exclude = self.get_usernames_from_ids(
                self.config["user_ids_to_exclude"]
            )
            userids_excluded = " and not owned by {}".format(
                ", ".join(usernames_to_exclude.values())
            )

        platforms_excluded = ""
        if self.config["exclude_platforms"]:
            platforms_excluded = " ({} excluded)".format(
                ", ".join(self.config["exclude_platforms"]).title()
            )

        self.logger.debug("platforms_excluded = {}".format(platforms_excluded))

        return "{} {} {}{}{}".format(
            num_games,
            caption_middle,
            ", ".join(usernames.values()),
            userids_excluded,
            platforms_excluded,
        )

    def get_usernames_from_ids(self, userids):
        """Returns a dict of usernames mapped by user ID"""
        usernames = {}
        sorted_usernames = {}

        for userid in userids:
            if "username" in self.config["users"][userid]:
                usernames[userid] = self.config["users"][userid]["username"]
            else:
                usernames[userid] = str(userid)

        # Order by value (username) to avoid having to do it in the templates
        sorted_usernames = {
            k: v for k, v in sorted(usernames.items(), key=lambda item: item[1].lower())
        }

        return sorted_usernames


def init_opts():
    """Initializes the options to pass to the gogDB class"""
    return {
        "include_single_player": False,
        "exclusive": False,
        "show_keys": False,
        "user_ids_to_compare": [],
        "exclude_platforms": [],
    }


def build_config(args):
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

    if args.all_games:
        config["all_games"] = True
    else:
        config["all_games"] = False

    if args.debug:
        config["log_level"] = "debug"
    elif "log_level" not in config:
        config["log_level"] = "info"

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

    if "multiplayer" not in config:
        config["multiplayer"] = []
    if "hidden" not in config:
        config["hidden"] = []

    # Lowercase and remove non-alphanumeric characters for better matching
    for k in ["multiplayer", "hidden"]:
        for i in range(len(config[k])):
            config[k][i] = alphanum_pattern.sub("", config[k][i]).lower()

    sanitized_metadata = {}
    for title in config["metadata"]:
        sanitized_title = alphanum_pattern.sub("", title).lower()
        sanitized_metadata[sanitized_title] = config["metadata"][title]

    config["metadata"] = sanitized_metadata

    return config


if __name__ == "__main__":
    print(str(sys.argv))

    parser = argparse.ArgumentParser(description="Show games owned by multiple users.")
    parser.add_argument(
        "db", type=str, nargs="*", help="the GOG DB for a user; multiple can be listed"
    )
    parser.add_argument(
        "-a",
        "--all-games",
        action="store_true",
        help="list all games owned by the selected users",
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

    args = parser.parse_args()
    try:
        config = build_config(args)
    except ValueError as e:
        print(e)
        sys.exit(1)

    if "mode" in config and config["mode"] == "server":
        # Start Flask to run in server mode until killed
        app.run(host=config["interface"], port=config["port"])
        sys.exit(0)

    if args.userid is None:
        user_ids_to_compare = [u for u in config["users"].keys()]
    else:
        user_ids_to_compare = args.userid

    opts = init_opts()
    opts["user_ids_to_compare"] = user_ids_to_compare
    gog = gogDB(config, opts)
    games_in_common = gog.get_common_games()

    for key in games_in_common:
        print(
            "{} ({})".format(
                games_in_common[key]["title"],
                ", ".join(games_in_common[key]["platforms"]),
            ),
            end="",
        )
        if "max_players" in games_in_common[key]:
            print(" Players: {}".format(games_in_common[key]["max_players"]), end="")
        if "comment" in games_in_common[key]:
            print(" Comment: {}".format(games_in_common[key]["comment"]), end="")
        print("")

    print(gog.get_caption(len(games_in_common)))
