import copy
import json
import logging
import os
import sqlite3
from functools import cmp_to_key

from gamatrix.helpers.misc_helper import get_slug_from_title
from gamatrix.helpers.constants import PLATFORMS


def is_sqlite3(stream: bytearray) -> bool:
    """Returns True if stream contains an SQLite3 DB header"""
    # https://www.sqlite.org/fileformat.html
    return len(stream) >= 16 and stream[:16] == b"SQLite format 3\000"


class Database:
    def __init__(self, config, opts):
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

        self.log = logging.getLogger(__name__)
        self.log.debug("db_list = {}".format(self.config["db_list"]))

    def use_db(self, db):
        """Connect to the specified database file"""
        if not os.path.exists(db):
            raise FileNotFoundError(f"DB {db} doesn't exist")

        self.db = db
        self.conn = sqlite3.connect(db)
        self.cursor = self.conn.cursor()

    def close_connection(self):
        """Close the database connection"""
        self.conn.close()

    def get_user(self):
        """Get the first user from the Users table"""
        user_query = self.cursor.execute("select * from Users")
        if user_query.rowcount == 0:
            raise ValueError("No users found in the Users table in the DB")

        user = self.cursor.fetchall()[0]

        if user_query.rowcount > 1:
            self.log.warning(
                "Found multiple users in the DB; using the first one ({})".format(user)
            )

        return user

    def get_gamepiecetype_id(self, name):
        """Returns the numeric ID for the specified type"""
        return self.cursor.execute(
            'SELECT id FROM GamePieceTypes WHERE type="{}"'.format(name)
        ).fetchone()[0]

    def get_owned_games(self):
        """Returns a list of release keys owned per the current DB"""
        owned_game_database = """CREATE TEMP VIEW MasterList AS
            SELECT GamePieces.releaseKey, GamePieces.gamePieceTypeId, GamePieces.value FROM ProductPurchaseDates
            JOIN GamePieces ON ProductPurchaseDates.gameReleaseKey = GamePieces.releaseKey;"""
        og_fields = [
            """CREATE TEMP VIEW MasterDB AS SELECT DISTINCT(MasterList.releaseKey) AS releaseKey, MasterList.value AS title, PLATFORMS.value AS platformList"""
        ]
        og_references = [""" FROM MasterList, MasterList AS PLATFORMS"""]
        og_conditions = [
            """ WHERE ((MasterList.gamePieceTypeId={}) OR (MasterList.gamePieceTypeId={})) AND ((PLATFORMS.releaseKey=MasterList.releaseKey) AND (PLATFORMS.gamePieceTypeId={}))""".format(
                self.get_gamepiecetype_id("originalTitle"),
                self.get_gamepiecetype_id("title"),
                self.get_gamepiecetype_id("allGameReleases"),
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
            self.log.debug("Running query: {}".format(query))
            self.cursor.execute(query)

        return self.cursor.fetchall()

    def get_igdb_release_key(self, gamepiecetype_id, release_key):
        """
        Returns the release key to look up in IGDB. Steam keys are the
        most reliable to look up; GOG keys are about 50% reliable;
        other platforms will never work. So, our order of preference is:
          - Steam
          - GOG
          - release_key
        """
        query = f'SELECT * FROM GamePieces WHERE releaseKey="{release_key}" and gamePieceTypeId = {gamepiecetype_id}'
        self.log.debug("Running query: {}".format(query))
        self.cursor.execute(query)

        raw_result = self.cursor.fetchall()
        self.log.debug(f"raw_result = {raw_result}")
        result = json.loads(raw_result[0][3])
        self.log.debug(f"{release_key}: all release keys: {result}")
        if "releases" not in result:
            self.log.debug(
                f'{release_key}: "releases" not found in result for release keys'
            )
            return release_key

        for k in result["releases"]:
            # Sometimes there's a steam_1234 and steam_steam_1234, but always in that order
            if k.startswith("steam_") and not k.startswith("steam_steam_"):
                return k

        # If we found no Steam key, look for a GOG key
        for k in result["releases"]:
            if k.startswith("gog_"):
                return k

        # If we found neither Steam nor GOG keys, just return the key we were given
        return release_key

    def get_installed_games(self):
        """Returns a list of release keys installed per the current DB"""
        # https://www.reddit.com/r/gog/comments/ek3vtz/dev_gog_galaxy_20_get_list_of_gameid_of_installed/
        query = """SELECT trim(GamePieces.releaseKey) FROM GamePieces
            JOIN GamePieceTypes ON GamePieces.gamePieceTypeId = GamePieceTypes.id
            WHERE releaseKey IN
            (SELECT platforms.name || '_' || InstalledExternalProducts.productId
            FROM InstalledExternalProducts
            JOIN Platforms ON InstalledExternalProducts.platformId = Platforms.id
            UNION
            SELECT 'gog_' || productId FROM InstalledProducts)
            AND GamePieceTypes.type = 'originalTitle'"""

        self.log.debug(f"Running query: {query}")
        self.cursor.execute(query)
        installed_games = []
        # Release keys are each in their own list. Should only be one element per
        # list, but let's not assume that. Put all results into a single list
        for result in self.cursor.fetchall():
            for r in result:
                installed_games.append(r)

        return installed_games 