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

MIN_ABSOLUTE_VOTES = 5
MIN_SNIPPET_VOTE_RATIO = 0.012
MIN_STORED_VOTE_RATIO = 0.008


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


def identify_from_hashes(db_connection, snippet_hashes) -> List[str]:
    """Return titles whose stored hashes best align with the snippet hashes."""

    if not snippet_hashes:
        print("[WARN] No hashes generated for snippet; unable to match.")
        return []

    hash_to_snippet_times = defaultdict(list)
    for hash_tuple, anchor_time_idx in snippet_hashes:
        hash_to_snippet_times[tuple(hash_tuple)].append(anchor_time_idx)

    snippet_hash_count = len(snippet_hashes)

    max_track_id = db.get_highest_track_id(db_connection)
    if max_track_id is None:
        print("[WARN] No tracks in database.")
        return []

    score_details = []
    for song_id in range(1, max_track_id + 1):
        stored_hashes = db.fetch_track_signatures(db_connection, song_id)

        stored_hash_count = len(stored_hashes)

        if not stored_hash_count:
            score_details.append({"song_id": song_id, "votes": 0, "ratio": 0.0, "stored_ratio": 0.0, "score": 0.0})
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

        if not offset_votes:
            score_details.append({"song_id": song_id, "votes": 0, "ratio": 0.0, "stored_ratio": 0.0, "score": 0.0})
            continue

        best_vote = max(offset_votes.values())
        snippet_ratio = best_vote / snippet_hash_count

        stored_ratio = best_vote / stored_hash_count

        if (
            best_vote < MIN_ABSOLUTE_VOTES
            or snippet_ratio < MIN_SNIPPET_VOTE_RATIO
            or stored_ratio < MIN_STORED_VOTE_RATIO
        ):
            score_details.append({"song_id": song_id, "votes": 0, "ratio": 0.0, "stored_ratio": 0.0, "score": 0.0})
            continue

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

    valid_scores = [detail for detail in score_details if detail["votes"] > 0]
    if not valid_scores:
        print("[INFO] No matching hashes met the confidence thresholds.")
        return []

    best_score = max(detail["score"] for detail in valid_scores)
    top_candidates = [detail for detail in valid_scores if detail["score"] == best_score]

    best_votes = max(detail["votes"] for detail in top_candidates)
    best_song_ids = [detail["song_id"] for detail in top_candidates if detail["votes"] == best_votes]

    score_by_song = {detail["song_id"]: detail for detail in top_candidates}

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
    """Return titles of tracks whose fingerprints best match the snippet file."""

    spectrogram = audio_processing.generate_spectrogram_from_wav(snippet_path)
    if spectrogram is None:
        print(f"[ERROR] Unable to process snippet: {snippet_path}")
        return []

    sample_rate, freq_bins, time_bins, power_matrix = spectrogram
    snippet_hashes = audio_processing.generate_constellation_hashes(freq_bins, time_bins, power_matrix)

    return identify_from_hashes(db_connection, snippet_hashes)

