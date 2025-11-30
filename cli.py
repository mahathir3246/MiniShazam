"""Command-line interface for MiniShazam workflows."""

from __future__ import annotations

import argparse
import sys

import Database.database as db
import orchestrator


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MiniShazam")

    subparsers = parser.add_subparsers(dest="command")

    # Build command - builds database from MP3 files
    subparsers.add_parser("build", help="Build database from MP3 files in ./music/mp3")

    # Identify command - finds matching song for a snippet
    identify_parser = subparsers.add_parser("identify", help="Identify a WAV snippet against the database")
    identify_parser.add_argument("snippet", help="Path to the WAV snippet")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    connection = db.get_db_connection()
    try:
        if args.command == "build":
            # Uses default directories: ./music/mp3 and ./music/wav
            orchestrator.construct_music_database(connection)
            return 0

        if args.command == "identify":
            matches = orchestrator.find_matching_track(connection, args.snippet)
            if matches:
                for match in matches:
                    print(f"[RESULT] Match found: {match}")
                return 0

            print("[RESULT] No matches found.")
            return 1

        print(f"[ERROR] Unknown command: {args.command}")
        return 1

    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(run_cli())

