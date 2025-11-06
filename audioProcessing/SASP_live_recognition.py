"""
live_recognition.py
-------------------
Captures live microphone audio and performs fingerprint-based recognition.
Integrates with the rest of the Freezam pipeline.
"""

import sounddevice as sd
import numpy as np
from audio_processing import generate_spectrogram_from_array, compute_audio_fingerprint
from fingerprint_match import are_fingerprints_similar


def record_live_audio(duration=10, sample_rate=44100):
    """
    Records audio from the microphone.
    """
    print(f"[INFO] Recording for {duration} seconds...")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
    sd.wait()
    print("[INFO] Recording finished.")
    return audio.flatten(), sample_rate


def live_audio_recognition(known_fingerprints, duration=10):
    """
    Records live audio, generates fingerprint, and compares to known fingerprints.
    known_fingerprints: dict {song_title: fingerprint_matrix}
    """
    audio_data, sr = record_live_audio(duration)
    sr, freqs, times, power = generate_spectrogram_from_array(audio_data, sr)
    fingerprint = compute_audio_fingerprint(freqs, power, sr)

    for title, known_fp in known_fingerprints.items():
        if are_fingerprints_similar(fingerprint, known_fp):
            print(f"[RESULT] Match found: {title}")
            return title

    print("[RESULT] No match found.")
    return None
