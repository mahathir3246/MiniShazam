"""Command-line interface for MiniShazam workflows."""

from __future__ import annotations

import argparse
import sys

import Database.database as db
import orchestrator


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MiniShazam - Database and audio processing integration")
    parser.add_argument("--mp3-dir", default="./music/mp3", help="Directory with source MP3 tracks")
    parser.add_argument("--wav-dir", default="./music/wav", help="Directory containing WAV tracks")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("construct", help="Populate the database from MP3 files")

    identify_parser = subparsers.add_parser("identify", help="Identify a WAV snippet against the database")
    identify_parser.add_argument("snippet", help="Path to the WAV snippet")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    connection = db.get_db_connection()
    try:
        if args.command == "construct":
            orchestrator.construct_music_database(connection, mp3_directory=args.mp3_dir, wav_directory=args.wav_dir)
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

