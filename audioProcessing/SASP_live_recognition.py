"""
Live Audio Recognition Module

This file provides functions for recording audio from the microphone
and identifying songs in real-time.

This is an alternative to the GUI - you can use these functions
programmatically to:
1. Record audio from the default microphone
2. Process it into a spectrogram
3. Generate fingerprint hashes
4. Match against the database

USAGE EXAMPLE:
    import Database.database as db
    from audioProcessing.SASP_live_recognition import live_audio_recognition
    
    connection = db.get_db_connection()
    result = live_audio_recognition(connection, duration=10)
    print(f"Detected song: {result}")
    connection.close()

DEPENDENCIES:
- sounddevice: For microphone access
"""

from __future__ import annotations

import sounddevice as sd

from audioProcessing import SASP_audio_processing as audio_processing
import orchestrator


def record_live_audio(duration: int = 10, sample_rate: int = 44_100):
    """
    Records audio from the default microphone.
    
    This function captures sound for the specified duration and returns
    the raw audio data as a NumPy array. The recording happens synchronously -
    the function will block until recording is complete.
    
    Args:
        duration: How many seconds to record (default: 10)
        sample_rate: Samples per second (default: 44100 = CD quality)
                    Higher = better quality but more data
    
    Returns:
        Tuple of (audio_data, sample_rate)
        - audio_data: NumPy array of audio samples (float32, mono)
        - sample_rate: The sample rate used (same as input)
    
    NOTE: Make sure your microphone is working and not muted!
    The function uses the system's default audio input device.
    """

    print(f"[INFO] Recording for {duration} seconds...")
    
    # sd.rec() starts recording and returns immediately
    # It returns a NumPy array that gets filled with audio data
    audio = sd.rec(
        int(duration * sample_rate),  # Total number of samples to record
        samplerate=sample_rate,       # How many samples per second
        channels=1,                   # Mono (1 channel), not stereo (2)
        dtype="float32",              # 32-bit floating point samples
    )
    
    # sd.wait() blocks until recording is complete
    sd.wait()
    
    print("[INFO] Recording finished.")
    
    # Flatten from 2D (samples, channels) to 1D (samples) since we're mono
    return audio.flatten(), sample_rate


def live_audio_recognition(db_connection, duration: int = 20):
    """
    Records from the microphone and identifies the song.
    
    This is a complete pipeline that:
    1. Records audio from your microphone for the specified duration
    2. Converts the audio into a spectrogram (frequency analysis)
    3. Extracts fingerprint hashes from the spectrogram
    4. Compares hashes against all songs in the database
    5. Returns the best matching song title
    
    Args:
        db_connection: Active database connection (from db.get_db_connection())
        duration: How many seconds to record (default: 20)
                 Longer = more accurate but takes more time
    
    Returns:
        The title of the matched song (string), or None if no match found
    
    TIPS FOR BEST RESULTS:
    - Record in a quiet environment
    - Hold the microphone close to the speaker
    - Make sure the song is in your database (run cli.py build first!)
    - Try recording different parts of the song
    """

    # Step 1: Record audio from the microphone
    audio_data, sr = record_live_audio(duration)
    
    # Step 2: Generate a spectrogram from the raw audio
    # This converts time-domain samples to frequency-domain representation
    sr, freq_bins, time_bins, power_matrix = audio_processing.generate_spectrogram_from_array(audio_data, sr)
    
    # Step 3: Extract fingerprint hashes from the spectrogram
    # These hashes capture unique patterns in the audio
    snippet_hashes = audio_processing.generate_constellation_hashes(freq_bins, time_bins, power_matrix)

    # Step 4: Compare against database using time-offset voting
    # This finds songs where hashes match with consistent timing
    matches = orchestrator.identify_from_hashes(db_connection, snippet_hashes)

    # Step 5: Return the result
    if matches:
        # We found a match! Return the best one
        print(f"[RESULT] Live match: {matches[0]}")
        return matches[0]

    # No match found - song might not be in database, or recording was too noisy
    print("[RESULT] No match found.")
    return None
