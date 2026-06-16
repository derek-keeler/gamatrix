# ARCHITECTURE

## High-level overview

Gamatrix ingests game ownership/install data from one or more local GOG Galaxy SQLite databases, enriches game records with IGDB metadata, then renders results either via CLI output or Flask web templates.

Primary runtime modules:
- `src/gamatrix/__main__.py` (application entrypoint and orchestration)
- `src/gamatrix/helpers/gogdb_helper.py` (SQLite extraction and game list shaping)
- `src/gamatrix/helpers/igdb_helper.py` (IGDB API integration and enrichment)
- `src/gamatrix/helpers/cache_helper.py` (JSON cache persistence)
- `src/gamatrix/helpers/misc_helper.py` (slug normalization)
- `src/gamatrix/helpers/network_helper.py` (IP/CIDR authorization checks)
- `src/gamatrix/helpers/constants.py` (platforms/modes/rate-limit constants)

## Execution model

### CLI mode
1. Parse args in `parse_cmdline()`.
2. Build merged config in `build_config()`.
3. Initialize `Cache` and `IGDBHelper`.
4. Initialize `gogDB` and call `get_common_games()`.
5. For each game: resolve IGDB ID, fetch game info, fetch multiplayer info.
6. Save cache and compute multiplayer status (`set_multiplayer_status()`).
7. Merge duplicate titles, filter games, print results.

### Server mode
1. Same startup/config/cache/helper initialization.
2. Flask routes:
   - `/` -> `root()`
   - `/upload` -> `upload_file()`
   - `/compare` -> `compare_libraries()`
3. Routes enforce IP authorization with `check_ip_is_authorized()`.
4. `/compare` runs the same ingestion+enrichment pipeline, then renders templates.

## Data flow and boundaries

### Inputs
- YAML config (`users`, DB paths, hidden titles, metadata, CIDRs, API credentials)
- SQLite DBs (per-user GOG Galaxy data)
- IGDB HTTP endpoints (token, external game mapping, game details, multiplayer modes)

### Transformations
- Extract owned/installed release keys from SQLite (`gogDB.get_owned_games()`, `gogDB.get_installed_games()`).
- Normalize title -> slug (`get_slug_from_title()`).
- Resolve preferred IGDB key (`gogDB.get_igdb_release_key()`, Steam > GOG > fallback).
- Enrich via IGDB (`IGDBHelper` methods).
- Set multiplayer/max player status (`set_multiplayer_status()`).
- Merge duplicate slugs and filter by ownership/install/platform criteria.

### Output targets
- CLI stdout summary/list
- Flask template render payloads
- Cache JSON file persisted by `Cache.save()`

## Module/function map (runtime)

### `gamatrix.__main__`
- Routes: `root`, `upload_file`, `compare_libraries`
- Config/utilities: `get_db_name_from_ip`, `allowed_file`, `init_opts`, `get_db_mtime`, `build_config`, `set_multiplayer_status`, `parse_cmdline`
- Orchestrates interactions with `gogDB`, `IGDBHelper`, `Cache`

### `gamatrix.helpers.gogdb_helper`
- Standalone: `is_sqlite3`
- Class `gogDB` methods:
  - DB/session lifecycle: `use_db`, `close_connection`
  - Core extractors: `get_user`, `get_gamepiecetype_id`, `get_owned_games`, `get_installed_games`
  - Key selection and shaping: `get_igdb_release_key`, `get_common_games`
  - Post-processing: `merge_duplicate_titles`, `filter_games`, `get_caption`, `_sort`

### `gamatrix.helpers.igdb_helper`
- Class `IGDBHelper` methods:
  - Auth/cache setup: `__init__`, `_init_cache`, `get_access_token`, `_set_headers`
  - API core: `api_request`
  - Enrichment: `get_igdb_id`, `get_igdb_id_by_slug`, `get_game_info`, `get_multiplayer_info`
  - Helpers: `_get_max_players`, `_igdb_id_in_cache`

### `gamatrix.helpers.cache_helper`
- `Cache.__init__`, `Cache.save`

### `gamatrix.helpers.misc_helper`
- `get_slug_from_title`

### `gamatrix.helpers.network_helper`
- `_ip_allowed`, `check_ip_is_authorized`

## Relationship summary

- `__main__` depends on all helper modules and acts as coordinator.
- `gogdb_helper` depends on `constants` and `misc_helper`.
- `igdb_helper` depends on `constants` and external `requests`.
- Tests validate command-line config behavior and SQLite header validation.
- `doc/samples/*.py` are educational/diagnostic extraction scripts mirroring ingestion logic.

## Ingestion-focused observations

- Ingestion path is centralized but tightly coupled to UI/entrypoint concerns.
- Game record and cache contracts are implicit (dict-based), not strongly typed.
- Enrichment calls are largely sequential and likely dominant for large libraries.
- Existing cache is functional but minimal (dirty flag + persisted payload).
