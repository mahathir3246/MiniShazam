"""
Database Configuration File

This file stores the connection settings for the PostgreSQL database.
You need to update these values to match your local PostgreSQL setup.

IMPORTANT: Before running MiniShazam, make sure:
1. PostgreSQL is installed and running on your computer
2. You have created a database called 'music' (or change DATABASE below)
3. You have a user with the correct password (update DB_USER and DB_PASSWORD)

To create the database in PostgreSQL:
  1. Open terminal and run: psql -U postgres
  2. Run: CREATE DATABASE music;
  3. Run: \q to exit
"""

# The hostname where PostgreSQL is running
# 'localhost' means it's on your own computer
HOST = 'localhost'

# The name of the database to store fingerprints
# This database must exist before running the application
DATABASE = 'music'

# Your PostgreSQL username
# 'postgres' is the default admin user
DB_USER = 'postgres'

# Your PostgreSQL password
# CHANGE THIS to your actual password!
DB_PASSWORD = 'yourpassword'
