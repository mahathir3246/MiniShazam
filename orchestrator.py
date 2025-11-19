# Main file that sums everything together - database + audio processing

from __future__ import annotations
import os
from collections import defaultdict
from typing import Iterable, List
import Database.database as db
from audioProcessing import (SASP_audio_processing as audio_processing,SASP_audio_utils as audio_utils)

# Thresholds for matching - had to tune these a bit to reduce false positives
MIN_ABSOLUTE_VOTES = 5
MIN_SNIPPET_VOTE_RATIO = 0.012
MIN_STORED_VOTE_RATIO = 0.008


# Helper to get all files with a certain extension, sorted
def _iter_files(directory: str, suffix: str) -> Iterable[str]:
    if not os.path.isdir(directory):
        return []
    matching_files = []
    for filename in sorted(os.listdir(directory)): 
        if filename.lower().endswith(suffix):
            matching_files.append(filename)
    return matching_files



def construct_music_database(db_connection, mp3_directory: str = "./music/mp3", wav_directory: str = "./music/wav") -> None:
    # Builds the database from MP3 files

    db.initialize_schema(db_connection)
    #Prints to get some info
    print("[INFO] Database schema initialized.")

    #Tracks the ID for the searches later
    title_to_id = {}

    for mp3_file in _iter_files(mp3_directory, ".mp3"):
        mp3_path = os.path.join(mp3_directory, mp3_file)
        track_title = os.path.splitext(mp3_file)[0]

        track_id = db.insert_track_metadata(track_title, db_connection)
        # Store the mapping so we can link WAV files later
        title_to_id[track_title] = track_id
        # Parse ID3 tags just for logging, not actually using them in the DB
        title, artist = audio_utils.parse_mp3_tags(mp3_path)
        print(f"[INFO] Stored track '{track_title}' (ID3 title='{title}', artist='{artist}').")
        # Convert MP3 to WAV for processing
        audio_utils.transform_mp3_to_wav(mp3_path)

    print("[INFO] MP3 ingestion complete.")

    for wav_file in _iter_files(wav_directory, ".wav"):
        wav_path = os.path.join(wav_directory, wav_file)
        # Get only the title without extension
        wav_title = os.path.splitext(wav_file)[0]

        #spectrogram
        spectrogram = audio_processing.generate_spectrogram_from_wav(wav_path)
        if spectrogram is None:
            print(f"[WARN] Skipping WAV without spectrogram data: {wav_path}")
            continue

        sample_rate, freq_bins, time_bins, power_matrix = spectrogram
        # Generate fingerprint hashes from the spectrogram
        fingerprint_hashes = audio_processing.generate_constellation_hashes(freq_bins, time_bins, power_matrix)

        # Try to find the track ID
        track_id = title_to_id.get(wav_title)
        if track_id is None:
            try:
                track_id = db.lookup_track_id_by_filename(wav_file, db_connection)
            except (IndexError, ValueError):
                print(f"[WARN] Missing metadata for '{wav_file}', skipping.")
                continue
        # Store all the fingerprint hashes for this track
        db.store_fingerprint_hashes(track_id, fingerprint_hashes, db_connection)
        # Mark this song as fully fingerprinted
        db.mark_as_fingerprinted(track_id, db_connection)
        print(f"[INFO] Fingerprint stored for track_id={track_id} ({wav_file}).")

    print("[INFO] Database construction finished.")


def identify_from_hashes(db_connection, snippet_hashes) -> List[str]:

    # Matches heard songs hashes against database and returns best matches
    # Using time offset voting (similar to how Shazam works)

    if not snippet_hashes:
        print("[WARN] No hashes generated for snippet; unable to match.")
        return []

    # list of times the hash appears in snippet
    hash_to_snippet_times = defaultdict(list)
    for hash_tuple, anchor_time_idx in snippet_hashes:
        hash_to_snippet_times[tuple(hash_tuple)].append(anchor_time_idx)

    snippet_hash_count = len(snippet_hashes)

    max_track_id = db.get_highest_track_id(db_connection)
    if max_track_id is None:
        print("[WARN] No tracks in database.")
        return []

    score_details = []
    # Check each song in the database
    for song_id in range(1, max_track_id + 1):
        stored_hashes = db.fetch_track_signatures(db_connection, song_id)

        stored_hash_count = len(stored_hashes)

        # if No matches found for this song
        if not stored_hash_count:
            score_details.append({"song_id": song_id, "votes": 0, "ratio": 0.0, "stored_ratio": 0.0, "score": 0.0})
            continue

        # This is where snippet matches a song
        offset_votes = defaultdict(int)

        for anchor_time_idx, signature_components in stored_hashes:
            hash_tuple = tuple(signature_components)
            snippet_times = hash_to_snippet_times.get(hash_tuple)
            if not snippet_times:
                continue

            # Check all matches of this hash in the snippet
            for snippet_time in snippet_times:
                offset = anchor_time_idx - snippet_time
                # Add a vote
                offset_votes[offset] += 1

        if not offset_votes:
            score_details.append({"song_id": song_id, "votes": 0, "ratio": 0.0, "stored_ratio": 0.0, "score": 0.0})
            continue

        #find the best votes
        best_vote = max(offset_votes.values())
        snippet_ratio = best_vote / snippet_hash_count

        stored_ratio = best_vote / stored_hash_count

        # Use the threshols above to filter out the worst or weak matches
        if (
            best_vote < MIN_ABSOLUTE_VOTES
            or snippet_ratio < MIN_SNIPPET_VOTE_RATIO
            or stored_ratio < MIN_STORED_VOTE_RATIO
        ):
            score_details.append({"song_id": song_id, "votes": 0, "ratio": 0.0, "stored_ratio": 0.0, "score": 0.0})
            continue

        #combine the score and store all the info for the song
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

    if not score_details:
        print("[WARN] No fingerprints stored; cannot identify snippet.")
        return []

    # Only keep songs that actually matched
    valid_scores = []
    for detail in score_details:
        if detail["votes"] > 0:
            valid_scores.append(detail)

    if not valid_scores:
        print("[INFO] No matching hashes met the confidence thresholds.")
        return []

    #find the best scoring songs
    best_score = 0.0
    for detail in valid_scores:
        if detail["score"] > best_score:
            best_score = detail["score"]

    top_candidates = []
    for detail in valid_scores:
        if detail["score"] == best_score:
            top_candidates.append(detail)

    #if multiple songs have same score, compare against most votes
    best_votes = 0
    for detail in top_candidates:
        if detail["votes"] > best_votes:
            best_votes = detail["votes"]

    best_song_ids = []
    for detail in top_candidates:
        if detail["votes"] == best_votes:
            best_song_ids.append(detail["song_id"])

    score_by_song = {}
    for detail in top_candidates:
        score_by_song[detail["song_id"]] = detail

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
    # Takes a snippet file path and finds which song it matches

    spectrogram = audio_processing.generate_spectrogram_from_wav(snippet_path)
    if spectrogram is None:
        print(f"[ERROR] Unable to process snippet: {snippet_path}")
        return []

    sample_rate, freq_bins, time_bins, power_matrix = spectrogram
    snippet_hashes = audio_processing.generate_constellation_hashes(freq_bins, time_bins, power_matrix)

    return identify_from_hashes(db_connection, snippet_hashes)

