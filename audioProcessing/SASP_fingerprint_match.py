"""
fingerprint_match.py
--------------------
Compares two fingerprints to determine similarity using Euclidean distance.
"""

import numpy as np
from scipy.spatial import distance


def fingerprint_distance(query_fp, reference_fp, metric="euclidean"):
    """Compute a distance metric between two fingerprint windows."""

    query = np.asarray(query_fp)
    reference = np.asarray(reference_fp)

    if query.shape != reference.shape:
        raise ValueError(f"Fingerprint shapes mismatch: {query.shape} vs {reference.shape}")

    if metric == "euclidean":
        return float(distance.euclidean(query, reference))

    raise ValueError(f"Unsupported fingerprint distance metric: {metric}")


def average_distance_between_fingerprints(query_matrix, reference_matrix, metric="euclidean"):
    """Return the average distance comparing all windows of query against reference."""

    query = np.asarray(query_matrix)
    reference = np.asarray(reference_matrix)

    if query.ndim == 1:
        query = query[np.newaxis, :]
    if reference.ndim == 1:
        reference = reference[np.newaxis, :]

    min_windows = min(len(query), len(reference))
    distances = [fingerprint_distance(query[idx], reference[idx], metric=metric) for idx in range(min_windows)]

    # Penalize mismatched lengths by adding average distance of extra windows.
    # This keeps longer fingerprints from automatically winning.
    if len(query) != len(reference):
        longer = query if len(query) > len(reference) else reference
        extra_distances = [fingerprint_distance(window, longer[min_windows - 1], metric=metric) for window in longer[min_windows:]]
        distances.extend(extra_distances)

    return float(np.mean(distances))
