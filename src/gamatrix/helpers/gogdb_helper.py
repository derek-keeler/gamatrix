import copy
import json
import logging
import os
import sqlite3
from functools import cmp_to_key

from gamatrix.helpers.misc_helper import get_slug_from_title
from gamatrix.helpers.database import Database, is_sqlite3

from gamatrix.helpers.constants import PLATFORMS


def is_sqlite3(stream: bytearray) -> bool:
    """Returns True if stream contains an SQLite3 DB header"""
    # https://www.sqlite.org/fileformat.html
    return len(stream) >= 16 and stream[:16] == b"SQLite format 3\000"


class gogDB:
    def __init__(
        self,
        config,
        opts,
    ):
        self.db = Database(config, opts)
        self.log = logging.getLogger(__name__)

    def use_db(self, db):
        self.db.use_db(db)

    def close_connection(self):
        self.db.close_connection()

    def get_user(self):
        return self.db.get_user()

    def get_gamepiecetype_id(self, name):
        return self.db.get_gamepiecetype_id(name)

    def get_owned_games(self):
        return self.db.get_owned_games()

    def get_igdb_release_key(self, gamepiecetype_id, release_key):
        return self.db.get_igdb_release_key(gamepiecetype_id, release_key)

    def get_installed_games(self):
        return self.db.get_installed_games()

    def get_common_games(self):
        game_list = {}
        self.owners_to_match = []

        # Loop through all the DBs and get info on all owned titles
        for db_file in self.db.config["db_list"]:
            self.log.debug("Using DB {}".format(db_file))
            self.use_db(db_file)
            userid = self.get_user()[0]
            self.owners_to_match.append(userid)
            self.gamepiecetype_id = self.get_gamepiecetype_id("allGameReleases")
            owned_games = self.get_owned_games()
            installed_games = self.get_installed_games()
            self.log.debug("owned games = {}".format(owned_games))
            # A row looks like (release_keys {"title": "Title Name"})
            for release_keys, title_json in owned_games:
                # If a game is owned on multiple platforms, the release keys will be comma-separated
                for release_key in release_keys.split(","):
                    release_key = release_key.strip()
                    if release_key in self.db.config["user_ids_to_exclude"]:
                        self.log.debug(
                            "Skipping {} as it's in user_ids_to_exclude".format(
                                release_key
                            )
                        )
                        continue

                    # If we've seen this game before, just add this user to the list of owners
                    if release_key in game_list:
                        self.log.debug("User {} owns {}".format(userid, release_key))
                        game_list[release_key]["owners"].append(userid)
                        if release_key in installed_games:
                            game_list[release_key]["installed"].append(userid)
                        continue

                    # We haven't seen this game before, so we need to get its metadata
                    title = json.loads(title_json)["title"]
                    slug = get_slug_from_title(title)
                    self.log.debug(
                        "First time seeing {} (slug: {})".format(title, slug)
                    )

                    # Skip hidden games
                    if slug in self.db.config["hidden"]:
                        self.log.debug(
                            "Skipping {} as it's in the hidden list".format(title)
                        )
                        continue

                    # Get the platform from the release key
                    platform = release_key.split("_")[0]
                    if platform not in PLATFORMS:
                        self.log.warning(
                            "Unknown platform {} for {}".format(platform, title)
                        )
                        platform = "unknown"

                    # Get the IGDB key for this game
                    igdb_key = self.get_igdb_release_key(
                        self.gamepiecetype_id, release_key
                    )
                    self.log.debug(
                        "{}: using {} for IGDB".format(release_key, igdb_key)
                    )

                    # Add metadata from the config file if we have any
                    if slug in self.db.config["metadata"]:
                        for k in self.db.config["metadata"][slug]:
                            self.log.debug(
                                "Adding metadata {} to title {}".format(k, title)
                            )
                            game_list[release_key][k] = self.db.config["metadata"][
                                slug
                            ][k]

                    self.log.debug("User {} owns {}".format(userid, release_key))
                    game_list[release_key]["owners"].append(userid)
                    game_list[release_key]["platforms"] = [platform]
                    if release_key in installed_games:
                        game_list[release_key]["installed"].append(userid)

            self.close_connection()

        # Sort by slug to avoid headaches in the templates;
        # dicts maintain insertion order as of Python 3.7
        ordered_game_list = {
            k: v for k, v in sorted(game_list.items(), key=cmp_to_key(self._sort))
        }

        # Sort the owner lists so we can compare them easily
        for k in ordered_game_list:
            ordered_game_list[k]["owners"].sort()

        self.owners_to_match.sort()
        self.log.debug("owners_to_match: {}".format(self.owners_to_match))

        return ordered_game_list

    def filter_games(self, game_list, all_games=False):
        """
        Removes games that don't fit the search criteria. Note that
        we will not filter a game we have no multiplayer info on
        """
        working_game_list = copy.deepcopy(game_list)

        for k in game_list:
            # Remove single-player games if we didn't ask for them
            if (
                not self.db.config["include_single_player"]
                and not game_list[k]["multiplayer"]
            ):
                self.log.debug(f"{k}: Removing as it is single player")
                del working_game_list[k]
                continue

            # If all games was chosen, we don't want to filter anything else
            if all_games:
                continue

            # Delete any entries that aren't owned by all users we want
            for owner in self.db.config["user_ids_to_compare"]:
                if owner not in game_list[k]["owners"]:
                    self.log.debug(
                        f'Deleting {game_list[k]["title"]} as owners {game_list[k]["owners"]} does not include {owner}'
                    )
                    del working_game_list[k]
                    break
                elif (
                    self.db.config["installed_only"]
                    and owner not in game_list[k]["installed"]
                ):
                    self.log.debug(
                        f'Deleting {game_list[k]["title"]} as it\'s not installed by {owner}'
                    )
                    del working_game_list[k]
                    break

        return working_game_list

    def get_caption(self, num_games, random=False):
        """Returns the caption string"""

        if random:
            caption_start = f"Random game selected from {num_games}"
        else:
            caption_start = num_games

        if self.db.config["all_games"]:
            caption_middle = "total games owned by"
        elif len(self.db.config["user_ids_to_compare"]) == 1:
            caption_middle = "games owned by"
        else:
            caption_middle = "games in common between"

        usernames_excluded = ""
        if self.db.config["user_ids_to_exclude"] and not self.db.config["all_games"]:
            usernames = [
                self.db.config["users"][userid]["username"]
                for userid in self.db.config["user_ids_to_exclude"]
            ]
            usernames_excluded = f' and not owned by {", ".join(usernames)}'

        platforms_excluded = ""
        if self.db.config["exclude_platforms"]:
            platforms_excluded = " ({} excluded)".format(
                ", ".join(self.db.config["exclude_platforms"]).title()
            )

        self.log.debug("platforms_excluded = {}".format(platforms_excluded))

        installed = ""
        if self.db.config["installed_only"] and not self.db.config["all_games"]:
            installed = " (installed only)"

        usernames = []
        for userid in self.db.config["user_ids_to_compare"]:
            usernames.append(self.db.config["users"][userid]["username"])

        return "{} {} {}{}{}{}".format(
            caption_start,
            caption_middle,
            ", ".join(usernames),
            usernames_excluded,
            platforms_excluded,
            installed,
        )

    def _sort(self, a, b):
        """Sort by slug"""
        a_slug = get_slug_from_title(a[1]["title"])
        b_slug = get_slug_from_title(b[1]["title"])
        if a_slug < b_slug:
            return -1
        elif a_slug > b_slug:
            return 1
        return 0
