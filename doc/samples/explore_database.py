#!/usr/bin/env python3
"""
Explore GOG Galaxy Database Structure

This script explores and displays the structure of a GOG Galaxy database,
including tables, schemas, and sample data. Useful for understanding how
GOG Galaxy stores game information.

Usage:
    python explore_database.py /path/to/galaxy-2.0.db

Output:
    - List of all tables
    - Schema for each table
    - Sample data from important tables
    - Record counts
"""

import sqlite3
import sys
import os


def connect_to_database(db_path):
    """
    Connect to the GOG Galaxy SQLite database.

    Args:
        db_path: Path to the galaxy-2.0.db file

    Returns:
        sqlite3.Connection object

    Raises:
        FileNotFoundError: If database doesn't exist
        sqlite3.Error: If database is invalid or corrupted
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        # Verify it's a valid SQLite database
        conn.execute("SELECT 1")
        return conn
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Invalid or corrupted database: {e}")


def get_all_tables(conn):
    """
    Get list of all tables in the database.

    Args:
        conn: Database connection

    Returns:
        List of table names
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """
    )
    return [row[0] for row in cursor.fetchall()]


def get_table_schema(conn, table_name):
    """
    Get the schema (columns and types) for a table.

    Args:
        conn: Database connection
        table_name: Name of the table

    Returns:
        List of tuples (cid, column_name, type, notnull, default_value, pk)
    """
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def get_row_count(conn, table_name):
    """
    Get the number of rows in a table.

    Args:
        conn: Database connection
        table_name: Name of the table

    Returns:
        Integer count of rows
    """
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cursor.fetchone()[0]


def get_sample_data(conn, table_name, limit=5):
    """
    Get sample rows from a table.

    Args:
        conn: Database connection
        table_name: Name of the table
        limit: Number of rows to retrieve

    Returns:
        List of rows (as tuples)
    """
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
    return cursor.fetchall()


def display_table_info(conn, table_name, show_samples=True):
    """
    Display comprehensive information about a table.

    Args:
        conn: Database connection
        table_name: Name of the table
        show_samples: Whether to show sample data
    """
    print(f"\n{'='*60}")
    print(f"Table: {table_name}")
    print(f"{'='*60}")

    # Get row count
    row_count = get_row_count(conn, table_name)
    print(f"Row Count: {row_count}")

    # Get and display schema
    schema = get_table_schema(conn, table_name)
    print("\nSchema:")
    print(f"  {'Column':<30} {'Type':<15} {'NotNull':<8} {'PK':<4}")
    print(f"  {'-'*30} {'-'*15} {'-'*8} {'-'*4}")
    for col in schema:
        cid, col_name, col_type, not_null, default_val, is_pk = col
        print(
            f"  {col_name:<30} {col_type:<15} {bool(not_null)!s:<8} {bool(is_pk)!s:<4}"
        )

    # Show sample data if requested and table has rows
    if show_samples and row_count > 0:
        print("\nSample Data (first 3 rows):")
        samples = get_sample_data(conn, table_name, limit=3)
        for i, row in enumerate(samples, 1):
            print(f"\n  Row {i}:")
            for col_idx, (col_info, value) in enumerate(zip(schema, row)):
                col_name = col_info[1]  # Column name is at index 1 (after cid)
                # Truncate long values
                str_value = str(value)
                if len(str_value) > 60:
                    str_value = str_value[:57] + "..."
                print(f"    {col_name}: {str_value}")


def main():
    """Main function to explore the database."""
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    db_path = sys.argv[1]

    print("=" * 60)
    print("GOG Galaxy Database Explorer")
    print("=" * 60)
    print(f"Database: {db_path}")

    try:
        # Connect to database
        conn = connect_to_database(db_path)

        # Get all tables
        tables = get_all_tables(conn)
        print(f"\nTotal Tables: {len(tables)}")
        print("\nAll Tables:")
        for i, table in enumerate(tables, 1):
            print(f"  {i}. {table}")

        # Key tables for Gamatrix
        key_tables = [
            "Users",
            "GamePieceTypes",
            "GamePieces",
            "ProductPurchaseDates",
            "InstalledProducts",
            "InstalledExternalProducts",
            "Platforms",
        ]

        print("\n" + "=" * 60)
        print("KEY TABLES FOR GAMATRIX")
        print("=" * 60)

        for table in key_tables:
            if table in tables:
                display_table_info(conn, table, show_samples=True)
            else:
                print(f"\n[WARNING] Table '{table}' not found in database")

        # Additional tables (without samples for brevity)
        print("\n" + "=" * 60)
        print("OTHER TABLES (schema only)")
        print("=" * 60)

        other_tables = [t for t in tables if t not in key_tables]
        for table in other_tables:
            display_table_info(conn, table, show_samples=False)

        # Summary statistics
        print("\n" + "=" * 60)
        print("DATABASE SUMMARY")
        print("=" * 60)

        # User info
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Users")
        user_count = cursor.fetchone()[0]
        print(f"Users: {user_count}")

        # Game info
        cursor.execute("SELECT COUNT(DISTINCT releaseKey) FROM GamePieces")
        unique_games = cursor.fetchone()[0]
        print(f"Unique Games (release keys): {unique_games}")

        # Owned games
        cursor.execute("SELECT COUNT(*) FROM ProductPurchaseDates")
        owned_count = cursor.fetchone()[0]
        print(f"Owned Games: {owned_count}")

        # Installed games
        cursor.execute("SELECT COUNT(*) FROM InstalledProducts")
        installed_gog = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM InstalledExternalProducts")
        installed_external = cursor.fetchone()[0]
        print(f"Installed Games (GOG): {installed_gog}")
        print(f"Installed Games (External): {installed_external}")
        print(f"Total Installed: {installed_gog + installed_external}")

        conn.close()

        print("\n" + "=" * 60)
        print("Exploration complete!")
        print("=" * 60)

    except FileNotFoundError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"\nDatabase Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
