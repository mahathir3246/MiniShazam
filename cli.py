"""
Command-line interface for MiniShazam workflows.

This file provides a simple command-line way to interact with MiniShazam.
You can either:
  1. Build the database: Scan all MP3 files, create fingerprints, and store them
  2. Identify a song: Take a recorded audio snippet and find which song it matches

Usage examples:
  python3 cli.py build                           # Build database from MP3 files
  python3 cli.py identify music/snippet/test.wav # Find which song matches this recording
"""

from __future__ import annotations

import argparse
import sys

import Database.database as db
import orchestrator


def run_cli(argv: list[str] | None = None) -> int:
    """
    Main entry point for the command-line interface.
    
    This function:
    1. Sets up the argument parser with available commands
    2. Parses the user's input from the command line
    3. Connects to the database
    4. Runs the appropriate command (build or identify)
    5. Returns an exit code (0 = success, 1 = error)
    """
    
    # Create the main argument parser with a description
    parser = argparse.ArgumentParser(description="MiniShazam")

    # Set up subcommands (like 'git commit', 'git push' - we have 'build' and 'identify')
    subparsers = parser.add_subparsers(dest="command")

    # 'build' command - scans MP3 files and creates the fingerprint database
    # No extra arguments needed - it uses default directories
    subparsers.add_parser("build", help="Build database from MP3 files in ./music/mp3")

    # 'identify' command - takes a WAV file and finds the matching song
    # Requires one argument: the path to the audio snippet
    identify_parser = subparsers.add_parser("identify", help="Identify a WAV snippet against the database")
    identify_parser.add_argument("snippet", help="Path to the WAV snippet")

    # Parse whatever the user typed in the command line
    args = parser.parse_args(argv)

    # If no command was given, show the help message
    if args.command is None:
        parser.print_help()
        return 1

    # Connect to the PostgreSQL database
    # This connection will be used for all database operations
    connection = db.get_db_connection()
    
    try:
        # Handle the 'build' command
        # This processes all MP3 files in ./music/mp3, converts them to WAV,
        # generates fingerprints, and stores everything in the database
        if args.command == "build":
            orchestrator.construct_music_database(connection)
            return 0

        # Handle the 'identify' command
        # This takes the snippet file, generates its fingerprint,
        # and compares it against all songs in the database
        if args.command == "identify":
            matches = orchestrator.find_matching_track(connection, args.snippet)
            if matches:
                # Print all matching songs (usually just one best match)
                for match in matches:
                    print(f"[RESULT] Match found: {match}")
                return 0

            print("[RESULT] No matches found.")
            return 1

        # If somehow an unknown command got through, show an error
        print(f"[ERROR] Unknown command: {args.command}")
        return 1

    finally:
        # Always close the database connection when we're done
        # This runs even if there was an error above
        connection.close()


# This runs when you execute the file directly (python3 cli.py ...)
# It calls run_cli() and exits with the return code
if __name__ == "__main__":
    sys.exit(run_cli())
