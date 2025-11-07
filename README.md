# MiniShazam

# Database Module

This module provides PostgreSQL database management for the audio fingerprinting system.

## Overview

The `database` module handles all database operations including schema creation, data insertion, retrieval, and updates for storing audio fingerprints and track metadata.

## Database Schema

### `music` Table
- `song_id` (SERIAL PRIMARY KEY) - Unique identifier for each track
- `title` (TEXT NOT NULL) - Track title
- `fingerprinted` (INT DEFAULT 0) - Flag indicating if track has been processed (0 = not fingerprinted, 1 = fingerprinted)

### `fingerprint` Table
- `sig_id` (SERIAL PRIMARY KEY) - Unique identifier for each fingerprint
- `song_id` (INT) - Foreign key reference to `music.song_id` (CASCADE DELETE)
- `center` (INT) - Time center point for the fingerprint
- `signature` (NUMERIC ARRAY) - Audio fingerprint signature data

## Setup

### 1. Install PostgreSQL

#### For WSL (Windows Subsystem for Linux)

1. **Update package list**:
   ```bash
   sudo apt update
   ```

2. **Install PostgreSQL**:
   ```bash
   sudo apt install postgresql postgresql-contrib
   ```

3. **Start PostgreSQL service**:
   ```bash
   sudo service postgresql start
   ```

4. **Create PostgreSQL user and database**:
   ```bash
   sudo -u postgres psql
   ```
   Then in the PostgreSQL prompt:
   ```sql
   CREATE USER <'your_username'> WITH PASSWORD 'your_password';
   ALTER USER <'your_username'> CREATEDB;
   CREATE DATABASE <database_name>;
   \q
   ```


### 2. Configure Database Credentials

Update `database/config.py` with your PostgreSQL credentials:
```python
HOST=<hostname>  #probably localhost
DATABASE=<database_name> # Database you created in step 4
DB_USER = 'your_username'  # username you created in step 4
DB_PASSWORD = 'your_password'  # password you set when creating the user

```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```