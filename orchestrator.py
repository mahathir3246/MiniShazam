"""
Orchestrator Module - The Brain of MiniShazam

This is the main coordination file that brings together:
- Database operations (storing and retrieving fingerprints)
- Audio processing (converting audio to fingerprints)

HOW SHAZAM-STYLE MATCHING WORKS:
================================
1. Each song is converted into a "spectrogram" (visual representation of frequencies over time)
2. We find "peaks" in the spectrogram - moments where certain frequencies are loudest
3. We create "hashes" by pairing nearby peaks together
4. These hashes are stored in the database with their time positions

When identifying a snippet:
1. We do the same process - create hashes from the recording
2. We compare snippet hashes against every song's hashes
3. If hashes match AND their time offsets align, we count it as a "vote"
4. The song with the most aligned votes is the match!

The key insight: Even with background noise, many hashes will still match,
and the correct song will have consistent time offsets between matches.
"""

from __future__ import annotations
import os
from collections import defaultdict
from typing import Iterable, List
import Database.database as db
from audioProcessing import (SASP_audio_processing as audio_processing, SASP_audio_utils as audio_utils)

# ============================================================================
# MATCHING THRESHOLDS
# These values control how confident we need to be before declaring a match.
# Too low = false positives (wrong matches), Too high = misses real matches
# ============================================================================

# Minimum number of matching hashes needed (absolute count)
# A single matching hash could be coincidence - we need at least this many
MIN_ABSOLUTE_VOTES = 5

# Minimum ratio of matching hashes relative to the snippet's total hashes
# Example: If snippet has 100 hashes, at least 0.6% (0.6 hashes) must match
MIN_SNIPPET_VOTE_RATIO = 0.006

# Minimum ratio of matching hashes relative to the stored song's total hashes
# This prevents matching tiny snippets against huge songs by coincidence
MIN_STORED_VOTE_RATIO = 0.004


def _iter_files(directory: str, suffix: str) -> Iterable[str]:
    """
    Helper function to find all files with a specific extension in a directory.
    
    Args:
        directory: Path to the folder to search
        suffix: File extension to look for (e.g., ".mp3", ".wav")
    
    Returns:
        A sorted list of filenames (not full paths) that end with the suffix
    
    Example:
        _iter_files("./music/mp3", ".mp3") might return:
        ["song1.mp3", "song2.mp3", "song3.mp3"]
    """
    # Return empty list if directory doesn't exist
    if not os.path.isdir(directory):
        return []
    
    # Collect all files that match the suffix
    matching_files = []
    for filename in sorted(os.listdir(directory)):
        if filename.lower().endswith(suffix):
            matching_files.append(filename)
    
    return matching_files


def construct_music_database(db_connection, mp3_directory: str = "./music/mp3", wav_directory: str = "./music/wav") -> None:
    """
    Builds the entire fingerprint database from MP3 files.
    
    This is the "learning" phase where MiniShazam learns about all your songs.
    For each MP3 file, it:
    1. Adds the song to the database
    2. Converts MP3 to WAV format (easier to process)
    3. Creates a spectrogram (frequency vs time graph)
    4. Extracts fingerprint hashes from the spectrogram
    5. Stores those hashes in the database
    
    Args:
        db_connection: Active database connection
        mp3_directory: Where to find MP3 files (default: ./music/mp3)
        wav_directory: Where to save converted WAV files (default: ./music/wav)
    
    After running this, the database will contain fingerprints for all songs
    and will be ready to identify recordings!
    """
    
    # Step 1: Create fresh database tables (this deletes old data!)
    db.initialize_schema(db_connection)
    print("[INFO] Database schema initialized.")

    # Keep track of which title maps to which ID
    # We need this because we process MP3s and WAVs separately
    title_to_id = {}

    # ========================================
    # PHASE 1: Process all MP3 files
    # ========================================
    for mp3_file in _iter_files(mp3_directory, ".mp3"):
        # Build the full path to the MP3 file
        mp3_path = os.path.join(mp3_directory, mp3_file)
        
        # Get the song title from the filename (remove .mp3 extension)
        track_title = os.path.splitext(mp3_file)[0]

        # Add this song to the database and get its unique ID
        track_id = db.insert_track_metadata(track_title, db_connection)
        
        # Remember the ID so we can link the WAV file later
        title_to_id[track_title] = track_id
        
        # Try to read ID3 tags (artist, title embedded in the MP3)
        # We just print these for info - we use filename as the actual title
        title, artist = audio_utils.parse_mp3_tags(mp3_path)
        print(f"[INFO] Stored track '{track_title}' (ID3 title='{title}', artist='{artist}').")
        
        # Convert the MP3 to WAV format for audio processing
        # WAV is uncompressed and easier to analyze
        audio_utils.transform_mp3_to_wav(mp3_path)

    print("[INFO] MP3 ingestion complete.")

    # ========================================
    # PHASE 2: Generate fingerprints from WAV files
    # ========================================
    for wav_file in _iter_files(wav_directory, ".wav"):
        wav_path = os.path.join(wav_directory, wav_file)
        
        # Get the title (filename without .wav extension)
        wav_title = os.path.splitext(wav_file)[0]

        # Generate a spectrogram from the WAV file
        # A spectrogram shows which frequencies are present at each moment in time
        spectrogram = audio_processing.generate_spectrogram_from_wav(wav_path)
        
        if spectrogram is None:
            print(f"[WARN] Skipping WAV without spectrogram data: {wav_path}")
            continue

        # Unpack the spectrogram components
        sample_rate, freq_bins, time_bins, power_matrix = spectrogram
        
        # Generate fingerprint hashes from the spectrogram
        # Each hash captures a unique pattern of peaks in the audio
        fingerprint_hashes = audio_processing.generate_constellation_hashes(freq_bins, time_bins, power_matrix)

        # Find the track ID - first try our title_to_id map
        track_id = title_to_id.get(wav_title)
        
        # If not found in map, try looking up in database
        if track_id is None:
            try:
                track_id = db.lookup_track_id_by_filename(wav_file, db_connection)
            except (IndexError, ValueError):
                print(f"[WARN] Missing metadata for '{wav_file}', skipping.")
                continue
        
        # Store all fingerprint hashes for this song
        db.store_fingerprint_hashes(track_id, fingerprint_hashes, db_connection)
        
        # Mark this song as fully processed
        db.mark_as_fingerprinted(track_id, db_connection)
        
        print(f"[INFO] Fingerprint stored for track_id={track_id} ({wav_file}).")

    print("[INFO] Database construction finished.")


