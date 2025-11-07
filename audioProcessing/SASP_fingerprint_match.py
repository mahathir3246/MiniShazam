"""
fingerprint_match.py
--------------------
Compares two fingerprints to determine similarity using Euclidean distance.
"""

import numpy as np
from scipy.spatial import distance

def are_fingerprints_similar(fp1, fp2, similarity_threshold=0.1):
    """
    (Function) Determines if two fingerprints match within a threshold.

    Args:
        fp1: Reference fingerprint (2D array)
        fp2: Query fingerprint (2D array)
        similarity_threshold: Euclidean distance tolerance

    Returns:
        True if similar, False otherwise
    """
    fp1_array = np.array(fp1)
    fp2_array = np.array(fp2)

    if fp1_array.ndim == 1 and fp2_array.ndim == 1:
        euclidean_dist = distance.euclidean(fp1_array, fp2_array)
        return euclidean_dist < similarity_threshold

    if fp1_array.shape == fp2_array.shape:
        distances = [distance.euclidean(x, y) for x, y in zip(fp1_array, fp2_array)]
        return all(d < similarity_threshold for d in distances)

    print("[WARN] Fingerprints must have equal shapes.")
    return False
