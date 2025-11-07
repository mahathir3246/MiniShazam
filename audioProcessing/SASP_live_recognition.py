"""Live microphone recognition using constellation-hash voting."""

from __future__ import annotations

import sounddevice as sd

from audioProcessing import SASP_audio_processing as audio_processing
import orchestrator


def record_live_audio(duration: int = 10, sample_rate: int = 44_100):
    """Record mono audio from the default microphone."""

    print(f"[INFO] Recording for {duration} seconds...")
    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    print("[INFO] Recording finished.")
    return audio.flatten(), sample_rate


def live_audio_recognition(db_connection, duration: int = 20):
    """Capture audio and match against the database using hash voting."""

    audio_data, sr = record_live_audio(duration)
    sr, freq_bins, time_bins, power_matrix = audio_processing.generate_spectrogram_from_array(audio_data, sr)
    snippet_hashes = audio_processing.generate_constellation_hashes(freq_bins, time_bins, power_matrix)

    matches = orchestrator.identify_from_hashes(db_connection, snippet_hashes)

    if matches:
        print(f"[RESULT] Live match: {matches[0]}")
        return matches[0]

    print("[RESULT] No match found.")
    return None