def identify_from_hashes(db_connection, snippet_hashes) -> List[str]:
    """
    The core matching algorithm - finds which song matches a set of hashes.
    
    HOW IT WORKS (Time Offset Voting):
    ==================================
    Imagine a hash appears at time T=5 in your snippet and T=105 in the stored song.
    The offset is 100 (105 - 5 = 100).
    
    If this song is correct, OTHER matching hashes should have the SAME offset!
    - Another hash at snippet T=8 should be at song T=108 (offset still 100)
    - Another hash at snippet T=12 should be at song T=112 (offset still 100)
    
    We "vote" for each offset we see. The correct song will have many votes
    for the same offset, while wrong songs will have scattered random offsets.
    
    Args:
        db_connection: Active database connection
        snippet_hashes: List of (hash_tuple, time_index) from the recorded audio
    
    Returns:
        List of matching song titles (usually just one best match)
    """
    
    # Can't match if we have no hashes
    if not snippet_hashes:
        print("[WARN] No hashes generated for snippet; unable to match.")
        return []

    # Build a lookup table: hash -> [list of times it appears in snippet]
    # This lets us quickly find matching hashes
    hash_to_snippet_times = defaultdict(list)
    for hash_tuple, anchor_time_idx in snippet_hashes:
        hash_to_snippet_times[tuple(hash_tuple)].append(anchor_time_idx)

    # Remember how many hashes the snippet has (for ratio calculations)
    snippet_hash_count = len(snippet_hashes)

    # Find out how many songs are in the database
    max_track_id = db.get_highest_track_id(db_connection)
    if max_track_id is None:
        print("[WARN] No tracks in database.")
        return []

    # We'll collect match statistics for each song
    score_details = []
    
    # ========================================
    # Check each song in the database
    # ========================================
    for song_id in range(1, max_track_id + 1):
        # Get all fingerprint hashes for this song
        stored_hashes = db.fetch_track_signatures(db_connection, song_id)
        stored_hash_count = len(stored_hashes)

        # Skip songs with no fingerprints
        if not stored_hash_count:
            score_details.append({"song_id": song_id, "votes": 0, "ratio": 0.0, "stored_ratio": 0.0, "score": 0.0})
            continue

        # Count votes for each time offset
        # Key: offset value, Value: number of times we saw this offset
        offset_votes = defaultdict(int)

        # Compare each stored hash against our snippet
        for anchor_time_idx, signature_components in stored_hashes:
            hash_tuple = tuple(signature_components)
            
            # Does this hash exist in our snippet?
            snippet_times = hash_to_snippet_times.get(hash_tuple)
            if not snippet_times:
                continue  # No match for this hash

            # For each occurrence in the snippet, calculate the time offset
            for snippet_time in snippet_times:
                # Offset = where in song - where in snippet
                offset = anchor_time_idx - snippet_time
                # Add a vote for this offset
                offset_votes[offset] += 1

        # If no hashes matched at all, record zero score
        if not offset_votes:
            score_details.append({"song_id": song_id, "votes": 0, "ratio": 0.0, "stored_ratio": 0.0, "score": 0.0})
            continue

        # Find the offset with the most votes (the best alignment)
        best_vote = max(offset_votes.values())
        
        # Calculate what percentage of snippet hashes matched
        snippet_ratio = best_vote / snippet_hash_count
        
        # Calculate what percentage of stored song hashes matched
        stored_ratio = best_vote / stored_hash_count

        # Apply our confidence thresholds
        # All three conditions must be met to consider this a valid match
        if (
            best_vote < MIN_ABSOLUTE_VOTES          # Need minimum number of matches
            or snippet_ratio < MIN_SNIPPET_VOTE_RATIO  # Need minimum snippet coverage
            or stored_ratio < MIN_STORED_VOTE_RATIO    # Need minimum song coverage
        ):
            score_details.append({"song_id": song_id, "votes": 0, "ratio": 0.0, "stored_ratio": 0.0, "score": 0.0})
            continue

        # Calculate a combined score (multiply both ratios)
        # This balances snippet coverage and song coverage
        combined_score = snippet_ratio * stored_ratio
        
        score_details.append(
            {
                "song_id": song_id,
                "votes": best_vote,
                "ratio": snippet_ratio,
                "stored_ratio": stored_ratio,
                "score": combined_score,
            }
        )

    # ========================================
    # Find the best matching song(s)
    # ========================================
    
    if not score_details:
        print("[WARN] No fingerprints stored; cannot identify snippet.")
        return []

    # Filter to only songs that had any matches
    valid_scores = []
    for detail in score_details:
        if detail["votes"] > 0:
            valid_scores.append(detail)

    if not valid_scores:
        print("[INFO] No matching hashes met the confidence thresholds.")
        return []

    # Find the highest score
    best_score = 0.0
    for detail in valid_scores:
        if detail["score"] > best_score:
            best_score = detail["score"]

    # Get all songs with the best score (usually just one)
    top_candidates = []
    for detail in valid_scores:
        if detail["score"] == best_score:
            top_candidates.append(detail)

    # If there's a tie in score, use vote count as tiebreaker
    best_votes = 0
    for detail in top_candidates:
        if detail["votes"] > best_votes:
            best_votes = detail["votes"]

    # Get the final winning song(s)
    best_song_ids = []
    for detail in top_candidates:
        if detail["votes"] == best_votes:
            best_song_ids.append(detail["song_id"])

    # Build lookup for printing details
    score_by_song = {}
    for detail in top_candidates:
        score_by_song[detail["song_id"]] = detail

    # Get the song titles and print match details
    matches = []
    for song_id in best_song_ids:
        title = db.get_track_name_by_id(song_id, db_connection)
        matches.append(title)
        song_score = score_by_song[song_id]
        print(
            f"[INFO] Best candidate song_id={song_id}, title='{title}', "
            f"votes={song_score['votes']}, snippet_ratio={song_score['ratio']:.3f}, "
            f"stored_ratio={song_score['stored_ratio']:.3f}, score={song_score['score']:.5f}."
        )

    return matches


def find_matching_track(db_connection, snippet_path: str) -> List[str]:
    """
    Main entry point for song identification.
    
    Takes a WAV file path (your recording) and finds which song it matches.
    This is what gets called when you click "identify" in the GUI or CLI.
    
    Process:
    1. Load the WAV file
    2. Create a spectrogram (frequency vs time visualization)
    3. Generate fingerprint hashes from the spectrogram
    4. Compare hashes against all songs in the database
    5. Return the best matching song(s)
    
    Args:
        db_connection: Active database connection
        snippet_path: Path to the WAV file to identify
    
    Returns:
        List of matching song titles, or empty list if no match found
    """
    
    # Generate spectrogram from the audio file
    spectrogram = audio_processing.generate_spectrogram_from_wav(snippet_path)
    
    if spectrogram is None:
        print(f"[ERROR] Unable to process snippet: {snippet_path}")
        return []

    # Unpack spectrogram data
    sample_rate, freq_bins, time_bins, power_matrix = spectrogram
    
    # Generate fingerprint hashes (same process used when building the database)
    snippet_hashes = audio_processing.generate_constellation_hashes(freq_bins, time_bins, power_matrix)

    # Compare against database and return matches
    return identify_from_hashes(db_connection, snippet_hashes)
