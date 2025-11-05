# PostgreSQL database management for audio fingerprint storage(Creates database, inserts data, updates )

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
    # Adds a new track to the music table
    cursor = db_conn.cursor()
    insert_sql = "INSERT INTO music (title) VALUES (%s)"
    cursor.execute(insert_sql, (title,))
    db_conn.commit()

def lookup_track_id_by_filename(file_name, db_conn):
    # Retrieves track ID using filename (removes .wav extension)
    cursor = db_conn.cursor()
    select_sql = 'SELECT song_id from music WHERE title = %s'
    title_value = (file_name[:-4],)
    print(f"Looking for title: '{file_name[:-4]}'")
    cursor.execute(select_sql, title_value)
    result_rows = cursor.fetchall()
    print("Found records:", result_rows)
    return result_rows[0][0]

def store_audio_signatures(file_name, time_array, signature_data, db_conn):
    # Stores fingerprint signatures for a track
    insert_query = 'INSERT INTO fingerprint (song_id, center, signature) VALUES (%s,%s,%s)'
    track_id = lookup_track_id_by_filename(file_name, db_conn)
    for idx in range(len(time_array)):
        row_data = (
            track_id,
            float(time_array[idx]),
            [float(val) for val in signature_data[idx]]
        )
        cursor = db_conn.cursor()
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
    # Retrieves all fingerprint signatures for a specific track
    cursor = db_conn.cursor()
    cursor.execute('select signature from fingerprint where song_id=%s', (track_id,))
    result_rows = cursor.fetchall()
    # Transform database decimals to Python floats
    result_rows = [list(map(float, list(row[0]))) for row in result_rows]
    return result_rows
