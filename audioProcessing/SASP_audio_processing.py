"""
Audio Processing Module - The Signal Processing Heart of MiniShazam

This file handles the core audio analysis:
1. Converting audio into spectrograms (visual frequency representations)
2. Extracting fingerprints (unique patterns that identify songs)
3. Generating hashes (compact codes for fast matching)

KEY CONCEPTS:
=============

SPECTROGRAM:
A spectrogram is like a "picture" of sound. It shows:
- X-axis: Time (left to right as the song plays)
- Y-axis: Frequency (low notes at bottom, high notes at top)
- Color/brightness: How loud that frequency is at that moment

STFT (Short-Time Fourier Transform):
We can't just analyze the whole song at once - we break it into small
overlapping windows (like frames of a video) and analyze each one.
This gives us frequency information at different points in time.

FINGERPRINTING:
Just like human fingerprints are unique, audio fingerprints are patterns
in the spectrogram that uniquely identify a song. We look for "peaks" -
moments where certain frequencies are much louder than their surroundings.

CONSTELLATION HASHES:
Instead of storing raw fingerprints (too much data), we create hashes
by pairing nearby peaks together. A hash contains:
- The frequency of the first peak (anchor)
- The frequency of the second peak (target)
- The time difference between them
This is extremely compact but still very distinctive!
"""

import numpy as np
from scipy.io import wavfile
import matplotlib
import matplotlib.pyplot as plt

# ============================================================================
# CONFIGURATION CONSTANTS
# These values were tuned through experimentation for best results
# ============================================================================

# Maximum number of frequency peaks to keep per time window
# Too many = more storage, possible noise. Too few = might miss important features.
MAX_PEAKS_PER_COLUMN = 5

# A peak must be at least this fraction of the column maximum to count
# This filters out quiet peaks that might just be noise
MIN_PEAK_MAG_RATIO = 0.25

# How many future peaks to pair with each anchor peak (fan-out)
# More = better matching but more storage. Less = faster but might miss matches.
FAN_VALUE = 6

# Maximum time difference (in frames) between paired peaks
# Peaks too far apart in time probably aren't related
MAX_TIME_DELTA = 20


