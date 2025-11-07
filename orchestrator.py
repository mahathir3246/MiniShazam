"""Integrates database operations with audio fingerprint processing."""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Iterable, List

import Database.database as db
from audioProcessing import (
    SASP_audio_processing as audio_processing,
    SASP_audio_utils as audio_utils,
)


def _iter_files(directory: str, suffix: str) -> Iterable[str]:
    if not os.path.isdir(directory):
        return []
    return (filename for filename in sorted(os.listdir(directory)) if filename.lower().endswith(suffix))


def construct_music_database(db_connection, mp3_directory: str = "./music/mp3", wav_directory: str = "./music/wav") -> None:
    """Populate the database by processing MP3 files and generating fingerprints."""

    db.initialize_schema(db_connection)
    print("[INFO] Database schema initialized.")

    title_to_id = {}

    for mp3_file in _iter_files(mp3_directory, ".mp3"):
        mp3_path = os.path.join(mp3_directory, mp3_file)
        track_title = os.path.splitext(mp3_file)[0]

        track_id = db.insert_track_metadata(track_title, db_connection)
        title_to_id[track_title] = track_id
        title, artist = audio_utils.parse_mp3_tags(mp3_path)
        print(f"[INFO] Stored track '{track_title}' (ID3 title='{title}', artist='{artist}').")

        audio_utils.transform_mp3_to_wav(mp3_path)

    print("[INFO] MP3 ingestion complete.")

    for wav_file in _iter_files(wav_directory, ".wav"):
        wav_path = os.path.join(wav_directory, wav_file)
        wav_title = os.path.splitext(wav_file)[0]

        spectrogram = audio_processing.generate_spectrogram_from_wav(wav_path)
        if spectrogram is None:
            print(f"[WARN] Skipping WAV without spectrogram data: {wav_path}")
            continue

        sample_rate, freq_bins, time_bins, power_matrix = spectrogram
        fingerprint_hashes = audio_processing.generate_constellation_hashes(freq_bins, time_bins, power_matrix)

        track_id = title_to_id.get(wav_title)
        if track_id is None:
            try:
                track_id = db.lookup_track_id_by_filename(wav_file, db_connection)
            except (IndexError, ValueError):
                print(f"[WARN] Missing metadata for '{wav_file}', skipping.")
                continue

        db.store_fingerprint_hashes(track_id, fingerprint_hashes, db_connection)
        db.mark_as_fingerprinted(track_id, db_connection)
        print(f"[INFO] Fingerprint stored for track_id={track_id} ({wav_file}).")

    print("[INFO] Database construction finished.")


def find_matching_track(db_connection, snippet_path: str) -> List[str]:
    """Return titles of tracks whose fingerprints best match the snippet."""

    spectrogram = audio_processing.generate_spectrogram_from_wav(snippet_path)
    if spectrogram is None:
        print(f"[ERROR] Unable to process snippet: {snippet_path}")
        return []

    sample_rate, freq_bins, time_bins, power_matrix = spectrogram
    snippet_hashes = audio_processing.generate_constellation_hashes(freq_bins, time_bins, power_matrix)

    if not snippet_hashes:
        print("[WARN] No hashes generated for snippet; unable to match.")
        return []

    hash_to_snippet_times = defaultdict(list)
    for hash_tuple, anchor_time_idx in snippet_hashes:
        hash_to_snippet_times[tuple(hash_tuple)].append(anchor_time_idx)

    max_track_id = db.get_highest_track_id(db_connection)
    if max_track_id is None:
        print("[WARN] No tracks in database.")
        return []

    vote_scores = []
    for song_id in range(1, max_track_id + 1):
        stored_hashes = db.fetch_track_signatures(db_connection, song_id)

        if not stored_hashes:
            vote_scores.append(0)
            continue

        offset_votes = defaultdict(int)

        for anchor_time_idx, signature_components in stored_hashes:
            hash_tuple = tuple(signature_components)
            snippet_times = hash_to_snippet_times.get(hash_tuple)
            if not snippet_times:
                continue

            for snippet_time in snippet_times:
                offset = anchor_time_idx - snippet_time
                offset_votes[offset] += 1

        vote_scores.append(max(offset_votes.values()) if offset_votes else 0)

    if not vote_scores:
        print("[WARN] No fingerprints stored; cannot identify snippet.")
        return []

    best_vote = max(vote_scores)
    if best_vote == 0:
        print("[INFO] No matching hashes found for snippet.")
        return []

    best_song_ids = [index + 1 for index, score in enumerate(vote_scores) if score == best_vote]

    matches = []
    for song_id in best_song_ids:
        title = db.get_track_name_by_id(song_id, db_connection)
        matches.append(title)
        print(f"[INFO] Best candidate song_id={song_id}, title='{title}', votes={best_vote}.")

    return matches

