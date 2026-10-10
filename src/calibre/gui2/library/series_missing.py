#!/usr/bin/env python
# License: GPLv3

import math
from collections import Counter

from calibre.gui2 import gprefs
from calibre.utils.localization import _, ngettext


def duplicate_volume_count(indices):
    """Number of positive finite indices assigned to more than one book."""
    counts = Counter()
    for value in indices:
        try:
            number = float(value)
        except TypeError, ValueError, OverflowError:
            continue
        if math.isfinite(number) and number > 0:
            counts[number] += 1
    return sum(count > 1 for count in counts.values())


def missing_volume_count(indices):
    """Lower bound from positive integer indices; no guess after the last one.

    Duplicate editions count once. Fractional and non-positive indices do not
    establish ownership of an integer volume.
    """
    owned = set()
    for value in indices:
        try:
            number = float(value)
        except TypeError, ValueError, OverflowError:
            continue
        if math.isfinite(number) and number > 0 and number.is_integer():
            owned.add(int(number))
    return max(owned, default=0) - len(owned)


def missing_series_tooltip(db, book_id):
    if not gprefs['show_missing_series_books']:
        return ''
    series_ids = db.field_ids_for('series', book_id)
    if not series_ids:
        return ''
    books = db.books_for_field('series', series_ids[0])
    indices = tuple(db.all_field_for('series_index', books).values())
    count = missing_volume_count(indices)
    messages = []
    if count:
        messages.append(ngettext('At least %d book missing', 'At least %d books missing', count) % count)
    elif len(indices) == 1 and indices[0] == 1:
        messages.append(_('At least 1 book potentially missing (only volume 1 is present)'))
    duplicates = duplicate_volume_count(indices)
    if duplicates:
        messages.append(ngettext('%d volume number appears more than once', '%d volume numbers appear more than once', duplicates) % duplicates)
    return '<br>'.join(f'<span style="color: #e53935">{text}</span>' for text in messages)
