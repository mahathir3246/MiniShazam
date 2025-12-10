"""
Audio Utilities Module

This file provides helper functions for working with audio files:
1. Converting MP3 files to WAV format
2. Reading ID3 metadata tags (artist, title) from MP3 files

WHY CONVERT MP3 TO WAV?
=======================
MP3 is a compressed format - great for storage and sharing, but the
compression removes some audio data. WAV is uncompressed, containing
the raw audio samples, which makes it easier to analyze accurately.

Our audio processing algorithms work directly with the sample values,
so WAV format is much more convenient to work with.

DEPENDENCIES:
- pydub: For audio format conversion (uses ffmpeg under the hood)
- eyed3: For reading MP3 metadata tags
"""

import os
from pydub import AudioSegment
import eyed3


def transform_mp3_to_wav(input_mp3_path):
    """
    Converts an MP3 file to WAV format.
    
    The WAV file is saved in ./music/wav/ with the same name as the
    original MP3 file (just with .wav extension instead of .mp3).
    
    EXAMPLE:
        Input:  ./music/mp3/MySong.mp3
        Output: ./music/wav/MySong.wav
    
    Args:
        input_mp3_path: Full path to the MP3 file to convert
    
    Returns:
        The path to the created WAV file, or None if conversion failed
    
    NOTE: This requires ffmpeg to be installed on your system.
    On Mac: brew install ffmpeg
    On Ubuntu: sudo apt install ffmpeg
    On Windows: Download from ffmpeg.org
    """

    try:
        # Create the output directory if it doesn't exist
        if not os.path.exists("./music/wav/"):
            os.makedirs("./music/wav/")

        # Extract the filename without path and extension
        # Example: "/path/to/MySong.mp3" -> "MySong"
        base_name = os.path.basename(input_mp3_path)  # "MySong.mp3"
        stem, _ = os.path.splitext(base_name)          # "MySong"
        
        # Build the output path
        output_wav_path = os.path.join("./music/wav/", f"{stem}.wav")

        # Load the MP3 file using pydub
        # AudioSegment handles all the complexity of reading MP3
        audio_track = AudioSegment.from_mp3(input_mp3_path)
        
        # Export as WAV format
        # WAV is uncompressed, so this will be larger than the MP3
        audio_track.export(output_wav_path, format="wav")

        print(f"[INFO] Converted {input_mp3_path} → {output_wav_path}")
        return output_wav_path

    except Exception as exc:
        # Common errors:
        # - ffmpeg not installed
        # - File doesn't exist
        # - Invalid MP3 file
        print(f"[ERROR] Could not convert MP3 to WAV: {exc}")
        return None


def parse_mp3_tags(input_mp3_path):
    """
    Reads the ID3 metadata tags from an MP3 file.
    
    ID3 tags are metadata stored inside MP3 files that can include:
    - Title: The song name
    - Artist: Who performed/created the song
    - Album: Which album it's from
    - Year: When it was released
    - And more...
    
    NOTE: In MiniShazam, we actually use the filename as the title
    (not the ID3 tag), because filenames are more reliable.
    This function is mainly for logging/debugging.
    
    Args:
        input_mp3_path: Path to the MP3 file
    
    Returns:
        A tuple of (title, artist) strings
        Returns ("Unknown Title", "Unknown Artist") if tags can't be read
    """

    try:
        # Load the MP3 file with eyed3
        audio_file = eyed3.load(input_mp3_path)
        
        # Check if the file loaded and has tags
        if audio_file is None or audio_file.tag is None:
            raise AttributeError("No ID3 tags found.")

        # Extract title and artist, with fallbacks
        title = audio_file.tag.title or "Unknown Title"
        artist = audio_file.tag.artist or "Unknown Artist"
        
        return title, artist

    except Exception as exc:
        # Common errors:
        # - File not found
        # - File is corrupted
        # - No ID3 tags present
        print(f"[WARN] Could not read tags: {exc}")
        return "Unknown Title", "Unknown Artist"