def _compute_manual_spectrogram(audio_data, sample_rate):
    """
    Core function that computes a spectrogram from raw audio data.
    
    This implements the Short-Time Fourier Transform (STFT) manually,
    which converts audio from the time domain to the frequency domain.
    
    HOW IT WORKS:
    1. Normalize the audio (scale to -1 to +1 range)
    2. Slide a window across the audio
    3. For each window position, apply Hamming window (smooths edges)
    4. Compute FFT (Fast Fourier Transform) to get frequencies
    5. Stack all these frequency snapshots into a 2D matrix
    
    Args:
        audio_data: NumPy array of audio samples (mono)
        sample_rate: Samples per second (e.g., 44100 for CD quality)
    
    Returns:
        Tuple of (sample_rate, frequency_bins, time_windows, power_matrix)
        - frequency_bins: Array of frequency values (Hz)
        - time_windows: Array of time values (seconds)
        - power_matrix: 2D array where [freq_index, time_index] = power
    """

    # Step 1: Normalize the audio to range [-1, 1]
    # This ensures consistent analysis regardless of recording volume
    audio_data = audio_data / np.max(np.abs(audio_data))

    # Step 2: Set up STFT parameters
    window_size = 4096    # Number of samples per analysis window
                          # Larger = better frequency resolution, worse time resolution
    hop_size = 2048       # How far to move between windows (50% overlap)
                          # Overlap helps catch events that span window boundaries
    
    # Hamming window - smoothly tapers the edges of each window to zero
    # This reduces "spectral leakage" (false frequencies from sharp edges)
    window = np.hamming(window_size)

    # Step 3: Calculate how many windows we'll analyze
    n_windows = (len(audio_data) - window_size) // hop_size
    
    # Create empty spectrogram matrix
    # Rows = frequency bins (half of window_size because FFT is symmetric)
    # Columns = time windows
    spectrogram = np.zeros((window_size // 2, n_windows))

    # Step 4: Process each window
    for i in range(n_windows):
        # Extract this window's samples
        start = i * hop_size
        frame = audio_data[start:start + window_size] * window
        
        # Compute FFT (converts time samples to frequency magnitudes)
        # We only keep the first half because FFT output is symmetric for real signals
        spectrum = np.abs(np.fft.fft(frame))[:window_size // 2]
        
        # Store in our spectrogram matrix
        spectrogram[:, i] = spectrum

    # Step 5: Convert to log scale (decibels)
    # Human hearing is logarithmic - this makes the spectrogram more useful
    # log1p(x) = log(1 + x), handles zero values gracefully
    power_matrix = np.log1p(spectrogram)
    
    # Create arrays for frequency and time labels
    freq_bins = np.linspace(0, sample_rate / 2, window_size // 2)  # 0 Hz to Nyquist
    time_windows = np.arange(n_windows) * hop_size / sample_rate   # In seconds

    return sample_rate, freq_bins, time_windows, power_matrix


def generate_spectrogram_from_wav(wav_path):
    """
    Loads a WAV file and generates its spectrogram.
    
    This is the main entry point for processing audio files.
    
    Args:
        wav_path: Path to the WAV file to analyze
    
    Returns:
        Tuple of (sample_rate, freq_bins, time_bins, power_matrix)
        or None if there was an error
    """
    # Validate file extension
    if not wav_path.endswith(".wav"):
        print("[ERROR] Expected a .wav file.")
        return None

    # Load the WAV file using scipy
    # Returns: sample_rate (int) and audio_data (numpy array)
    sample_rate, audio_data = wavfile.read(wav_path)
    print(f"[INFO] Loaded WAV file: {wav_path}")

    # Convert stereo to mono if necessary
    # Stereo has shape (samples, 2), mono has shape (samples,)
    if len(audio_data.shape) > 1:
        # Average the two channels together
        audio_data = np.mean(audio_data, axis=1)

    # Compute and return the spectrogram
    print("[INFO] Computing spectrogram (file input)...")
    return _compute_manual_spectrogram(audio_data, sample_rate)


def generate_spectrogram_from_array(audio_data, sample_rate):
    """
    Generates a spectrogram from raw audio data in memory.
    
    This is used for live microphone input where we already
    have the audio data in a NumPy array (not a file).
    
    Args:
        audio_data: NumPy array of audio samples
        sample_rate: Samples per second
    
    Returns:
        Tuple of (sample_rate, freq_bins, time_bins, power_matrix)
    """
    print("[INFO] Computing spectrogram (live input)...")
    return _compute_manual_spectrogram(audio_data, sample_rate)


def visualize_spectrogram(freq_array, time_array, power_matrix):
    """
    Displays a visual plot of the spectrogram.
    
    Useful for debugging and understanding what the audio looks like.
    Colors represent loudness at each frequency/time point.
    
    Args:
        freq_array: Array of frequency values (Y-axis labels)
        time_array: Array of time values (X-axis labels)
        power_matrix: 2D array of power values (colors)
    """
    plt.figure(figsize=(10, 5))
    
    # pcolormesh creates a colored grid
    plt.pcolormesh(time_array, freq_array, power_matrix, shading='auto',
                   norm=matplotlib.colors.Normalize(vmin=0, vmax=np.max(power_matrix)))
    
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.title('Spectrogram')
    plt.colorbar(label='Log Power')
    plt.show()


def compute_audio_fingerprint(freq_bins, power_matrix, sample_rate):
    """
    Extracts a simple fingerprint based on peak frequencies per octave.
    
    NOTE: This is an older/simpler fingerprinting method.
    The constellation hash method (generate_constellation_hashes) is
    what's actually used for matching - it works much better.
    
    This divides the frequency range into octaves (like piano octaves)
    and finds the peak frequency in each octave for each time frame.
    
    Args:
        freq_bins: Array of frequency values
        power_matrix: Spectrogram data
        sample_rate: Audio sample rate
    
    Returns:
        Matrix of normalized peak frequencies per octave over time
    """
    num_octaves = 8
    base_frequency = int((2 ** -(num_octaves + 1)) * (sample_rate / 2))
    octave_fingerprints = []

    print("[INFO] Generating fingerprint...")

    # Process each octave (frequency doubles each octave)
    for octave_idx in range(num_octaves):
        # Calculate frequency range for this octave
        octave_start = base_frequency * (2 ** octave_idx) * 10
        octave_end = base_frequency * (2 ** (octave_idx + 1)) * 10
        octave_start = int(min(octave_start, len(freq_bins) - 1))
        octave_end = int(min(octave_end, len(freq_bins)))

        # Extract this octave's data from the spectrogram
        octave_freqs = freq_bins[octave_start:octave_end]
        octave_power = power_matrix[octave_start:octave_end, :]

        if len(octave_freqs) == 0:
            continue

        # Find the peak frequency for each time frame
        peak_indices = np.argmax(octave_power, axis=0)
        normalized_peaks = octave_freqs[peak_indices] / np.max(freq_bins)
        octave_fingerprints.append(normalized_peaks)

    fingerprint_matrix = np.array(octave_fingerprints).T
    print("[INFO] Fingerprint generated successfully.")
    return fingerprint_matrix


def _extract_peak_constellation(power_matrix, max_peaks=MAX_PEAKS_PER_COLUMN):
    """
    Finds the loudest frequency peaks at each time point.
    
    This creates a "constellation" - like a star map where each star
    represents a peak in the audio. These peaks are what make the
    fingerprint unique to each song.
    
    Selection criteria:
    1. Take the N loudest frequencies at each time point
    2. Filter out any that are below 25% of the loudest
    
    Args:
        power_matrix: Spectrogram data [frequency x time]
        max_peaks: Maximum peaks to keep per time column
    
    Returns:
        List of (time_index, frequency_index, magnitude) tuples
        Sorted by time
    """
    peaks = []
    num_time_bins = power_matrix.shape[1]

    # Process each time column
    for time_idx in range(num_time_bins):
        column = power_matrix[:, time_idx]
        
        # Skip empty columns
        if not np.any(column):
            continue

        # Find the maximum value in this column
        column_max = float(np.max(column))
        if column_max <= 0:
            continue

        # Find indices of the N largest values
        # argpartition is faster than full sort when we only need top N
        limited_peaks = min(max_peaks, len(column))
        peak_indices = np.argpartition(column, -limited_peaks)[-limited_peaks:]
        
        # Only keep peaks that are at least 25% of the maximum
        magnitude_threshold = column_max * MIN_PEAK_MAG_RATIO

        for freq_idx in peak_indices:
            magnitude = float(column[freq_idx])
            if magnitude < magnitude_threshold:
                continue
            peaks.append((time_idx, freq_idx, magnitude))

    # Sort by time for consistent processing
    peaks.sort(key=lambda entry: entry[0])
    return peaks


def generate_constellation_hashes(freq_bins, time_bins, power_matrix,
                                  max_peaks_per_column=MAX_PEAKS_PER_COLUMN,
                                  fan_value=FAN_VALUE,
                                  max_time_delta=MAX_TIME_DELTA):
    """
    THE KEY FUNCTION: Generates fingerprint hashes from a spectrogram.
    
    This implements the "constellation map" algorithm used by Shazam.
    
    HOW IT WORKS:
    1. Find all peaks in the spectrogram (constellation points)
    2. For each peak (anchor), pair it with the next few peaks (targets)
    3. Create a hash from: anchor_freq + target_freq + time_delta
    4. Store each hash with its anchor time position
    
    WHY THIS WORKS:
    - The hash captures a relationship between two peaks
    - This relationship is the same no matter when in the song you start
    - Background noise adds random peaks, but the song's peaks are consistent
    - When matching, we look for hashes with consistent time offsets
    
    Args:
        freq_bins: Array of frequency values (not directly used, kept for API)
        time_bins: Array of time values (not directly used, kept for API)
        power_matrix: Spectrogram data [frequency x time]
        max_peaks_per_column: Max peaks per time frame
        fan_value: How many forward peaks to pair with each anchor
        max_time_delta: Maximum time gap between paired peaks
    
    Returns:
        List of (hash_tuple, anchor_time_index) pairs
        hash_tuple = (anchor_freq_idx, target_freq_idx, time_delta)
    """
    
    # Step 1: Extract all peaks from the spectrogram
    peaks = _extract_peak_constellation(power_matrix, max_peaks=max_peaks_per_column)

    hashes = []
    num_peaks = len(peaks)

    # Step 2: Create hashes by pairing each peak with nearby future peaks
    for anchor_idx in range(num_peaks):
        anchor_time_idx, anchor_freq_idx, _ = peaks[anchor_idx]

        # Pair with the next 'fan_value' peaks (fan-out)
        for offset in range(1, fan_value + 1):
            target_idx = anchor_idx + offset
            
            # Don't go past the end of our peaks list
            if target_idx >= num_peaks:
                break

            target_time_idx, target_freq_idx, _ = peaks[target_idx]
            
            # Calculate time difference
            delta_time = target_time_idx - anchor_time_idx

            # Skip if time delta is invalid
            # Must be positive (target after anchor) and not too far
            if delta_time <= 0 or delta_time > max_time_delta:
                continue

            # Create the hash tuple
            # This compact representation captures the relationship between peaks
            hash_tuple = (
                int(anchor_freq_idx),   # What frequency was the anchor at?
                int(target_freq_idx),   # What frequency was the target at?
                int(delta_time),        # How far apart in time?
            )

            # Store hash with its position in time (for offset voting later)
            hashes.append((hash_tuple, int(anchor_time_idx)))

    # Remove duplicates while preserving order
    unique_hashes = list(dict.fromkeys(hashes))
    
    return unique_hashes
