# -*- coding: utf-8 -*-
"""Permutation test based corrections for multiple testing.

Author: Tuomas Puoliväli
Email: tuomas.puolivali@helsinki.fi
Last modified: 3rd August 2018
License: Revised 3-clause BSD

TODO:

- Permutation testing for (time, sensor) tuples.
- Permutation testing for (time, frequency) tuples.
- Permutation testing for (time, dipole) tuples.

The definition of adjacency can be different in each case and needs to be
thought first. In [1] the authors chose <= 4 cm distance for two (time,
sensor) tuples to be adjacent.

References:

[1] Maris E, Oostenveld R (2007): Nonparametric statistical testing of EEG-
    and MEG-data. Journal of Neuroscience Methods 164(1):177-190.

[2] Bullmore E, Suckling J, Overmeyer S, Rabe-Hesketh S, Taylor E, Brammer M
    (1999): Global, voxel, and cluster tests, by theory and permutation, for
    a difference between two groups of structural MR images of the brain.
    IEEE Transactions on Medical Imaging 18:32-42.

WARNING: work in progress.

"""

import numpy as np
from numpy import arange
from numpy.random import permutation

from scipy.stats import ttest_ind

def _sensor_adjacency(raw, threshold=4):
    """Function for computing sensor adjacencies using Euclidean distance.
    The default 4 cm threshold is the one chosen in reference [1].

    Input arguments:
    ================
    raw : mne.io.Raw
      MNE-Python raw data file object.
    threshold : float
      Maximum distance between two sensors for being adjacent.
    """

    """Get channel names and locations."""
    loc = np.asarray([ch['loc'][0:3] for ch in raw.info['chs']],
                     dtype='float')
    ch_names = np.asarray([ch['ch_name'] for ch in raw.info['chs']])

    """For each channel, find names of the adjacent channels."""
    adjacent = []
    for i, _ in enumerate(ch_names):
        distance = np.sum((loc - loc[i, :]) ** 2, axis=1)
        adjacent.append(ch_names[(distance < threshold) & (distance > 1e-5)])

    return adjacent

def _cluster_time_frequency():
    """Cluster time-frequency tuples."""

    clusters = np.zeros([n_frequencies, n_samples])
    cluster_number = 1

    """Perform the clustering."""
    for i in np.arange(0, n_frequencies):
        for j in np.arange(0, n_samples):
            """If the time-frequency tuple has been already assigned a value
            earlier, move on."""
            if (X[i, j] > 0):
                continue

            """Add the tuple to the search queue. Iterate through neighboring
            tuples recursively."""
            q = list([i, j])
            while q:
                t = q[0]
                # TODO: search
                q = q.remove(t)

            """Update cluster number."""
            cluster_number += 1

    return clusters

def _cluster_spatiotemporal():
    """Cluster data based on spatio-temporal adjacency."""
    clusters = np.zeros([n_sensors, n_samples], dtype='int')
    adjacent_sensors = _sensor_adjacency(raw, sensor_adjacency_threshold)

def _cluster_by_adjacency(sel_samples):
    """Function for clustering selected samples based on temporal adjacency.

    Input arguments:
    sel_samples - A vector of booleans indicating which samples have been
                  selected.

    Output arguments:
    clusters    - A vector of cluster numbers indicating to which cluster
                  each sample belongs to. The cluster number zero corresponds
                  to samples that were not selected.
    """
    clusters = np.zeros(len(sel_samples), dtype='int')
    cluster_number = 1 # Next cluster number.
    for i, s in enumerate(sel_samples):
        if (s == True):
            clusters[i] = cluster_number
        else:
            # Update the cluster number at temporal discontinuities.
            if (i > 0 and sel_samples[i-1] == True):
                cluster_number += 1
    return clusters

def _cluster_stat(stat, clusters, statistic='cluster_mass'):
    """Function for computing the cluster mass statistic.

    Input arguments:
    stat      - Student's T or some other statistic for each variable.
    clusters  - A vector of cluster numbers grouping the test statistics.
    statistic - The computed cluster-level statistic. For now the only
                available option is 'cluster_mass' [2]. TODO: implement
                alternatives.

    Output arguments:
    cstat    - The cluster mass statistic.
    """
    if (statistic == 'cluster_mass'):
        n_clusters = np.max(clusters)
        if (n_clusters == 0):
            return 0
        else:
            cstat = [np.sum(stat[clusters == i]) for i in
                                                 arange(1, n_clusters+1)]
            return cstat
    else:
        raise NotImplementedError('Option \'%s\' for input argument' +
                                  ' is not available' % statistic)

def permutation_test(X, Y, n_permutations=1000, threshold=1, tail='both',
                     alpha=0.05):
    """Permutation test for a significant difference between two sets of data.

    Input arguments:
    X              - An N_1-by-m matrix (NumPy ndarray) where N is the number
                     of samples and m is the number of variables. The first
                     group of data.
    Y              - An N_2-by-m matrix. The second group of data.
    n_permutations - Number of permutations. Consider how accurate p-value
                     is needed.
    threshold      -
    tail           - Only two-sided tests are supported for the moment (i.e.
                     tail = 'both').
    alpha          - The desired critical level.

    Output arguments:
    """

    """Find the number of samples in each of the two sets of data."""
    (n_samples_x, n_vars_x), (n_samples_y, _) = np.shape(X), np.shape(Y)
    n_total = n_samples_x + n_samples_y

    """Do an independent two-sample t-test for each variable using the
    original unpermuted data. Compute the cluster mass statistic that is
    compared to the permutation distribution."""
    ref_tstat, _ = ttest_ind(X, Y)
    ref_clusters = _cluster_by_adjacency(ref_tstat > threshold)
    ref_cstat = _cluster_stat(ref_tstat, ref_clusters)

    """Combine the two sets of data."""
    Z = np.vstack([X, Y])

    """Compute the permutation distribution."""
    cstat = np.zeros(n_permutations)

    for p in arange(0, n_permutations):
        """Do a random partition of the data."""
        permuted_ind = permutation(arange(n_total))
        T, U = Z[permuted_ind[0:n_samples_x], :], Z[permuted_ind[n_samples_x:], :]

        """Compute the test statistics and perform the clustering."""
        tstat, _ = ttest_ind(T, U)
        clusters = _cluster_by_adjacency(tstat > threshold)

        """Compute cluster-level statistics."""
        cstat[p] = np.max(_cluster_stat(tstat, clusters))

    """Compute p-values for each cluster. Make a vector indicating which
    variables are significant."""
    pvals = [np.sum(cstat > c) / float(n_permutations) for c in ref_cstat]

    # Find significant variables.
    significant_clusters = [i for i, p in enumerate(pvals) if p < alpha]
    significant = np.zeros([n_vars_x, 1], dtype='bool')
    for c in significant_clusters:
        significant[ref_clusters == c] = True

    return significant, pvals, cstat, ref_cstat, ref_clusters
