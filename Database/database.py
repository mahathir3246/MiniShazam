# PostgreSQL database management for audio fingerprint storage(Creates database, inserts data, updates )

import os

import psycopg2
from .config import HOST,DATABASE,DB_USER, DB_PASSWORD


def get_db_connection():
    # Creates and returns a PostgreSQL connection object
    return psycopg2.connect(
        host=HOST,
        database=DATABASE,
        user=DB_USER,
        password=DB_PASSWORD
    )

def initialize_schema(db_conn):
    # Creates music and fingerprint tables
    # Schema Design:
    # - music table: stores track id, title and fingerprinting completion status
    # - fingerprint table: stores computed audio signatures
    #   - linked via foreign key to music table
    cursor = db_conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS fingerprint")
    cursor.execute("DROP TABLE IF EXISTS music")
    
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS music (
            song_id SERIAL PRIMARY KEY,
            title TEXT not null,
            fingerprinted INT default 0
            )""")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS fingerprint (
            sig_id SERIAL PRIMARY KEY,
            song_id INT REFERENCES music (song_id) ON DELETE CASCADE,
            center INT,
            signature NUMERIC ARRAY
            )""")
    
    db_conn.commit()


def insert_track_metadata(title, db_conn):
    # Adds a new track to the music table and returns its id
    cursor = db_conn.cursor()
    insert_sql = "INSERT INTO music (title) VALUES (%s) RETURNING song_id"
    cursor.execute(insert_sql, (title,))
    track_id = cursor.fetchone()[0]
    db_conn.commit()
    return track_id

def lookup_track_id_by_filename(file_name, db_conn):
    # Retrieves track ID using filename (removes .wav extension)
    cursor = db_conn.cursor()
    select_sql = 'SELECT song_id from music WHERE title = %s'
    title_without_ext = os.path.splitext(file_name)[0]
    print(f"Looking for title: '{title_without_ext}'")
    title_value = (title_without_ext,)
    cursor.execute(select_sql, title_value)
    result_rows = cursor.fetchall()
    print("Found records:", result_rows)
    return result_rows[0][0]

def store_fingerprint_hashes(track_id, hash_entries, db_conn):
    # Stores hashed fingerprint signatures for a track
    insert_query = 'INSERT INTO fingerprint (song_id, center, signature) VALUES (%s,%s,%s)'
    cursor = db_conn.cursor()

    unique_entries = list(dict.fromkeys(hash_entries))

    for hash_tuple, anchor_time_idx in unique_entries:
        row_data = (
            track_id,
            int(anchor_time_idx),
            [int(component) for component in hash_tuple]
        )
        cursor.execute(insert_query, row_data)

    db_conn.commit()


def mark_as_fingerprinted(track_id, db_conn):
    # Updates the fingerprinted flag for a completed track
    cursor = db_conn.cursor()
    update_sql = 'UPDATE music SET fingerprinted = 1 where song_id = %s'
    cursor.execute(update_sql, (track_id,))
    db_conn.commit()


def get_track_name_by_id(track_id, db_conn):
    # Fetches track title using its ID
    cursor = db_conn.cursor()
    select_sql = 'SELECT title from music WHERE song_id = %s'
    cursor.execute(select_sql, (track_id,))
    result_rows = cursor.fetchall()
    return result_rows[0][0]


def get_highest_track_id(db_conn):
    # Returns the maximum song_id value for iteration purposes
    cursor = db_conn.cursor()
    cursor.execute('SELECT MAX(song_id) from music')
    result_rows = cursor.fetchall()
    return result_rows[0][0]


def fetch_track_signatures(db_conn, track_id):
    # Retrieves all fingerprint hashes for a specific track
    cursor = db_conn.cursor()
    cursor.execute('select center, signature from fingerprint where song_id=%s', (track_id,))
    result_rows = cursor.fetchall()
    formatted_rows = [
        (int(center), [int(component) for component in signature])
        for center, signature in result_rows
    ]
    return formatted_rows
