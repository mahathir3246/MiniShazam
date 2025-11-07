"""
audio_utils.py
--------------
Handles audio format conversions (MP3 → WAV) and metadata extraction.
"""

import os

from pydub import AudioSegment
import eyed3


def transform_mp3_to_wav(input_mp3_path):
    """
    Converts an MP3 file to WAV format and saves it under ./music/wav/.
    Returns the path of the generated WAV file.
    """

    try:
        if not os.path.exists("./music/wav/"):
            os.makedirs("./music/wav/")

        base_name = os.path.basename(input_mp3_path)
        stem, _ = os.path.splitext(base_name)
        output_wav_path = os.path.join("./music/wav/", f"{stem}.wav")

        audio_track = AudioSegment.from_mp3(input_mp3_path)
        audio_track.export(output_wav_path, format="wav")

        print(f"[INFO] Converted {input_mp3_path} → {output_wav_path}")
        return output_wav_path

    except Exception as exc:
        print(f"[ERROR] Could not convert MP3 to WAV: {exc}")
        return None


def parse_mp3_tags(input_mp3_path):
    """
    Extracts title and artist from MP3 file ID3 tags.
    Returns: (title, artist)
    """

    try:
        audio_file = eyed3.load(input_mp3_path)
        if audio_file is None or audio_file.tag is None:
            raise AttributeError("No ID3 tags found.")

        title = audio_file.tag.title or "Unknown Title"
        artist = audio_file.tag.artist or "Unknown Artist"
        return title, artist

    except Exception as exc:
        print(f"[WARN] Could not read tags: {exc}")
        return "Unknown Title", "Unknown Artist"

