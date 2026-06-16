# GOG Database Sample Scripts

This directory contains sample Python scripts demonstrating how to extract data from the GOG Galaxy database. These scripts are designed to be educational and can be run independently of the main Gamatrix application.

## Purpose

These samples help you:
- Understand the GOG Galaxy database structure
- Learn how to extract game ownership data
- See how Gamatrix processes the database
- Test database queries without running the full application

## Scripts

### 1. `explore_database.py`
Explores and displays the structure of a GOG Galaxy database.

**What it does**:
- Lists all tables in the database
- Shows schema for each table
- Displays sample data from key tables
- Counts records in important tables

**Usage**:
```bash
python explore_database.py /path/to/galaxy-2.0.db
```

**Output**: Human-readable database structure and sample data.

---

### 2. `extract_owned_games.py`
Extracts the list of games owned by a user.

**What it does**:
- Identifies the user from the database
- Queries owned games using Gamatrix's approach
- Shows game titles, platforms, and release keys
- Demonstrates the view-based query strategy

**Usage**:
```bash
python extract_owned_games.py /path/to/galaxy-2.0.db
```

**Output**: List of owned games with metadata.

---

### 3. `extract_installed_games.py`
Shows which games are currently installed.

**What it does**:
- Queries both GOG and external platform installations
- Maps platform IDs to platform names
- Shows the release keys for installed games
- Compares installed vs. owned games

**Usage**:
```bash
python extract_installed_games.py /path/to/galaxy-2.0.db
```

**Output**: List of installed games with platform information.

---

### 4. `complete_extraction_demo.py`
Full demonstration of the complete data extraction process.

**What it does**:
- Replicates Gamatrix's extraction logic
- Shows all steps: user identification, owned games, installed games
- Builds the game data structure Gamatrix uses
- Exports results to JSON for inspection

**Usage**:
```bash
python complete_extraction_demo.py /path/to/galaxy-2.0.db [output.json]
```

**Output**: Comprehensive game data in JSON format and console summary.

---

## Requirements

These scripts require only Python's standard library (no external dependencies):
- `sqlite3` (built-in)
- `json` (built-in)
- `sys`, `os` (built-in)

## Black Box Testing Approach

These scripts are designed with a "black box" testing philosophy:

1. **Self-Contained**: Each script can run independently
2. **Clear Inputs/Outputs**: Simple command-line interface
3. **No Internal Dependencies**: Don't require knowledge of Gamatrix internals
4. **Human-Readable Output**: Results are formatted for easy reading
5. **Educational Comments**: Code is well-commented for learning

## Example Workflow

### Getting Started
```bash
# 1. Locate your GOG Galaxy database
# Windows: C:\ProgramData\GOG.com\Galaxy\storage\galaxy-2.0.db
# Linux: ~/.local/share/GOG.com/Galaxy/storage/galaxy-2.0.db

# 2. Copy it to a safe location (optional but recommended)
cp /path/to/galaxy-2.0.db ./my-gog-backup.db

# 3. Explore the database structure
python explore_database.py ./my-gog-backup.db

# 4. Extract owned games
python extract_owned_games.py ./my-gog-backup.db

# 5. See what's installed
python extract_installed_games.py ./my-gog-backup.db

# 6. Run complete extraction
python complete_extraction_demo.py ./my-gog-backup.db output.json
```

### Comparing Multiple Users
```bash
# Extract data for each user
python complete_extraction_demo.py user1-galaxy-2.0.db user1.json
python complete_extraction_demo.py user2-galaxy-2.0.db user2.json

# Now you can compare the JSON files to find common games
# (This would be done by Gamatrix in the real application)
```

## Understanding the Output

### Sample Output from `extract_owned_games.py`
```
=== GOG Galaxy Database Analysis ===
Database: /path/to/galaxy-2.0.db
User ID: 1234567

=== Owned Games (15 found) ===

1. Counter-Strike: Global Offensive
   Release Keys: steam_730
   Platforms: steam

2. The Witcher 3: Wild Hunt
   Release Keys: gog_1207658924, steam_292030
   Platforms: gog, steam

3. Among Us
   Release Keys: steam_945360, epic_33956bcb55d4452d8c47e16b94e294bd
   Platforms: steam, epic
```

### Sample Output from `extract_installed_games.py`
```
=== Installed Games Analysis ===
Database: /path/to/galaxy-2.0.db

=== Installed Games (8 found) ===

Installed:
- steam_730 (Counter-Strike: Global Offensive)
- gog_1207658924 (The Witcher 3: Wild Hunt)
- steam_945360 (Among Us)

Not Installed (but owned):
- epic_33956bcb55d4452d8c47e16b94e294bd (Among Us)
- steam_292030 (The Witcher 3: Wild Hunt)
```

## Modifying the Scripts

These scripts are intentionally simple and can be easily modified:

### Add More Metadata
```python
# In extract_owned_games.py, add more game piece types:
query = """
    SELECT gp.value 
    FROM GamePieces gp
    WHERE gp.releaseKey = ? 
    AND gp.gamePieceTypeId = (
        SELECT id FROM GamePieceTypes WHERE type='summary'
    )
"""
```

### Filter by Platform
```python
# Only show Steam games:
for release_key in owned_games:
    if release_key.startswith('steam_'):
        print(release_key)
```

### Export to CSV
```python
import csv

with open('output.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Title', 'Platform', 'Release Key'])
    for game in games:
        writer.writerow([game['title'], game['platform'], game['release_key']])
```

## Troubleshooting

### "Database is locked" error
- Ensure GOG Galaxy is closed
- Try copying the database file first
- Use read-only mode: `sqlite3.connect(db_path, uri=True)`

### "No such table" error
- Verify you're using a GOG Galaxy 2.0 database (not 1.0)
- Check the database isn't corrupted: `sqlite3 database.db "PRAGMA integrity_check;"`

### Empty results
- Ensure you've synced your libraries in GOG Galaxy
- Check that integrations are properly connected
- Verify games show up in the GOG Galaxy application

### Unicode/encoding errors
- Use UTF-8 encoding when reading database values
- Some game titles contain special characters

## Contributing

If you create additional sample scripts or improvements:
1. Follow the black box testing approach
2. Keep dependencies minimal (standard library preferred)
3. Add clear documentation in this README
4. Include example output in comments

## Related Documentation

- [GOG Database Schema](../GOG_DATABASE_SCHEMA.md) - Detailed database structure
- [Main README](../../README.md) - Gamatrix application documentation

## License

These sample scripts are part of the Gamatrix project and share the same license.
