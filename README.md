# MiniShazam

## Overview

MiniShazam uses audio fingerprinting to match recorded audio snippets against a database of known songs. It processes MP3 files, generates unique fingerprints, and can identify songs from short recordings.


## Project Structure

- Database/ # Database configuration and operations
 - config.py # Database credentials
 - database.py # Database functions
- audioProcessing/ # Audio processing modules
 - SASP_audio_processing.py # Spectrogram and fingerprint generation
 - SASP_audio_utils.py # MP3 conversion and utilities
- music/
 - mp3/ # Source MP3 files
 - wav/ # Converted WAV files
 - snippet/ # Recorded audio snippets
- cli.py # Command-line interface
- GUI.py # Graphical user interface
- orchestrator.py # Main logic connecting database and audio processing
- requirements.txt # Python dependencies


## Installation

### 1. Install PostgreSQL

#### For WSL (Windows Subsystem for Linux)

1. **Update package list**:
 
   sudo apt update
   2. **Install PostgreSQL**:
   
   sudo apt install postgresql postgresql-contrib
   3. **Start PostgreSQL service**:
   sudo service postgresql start
   4. **Create PostgreSQL user and database**:h
   sudo -u postgres psql
      
   Then in the PostgreSQL prompt:
   CREATE USER your_username WITH PASSWORD 'your_password';
   ALTER USER your_username CREATEDB;
   CREATE DATABASE music;
   \q
   ### 2. Configure Database Credentials

Update `Database/config.py` with your PostgreSQL credentials:
HOST = 'localhost'
DATABASE = 'music'
DB_USER = 'your_username'
DB_PASSWORD = 'your_password'### 3. Install Python Dependencies
h
pip install -r requirements.txt## Usage

### Building the Database

First, place your MP3 files in the `music/mp3/` directory, then build the database:

   - python cli.py build

This will:
- Convert MP3 files to WAV format
- Generate audio fingerprints for each track
- Store everything in the PostgreSQL database

### Identifying Songs via CLI

To identify a WAV snippet file:
ash
python cli.py identify music/snippet/your_recording.wav### Using the GUI

Launch the graphical interface:

   - python GUI.py

Then:
1. Click "Tap to minishazam" to start recording
2. Play the song you want to identify
3. Click "Stop" when done
4. The app will identify the song and display the result