"""
Database Operations Module

This file handles all interactions with the PostgreSQL database.
It provides functions to:
- Connect to the database
- Create the necessary tables (music and fingerprint)
- Store and retrieve song metadata
- Store and retrieve audio fingerprints

The database has two main tables:
1. 'music' table: Stores song information (ID, title, fingerprinted status)
2. 'fingerprint' table: Stores the actual fingerprint hashes for each song

Each song can have thousands of fingerprint hashes - these are what we use
to identify songs when someone plays a recording.
"""

import os
import psycopg2
from .config import HOST, DATABASE, DB_USER, DB_PASSWORD


def get_db_connection():
    """
    Creates and returns a connection to the PostgreSQL database.
    
    This is the first thing we call before any database operation.
    The connection object lets us send queries to the database.
    
    Returns:
        A psycopg2 connection object that we can use to interact with the database
    
    Raises:
        psycopg2.Error: If the connection fails (wrong password, database not running, etc.)
    """
    return psycopg2.connect(
        host=HOST,           # Where the database server is (usually 'localhost')
        database=DATABASE,   # Which database to use (usually 'music')
        user=DB_USER,        # Your PostgreSQL username
        password=DB_PASSWORD # Your PostgreSQL password
    )


def initialize_schema(db_conn):
    """
    Creates the database tables needed for MiniShazam.
    
    WARNING: This function DROPS existing tables first, so all previous
    data will be deleted! This is intentional - we rebuild from scratch.
    
    Tables created:
    1. 'music' table:
       - song_id: Auto-incrementing unique ID for each song
       - title: The name of the song (from the filename)
       - fingerprinted: Flag (0 or 1) indicating if fingerprinting is complete
    
    2. 'fingerprint' table:
       - sig_id: Auto-incrementing unique ID for each fingerprint entry
       - song_id: Links to the music table (which song this fingerprint belongs to)
       - center: The time index where this fingerprint was found
       - signature: An array of numbers representing the fingerprint hash
    
    Args:
        db_conn: An active database connection from get_db_connection()
    """
    cursor = db_conn.cursor()
    
    # Drop existing tables to start fresh
    # The order matters! fingerprint references music, so drop it first
    cursor.execute("DROP TABLE IF EXISTS fingerprint")
    cursor.execute("DROP TABLE IF EXISTS music")
    
    # Create the music table to store song metadata
    # SERIAL PRIMARY KEY means song_id auto-increments (1, 2, 3, ...)
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS music (
            song_id SERIAL PRIMARY KEY,
            title TEXT not null,
            fingerprinted INT default 0
            )""")
    
    # Create the fingerprint table to store audio fingerprints
    # REFERENCES music (song_id) creates a foreign key relationship
    # ON DELETE CASCADE means if we delete a song, its fingerprints are also deleted
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS fingerprint (
            sig_id SERIAL PRIMARY KEY,
            song_id INT REFERENCES music (song_id) ON DELETE CASCADE,
            center INT,
            signature NUMERIC ARRAY
            )""")
    
    # Commit the changes to make them permanent
    db_conn.commit()


def insert_track_metadata(title, db_conn):
    """
    Adds a new song to the music table.
    
    This is called when we first discover an MP3 file. We store the
    song's title and get back a unique ID that we'll use for everything else.
    
    Args:
        title: The name of the song (usually the filename without .mp3)
        db_conn: An active database connection
    
    Returns:
        The song_id (integer) assigned to this new track
    """
    cursor = db_conn.cursor()
    
    # INSERT the title and get back the auto-generated song_id
    # RETURNING song_id tells PostgreSQL to give us the ID it created
    insert_sql = "INSERT INTO music (title) VALUES (%s) RETURNING song_id"
    cursor.execute(insert_sql, (title,))
    
    # Fetch the returned song_id
    track_id = cursor.fetchone()[0]
    
    # Save the changes
    db_conn.commit()
    return track_id


def lookup_track_id_by_filename(file_name, db_conn):
    """
    Finds a song's ID by looking up its filename/title.
    
    This is useful when we have a WAV file and need to find which
    song entry it corresponds to in the database.
    
    Args:
        file_name: The filename (with or without extension)
        db_conn: An active database connection
    
    Returns:
        The song_id (integer) for this track
    
    Raises:
        IndexError: If no matching song is found
    """
    cursor = db_conn.cursor()
    
    # Build the query - we search by title
    select_sql = 'SELECT song_id from music WHERE title = %s'
    
    # Remove the file extension (.wav, .mp3) to get just the title
    title_without_ext = os.path.splitext(file_name)[0]
    
    # Debug output to help troubleshoot
    print(f"Looking for title: '{title_without_ext}'")
    
    # Execute the query
    title_value = (title_without_ext,)
    cursor.execute(select_sql, title_value)
    result_rows = cursor.fetchall()
    
    print("Found records:", result_rows)
    
    # Return just the song_id from the first matching row
    return result_rows[0][0]


