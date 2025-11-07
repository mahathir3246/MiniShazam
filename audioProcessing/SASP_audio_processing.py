"""
audio_processing.py
-------------------
Manually computes spectrograms and fingerprints from WAV or live audio data.
"""

import numpy as np
from scipy.io import wavfile
import matplotlib
import matplotlib.pyplot as plt

MAX_PEAKS_PER_COLUMN = 5
FAN_VALUE = 5
MAX_TIME_DELTA = 20

"""
 Shared internal function 
 Computes the shared part of audio processing for both inputs: file and microphone
"""

def _compute_manual_spectrogram(audio_data, sample_rate):
    """
    Core manual STFT-based spectrogram computation shared by both entry points.
    """


    """ Normalize input """ 
    audio_data = audio_data / np.max(np.abs(audio_data))

    """ Manual STFT parameters """
    window_size = 4096
    hop_size = 2048
    window = np.hamming(window_size)

    """ Number of analysis frames """
    n_windows = (len(audio_data) - window_size) // hop_size
    spectrogram = np.zeros((window_size // 2, n_windows))

    for i in range(n_windows):
        start = i * hop_size
        frame = audio_data[start:start + window_size] * window
        spectrum = np.abs(np.fft.fft(frame))[:window_size // 2]
        spectrogram[:, i] = spectrum

    """ Convert to log power scale """
    power_matrix = np.log1p(spectrogram)
    freq_bins = np.linspace(0, sample_rate / 2, window_size // 2)
    time_windows = np.arange(n_windows) * hop_size / sample_rate

    return sample_rate, freq_bins, time_windows, power_matrix


""" WAV file entry point """ 
def generate_spectrogram_from_wav(wav_path):
    """
    Loads a WAV file, converts to mono, and computes a manual STFT-based spectrogram.
    """
    if not wav_path.endswith(".wav"):
        print("[ERROR] Expected a .wav file.")
        return None

    """ Load the WAV file """
    sample_rate, audio_data = wavfile.read(wav_path)
    print(f"[INFO] Loaded WAV file: {wav_path}")

    """ Convert to mono if stereo """
    if len(audio_data.shape) > 1:
        audio_data = np.mean(audio_data, axis=1)

    """ Delegate to shared computation """
    print("[INFO] Computing spectrogram (file input)...")
    return _compute_manual_spectrogram(audio_data, sample_rate)


""" Live array entry point """
def generate_spectrogram_from_array(audio_data, sample_rate):
    """
    Computes a manual spectrogram from NumPy audio data (used for live mic input).
    """
    print("[INFO] Computing spectrogram (live input)...")
    return _compute_manual_spectrogram(audio_data, sample_rate)


def visualize_spectrogram(freq_array, time_array, power_matrix):
    """
    Visualizes a computed spectrogram.
    """
    plt.figure(figsize=(10, 5))
    plt.pcolormesh(time_array, freq_array, power_matrix, shading='auto',
                   norm=matplotlib.colors.Normalize(vmin=0, vmax=np.max(power_matrix)))
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.title('Spectrogram')
    plt.colorbar(label='Log Power')
    plt.show()


def compute_audio_fingerprint(freq_bins, power_matrix, sample_rate):
    """
    Extracts peak frequencies per octave band.
    """
    num_octaves = 8
    base_frequency = int((2 ** -(num_octaves + 1)) * (sample_rate / 2))
    octave_fingerprints = []

    print("[INFO] Generating fingerprint...")

    for octave_idx in range(num_octaves):
        octave_start = base_frequency * (2 ** octave_idx) * 10
        octave_end = base_frequency * (2 ** (octave_idx + 1)) * 10
        octave_start = int(min(octave_start, len(freq_bins) - 1))
        octave_end = int(min(octave_end, len(freq_bins)))

        octave_freqs = freq_bins[octave_start:octave_end]
        octave_power = power_matrix[octave_start:octave_end, :]

        if len(octave_freqs) == 0:
            continue

        peak_indices = np.argmax(octave_power, axis=0)
        normalized_peaks = octave_freqs[peak_indices] / np.max(freq_bins)
        octave_fingerprints.append(normalized_peaks)

    fingerprint_matrix = np.array(octave_fingerprints).T
    print("[INFO] Fingerprint generated successfully.")
    return fingerprint_matrix


def _extract_peak_constellation(power_matrix, max_peaks=MAX_PEAKS_PER_COLUMN):
    peaks = []
    num_time_bins = power_matrix.shape[1]

    for time_idx in range(num_time_bins):
        column = power_matrix[:, time_idx]
        if not np.any(column):
            continue

        limited_peaks = min(max_peaks, len(column))
        peak_indices = np.argpartition(column, -limited_peaks)[-limited_peaks:]
        for freq_idx in peak_indices:
            peaks.append((time_idx, freq_idx, column[freq_idx]))

    peaks.sort(key=lambda entry: entry[0])
    return peaks


def generate_constellation_hashes(freq_bins, time_bins, power_matrix,
                                  max_peaks_per_column=MAX_PEAKS_PER_COLUMN,
                                  fan_value=FAN_VALUE,
                                  max_time_delta=MAX_TIME_DELTA):
    peaks = _extract_peak_constellation(power_matrix, max_peaks=max_peaks_per_column)

    hashes = []
    num_peaks = len(peaks)

    for anchor_idx in range(num_peaks):
        anchor_time_idx, anchor_freq_idx, _ = peaks[anchor_idx]

        for offset in range(1, fan_value + 1):
            target_idx = anchor_idx + offset
            if target_idx >= num_peaks:
                break

            target_time_idx, target_freq_idx, _ = peaks[target_idx]
            delta_time = target_time_idx - anchor_time_idx

            if delta_time <= 0 or delta_time > max_time_delta:
                continue

            hash_tuple = (
                int(anchor_freq_idx),
                int(target_freq_idx),
                int(delta_time),
            )

            hashes.append((hash_tuple, int(anchor_time_idx)))

    return hashes
