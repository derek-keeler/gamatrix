-- Active: 1687659935883@@127.0.0.1@3306

-- Modes that the Gamatrix application provides.
CREATE TABLE gamatrix_modes(
    mode_id TEXT NOT NULL PRIMARY KEY,
    mode_name TEXT NOT NULL UNIQUE
);

INSERT INTO gamatrix_modes (mode_id, mode_name) VALUES ('grid', 'Game Grid');
INSERT INTO gamatrix_modes (mode_id, mode_name) VALUES ('upload_db', 'Upload DB');
INSERT INTO gamatrix_modes (mode_id, mode_name) VALUES ('list', 'Game List');

-- Users that are being compared in the Gamatrix application.
CREATE TABLE users_list(
    user_id TEXT NOT NULL PRIMARY KEY,
    user_icon TEXT NULL,
    real_name TEXT NULL
);



-- Gaming platforms (stores/services) that Gamatrix can use to compare between user's owned games with.
CREATE TABLE gaming_platforms(
    platform_id TEXT NOT NULL PRIMARY KEY,
    platform_name TEXT NOT NULL UNIQUE,
    icon TEXT NULL
);

INSERT INTO gaming_platforms (platform_id, platform_name) VALUES ('steam', 'Steam', 'static/steam.png');
INSERT INTO gaming_platforms (platform_id, platform_name) VALUES ('uplay', 'Uplay', 'static/uplay.png');
INSERT INTO gaming_platforms (platform_id, platform_name) VALUES ('epic', 'Epic Games', 'static/epic.png');
INSERT INTO gaming_platforms (platform_id, platform_name) VALUES ('battle_net', 'Battle.net', 'static/battlenet.png');
INSERT INTO gaming_platforms (platform_id, platform_name) VALUES ('gog', 'GOG', 'static/gog.png');
INSERT INTO gaming_platforms (platform_id, platform_name) VALUES ('bethesda', 'Bethesda.net', 'static/bethesda.png');
INSERT INTO gaming_platforms (platform_id, platform_name) VALUES ('ea', 'Origin', 'static/origin.png');
INSERT INTO gaming_platforms (platform_id, platform_name) VALUES ('xbox', 'Xbox', 'static/xboxone.png');

-- Options that apply to the Gamatrix application. Some options apply to all 
-- modes, most only to some (or one).
CREATE TABLE app_options(
    mode TEXT NOT NULL PRIMARY KEY,
    option_id TEXT NOT NULL,
    option_name TEXT NOT NULL
);

INSERT INTO app_options (mode, option_id, option_name) VALUES ('grid', 'exclusive', 'Exclusively Owned');
INSERT INTO app_options (mode, option_id, option_name) VALUES ('grid', 'installed', 'Installed Only');
INSERT INTO app_options (mode, option_id, option_name) VALUES ('grid', 'include1p', 'Include single-player');
INSERT INTO app_options (mode, option_id, option_name) VALUES ('grid', 'show_prod_key', 'Show product keys');
INSERT INTO app_options (mode, option_id, option_name) VALUES ('grid', 'pick', 'Pick a random game');