def store_fingerprint_hashes(track_id, hash_entries, db_conn):
    """
    Stores all the fingerprint hashes for a song.
    
    Each song generates hundreds or thousands of fingerprint hashes.
    These hashes are what we compare against when trying to identify
    a recorded snippet. Each hash captures a unique moment in the song.
    
    Args:
        track_id: The song_id to associate these fingerprints with
        hash_entries: A list of (hash_tuple, time_index) pairs
                     - hash_tuple: (anchor_freq, target_freq, time_delta)
                     - time_index: When in the song this hash occurs
        db_conn: An active database connection
    """
    insert_query = 'INSERT INTO fingerprint (song_id, center, signature) VALUES (%s,%s,%s)'
    cursor = db_conn.cursor()

    # Remove duplicate entries to save space
    # dict.fromkeys() preserves order while removing duplicates
    unique_entries = list(dict.fromkeys(hash_entries))

    # Insert each fingerprint hash into the database
    for hash_tuple, anchor_time_idx in unique_entries:
        row_data = (
            track_id,                                    # Which song this belongs to
            int(anchor_time_idx),                        # When in the song (time index)
            [int(component) for component in hash_tuple] # The hash values as an array
        )
        cursor.execute(insert_query, row_data)

    # Save all the inserts
    db_conn.commit()


def mark_as_fingerprinted(track_id, db_conn):
    """
    Marks a song as fully fingerprinted.
    
    After we've generated and stored all fingerprints for a song,
    we update this flag to indicate the process is complete.
    This can be useful for resuming interrupted builds.
    
    Args:
        track_id: The song_id to mark as complete
        db_conn: An active database connection
    """
    cursor = db_conn.cursor()
    
    # Set fingerprinted = 1 (true) for this song
    update_sql = 'UPDATE music SET fingerprinted = 1 where song_id = %s'
    cursor.execute(update_sql, (track_id,))
    
    db_conn.commit()


def get_track_name_by_id(track_id, db_conn):
    """
    Retrieves a song's title using its ID.
    
    After we find a matching song_id during identification,
    we use this to get the human-readable song name to display.
    
    Args:
        track_id: The song_id to look up
        db_conn: An active database connection
    
    Returns:
        The song title as a string
    """
    cursor = db_conn.cursor()
    
    select_sql = 'SELECT title from music WHERE song_id = %s'
    cursor.execute(select_sql, (track_id,))
    result_rows = cursor.fetchall()
    
    return result_rows[0][0]


def get_highest_track_id(db_conn):
    """
    Returns the highest song_id in the database.
    
    We need this to know how many songs we have, so we can
    loop through all of them when trying to identify a snippet.
    
    Args:
        db_conn: An active database connection
    
    Returns:
        The maximum song_id (integer), or None if database is empty
    """
    cursor = db_conn.cursor()
    
    # Get the maximum song_id value
    cursor.execute('SELECT MAX(song_id) from music')
    result_rows = cursor.fetchall()
    
    return result_rows[0][0]


def fetch_track_signatures(db_conn, track_id):
    """
    Retrieves all fingerprint hashes for a specific song.
    
    When identifying a snippet, we compare its hashes against
    the stored hashes of each song. This function gets all the
    fingerprints we stored for a particular song.
    
    Args:
        db_conn: An active database connection
        track_id: The song_id to fetch fingerprints for
    
    Returns:
        A list of (time_index, signature_array) tuples
        Each tuple represents one fingerprint hash for this song
    """
    cursor = db_conn.cursor()
    
    # Get all fingerprints for this song
    cursor.execute('select center, signature from fingerprint where song_id=%s', (track_id,))
    result_rows = cursor.fetchall()
    
    # Convert the results to Python integers for easier processing
    # PostgreSQL returns Decimal types, but we want plain ints
    formatted_rows = [
        (int(center), [int(component) for component in signature])
        for center, signature in result_rows
    ]
    
    return formatted_rows
