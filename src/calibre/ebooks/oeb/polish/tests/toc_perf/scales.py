#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
'''Shared TOC scale / fanout specifications for check and convert perf tests.'''

from __future__ import annotations

from typing import NamedTuple

# Seed for reproducible generators
SEED = 20261115

# Scale name → TOC entry count N
SCALES: dict[str, int] = {
    'Tiny': 20,
    'S': 100,
    'M': 500,
    'L': 2000,
    'XL': 8000,
}


class Fanout(NamedTuple):
    '''Per-level fanout for a depth-3 TOC tree.

    For N divisible by 100: L1=10, L2=10, L3=N/100.
    Tiny (N=20): L1=2, L2=2, L3=5.

    N is the scale parameter (= l1*l2*l3 leaf slots). Every L1/L2/L3 node is a
    TOC entry, so total_entries = l1 + l1*l2 + l1*l2*l3.
    '''

    l1: int
    l2: int
    l3: int

    @property
    def leaf_n(self) -> int:
        return self.l1 * self.l2 * self.l3

    @property
    def total_entries(self) -> int:
        return self.l1 + self.l1 * self.l2 + self.l1 * self.l2 * self.l3

    # Back-compat alias used by older notes: N ≈ leaf product
    @property
    def n(self) -> int:
        return self.leaf_n


def fanout_for(n: int) -> Fanout:
    if n == 20:
        return Fanout(2, 2, 5)
    if n % 100 != 0:
        raise ValueError(f'TOC scale N={n} must be divisible by 100 (or Tiny=20)')
    return Fanout(10, 10, n // 100)


def scale_n(name: str) -> int:
    try:
        return SCALES[name]
    except KeyError as e:
        raise KeyError(f'Unknown scale {name!r}; known: {sorted(SCALES)}') from e
