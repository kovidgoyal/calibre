#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import unpack_from
from functools import partial

from calibre.utils.fonts.sfnt import UnknownTable, FixedProperty
from calibre.utils.fonts.sfnt.errors import UnsupportedFont
from calibre.utils.fonts.sfnt.common import (ScriptListTable, FeatureListTable,
        SimpleListTable, LookupTable, ExtensionSubstitution,
        UnknownLookupSubTable)

class SingleSubstitution(UnknownLookupSubTable):

    formats = {1, 2}

    def initialize(self, data):
        if self.format == 1:
            self.delta = data.unpack('h')
        else:
            count = data.unpack('H')
            self.substitutes = data.unpack('%dH'%count, single_special=False)

    def all_substitutions(self, glyph_ids):
        gid_index_map = self.coverage.coverage_indices(glyph_ids)
        if self.format == 1:
            return {gid + self.delta for gid in gid_index_map}
        return {self.substitutes[i] for i in gid_index_map.itervalues()}

class MultipleSubstitution(UnknownLookupSubTable):

    formats = {1}

    def initialize(self, data):
        self.coverage_to_subs_map = self.read_sets(data, set_is_index=True)

    def all_substitutions(self, glyph_ids):
        gid_index_map = self.coverage.coverage_indices(glyph_ids)
        ans = set()
        for index in gid_index_map.itervalues():
            glyphs = set(self.coverage_to_subs_map[index])
            ans |= glyphs
        return ans

class AlternateSubstitution(MultipleSubstitution):
    pass

class LigatureSubstitution(UnknownLookupSubTable):

    formats = {1}

    def initialize(self, data):
        self.coverage_to_lig_map = self.read_sets(data, self.read_ligature)

    def read_ligature(self, data):
        lig_glyph, count = data.unpack('HH')
        components = data.unpack('%dH'%(count-1), single_special=False)
        return (lig_glyph, components)

    def all_substitutions(self, glyph_ids):
        gid_index_map = self.coverage.coverage_indices(glyph_ids)
        ans = set()
        for start_glyph_id, index in gid_index_map.iteritems():
            for glyph_id, components in self.coverage_to_lig_map[index]:
                components = (start_glyph_id,) + (components)
                if set(components).issubset(glyph_ids):
                    ans.add(glyph_id)
        return ans

class ContexttualSubstitution(UnknownLookupSubTable):

    formats = {1, 2, 3}

    @property
    def has_initial_coverage(self):
        return self.format != 3

    def initialize(self, data):
        pass # TODO

    def all_substitutions(self, glyph_ids):
        # This table only defined substitution in terms of other tables
        return set()


class ChainingContextualSubstitution(UnknownLookupSubTable):

    formats = {1, 2, 3}

    @property
    def has_initial_coverage(self):
        return self.format != 3

    def initialize(self, data):
        pass # TODO

    def all_substitutions(self, glyph_ids):
        # This table only defined substitution in terms of other tables
        return set()

class ReverseChainSingleSubstitution(UnknownLookupSubTable):

    formats = {1}

    def initialize(self, data):
        backtrack_count = data.unpack('H')
        backtrack_offsets = data.unpack('%dH'%backtrack_count,
                single_special=False)
        lookahead_count = data.unpack('H')
        lookahead_offsets = data.unpack('%dH'%lookahead_count,
                single_special=False)
        backtrack_offsets = [data.start_pos + x for x in backtrack_offsets]
        lookahead_offsets = [data.start_pos + x for x in lookahead_offsets]
        backtrack_offsets, lookahead_offsets # TODO: Use these
        count = data.unpack('H')
        self.substitutes = data.unpack('%dH'%count)

    def all_substitutions(self, glyph_ids):
        gid_index_map = self.coverage.coverage_indices(glyph_ids)
        return {self.substitutes[i] for i in gid_index_map.itervalues()}

subtable_map = {
        1: SingleSubstitution,
        2: MultipleSubstitution,
        3: AlternateSubstitution,
        4: LigatureSubstitution,
        5: ContexttualSubstitution,
        6: ChainingContextualSubstitution,
        8: ReverseChainSingleSubstitution,
}

class GSUBLookupTable(LookupTable):

    def set_child_class(self):
        if self.lookup_type == 7:
            self.child_class = partial(ExtensionSubstitution,
                    subtable_map=subtable_map)
        else:
            self.child_class = subtable_map[self.lookup_type]

class LookupListTable(SimpleListTable):

    child_class = GSUBLookupTable

class GSUBTable(UnknownTable):

    version = FixedProperty('_version')

    def decompile(self):
        (self._version, self.scriptlist_offset, self.featurelist_offset,
                self.lookuplist_offset) = unpack_from(b'>L3H', self.raw)
        if self._version != 0x10000:
            raise UnsupportedFont('The GSUB table has unknown version: 0x%x'%
                    self._version)

        self.script_list_table = ScriptListTable(self.raw,
                self.scriptlist_offset)
        # self.script_list_table.dump()

        self.feature_list_table = FeatureListTable(self.raw,
                self.featurelist_offset)
        # self.feature_list_table.dump()

        self.lookup_list_table = LookupListTable(self.raw,
                self.lookuplist_offset)

    def all_substitutions(self, glyph_ids):
        ans = set()
        glyph_ids = frozenset(glyph_ids)
        for lookup_table in self.lookup_list_table:
            for subtable in lookup_table:
                gids = subtable.all_substitutions(glyph_ids)
                ans |= gids
        return ans

