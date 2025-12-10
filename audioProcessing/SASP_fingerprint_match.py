"""
Fingerprint Matching Module

This file provides functions to compare two audio fingerprints
and determine how similar they are.

NOTE: This is an older/alternative approach that computes direct
distance between fingerprint matrices. The main MiniShazam system
uses constellation hashes with time-offset voting instead (see
orchestrator.py), which works much better in practice.

This module is kept for reference and potential future use.

DISTANCE METRICS:
================
Euclidean distance is used by default - this is the "straight line"
distance between two points. For fingerprints, a smaller distance
means the two audio clips are more similar.
"""

import numpy as np
from scipy.spatial import distance


def fingerprint_distance(query_fp, reference_fp, metric="euclidean"):
    """
    Computes the distance between two fingerprint vectors.
    
    A fingerprint vector represents one "window" of audio - the peak
    frequencies at a single point in time. This function tells us
    how different two such windows are.
    
    SMALLER DISTANCE = MORE SIMILAR
    
    Args:
        query_fp: Fingerprint vector from the recording we're trying to identify
        reference_fp: Fingerprint vector from a known song in the database
        metric: Distance metric to use (only "euclidean" is implemented)
    
    Returns:
        A float representing the distance (0 = identical, higher = different)
    
    Raises:
        ValueError: If fingerprint shapes don't match or unknown metric used
    """
    
    # Convert to NumPy arrays for math operations
    query = np.asarray(query_fp)
    reference = np.asarray(reference_fp)

    # Both fingerprints must have the same shape to compare
    if query.shape != reference.shape:
        raise ValueError(f"Fingerprint shapes mismatch: {query.shape} vs {reference.shape}")

    # Compute Euclidean distance (straight-line distance in N-dimensional space)
    # Formula: sqrt(sum((a[i] - b[i])^2 for all i))
    if metric == "euclidean":
        return float(distance.euclidean(query, reference))

    raise ValueError(f"Unsupported fingerprint distance metric: {metric}")


def average_distance_between_fingerprints(query_matrix, reference_matrix, metric="euclidean"):
    """
    Compares two fingerprint matrices and returns their average distance.
    
    A fingerprint matrix has multiple rows, where each row is a fingerprint
    for one time window. This function compares corresponding rows and
    averages the results.
    
    HANDLING DIFFERENT LENGTHS:
    If one fingerprint is longer than the other (songs have different lengths),
    we compare what we can, then compare the extra windows against the
    last window of the shorter one.
    
    Args:
        query_matrix: Fingerprint matrix from the unknown audio [windows x features]
        reference_matrix: Fingerprint matrix from a known song [windows x features]
        metric: Distance metric to use
    
    Returns:
        Average distance across all window comparisons (float)
        Lower = more similar
    """
    
    # Convert to NumPy arrays
    query = np.asarray(query_matrix)
    reference = np.asarray(reference_matrix)

    # Handle 1D inputs (single window) by converting to 2D (1 row)
    if query.ndim == 1:
        query = query[np.newaxis, :]      # Add a dimension: (n,) -> (1, n)
    if reference.ndim == 1:
        reference = reference[np.newaxis, :]

    # Compare windows that both matrices have
    min_windows = min(len(query), len(reference))
    
    distances = [
        fingerprint_distance(query[idx], reference[idx], metric=metric)
        for idx in range(min_windows)
    ]

    # Handle extra windows in the longer matrix
    # Compare them against the last window of the shorter one
    if len(query) != len(reference):
        # Figure out which is longer
        longer = query if len(query) > len(reference) else reference
        
        # Compare extra windows against the last common window
        extra_distances = [
            fingerprint_distance(window, longer[min_windows - 1], metric=metric)
            for window in longer[min_windows:]
        ]
        distances.extend(extra_distances)

    # Return the average of all distances
    return float(np.mean(distances))
