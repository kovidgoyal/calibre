/*
 * sfntly.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define _UNICODE
#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "sfntly.h"

#include <new>

#include <sfntly/port/memory_input_stream.h>
#include <sfntly/port/memory_output_stream.h>

static PyObject *Error = NULL;
static PyObject *NoGlyphs = NULL;

// Predicates {{{
CompositePredicate::CompositePredicate(IntegerSet &chars, IntegerList &ranges) : 
    chars(chars), ranges(ranges) {}

CompositePredicate::~CompositePredicate() {}

bool CompositePredicate::operator()(int32_t character) const {
    for (size_t i = 0; i < ranges.size()/2; i++) {
        if (ranges[2*i] <= character && character <= ranges[2*i+1]) return true;
    }
    return chars.count(character) > 0;
}

// }}}

// Font Info {{{

GlyphId::GlyphId(int32_t glyph_id, FontId font_id) : glyph_id_(glyph_id), font_id_(font_id) {}

GlyphId::~GlyphId() {}

bool GlyphId::operator==(const GlyphId& other) const { return glyph_id_ == other.glyph_id(); }

bool GlyphId::operator<(const GlyphId& other) const { return glyph_id_ < other.glyph_id(); }

int32_t GlyphId::glyph_id() const { return glyph_id_; }

void GlyphId::set_glyph_id(const int32_t glyph_id) { glyph_id_ = glyph_id; }

FontId GlyphId::font_id() const { return font_id_; }

void GlyphId::set_font_id(const FontId font_id) { font_id_ = font_id; }

FontInfo::FontInfo() : chars_to_glyph_ids_(new CharacterMap), 
    resolved_glyph_ids_(new GlyphIdSet), fonts_(new FontIdMap) { }

FontInfo::FontInfo(CharacterMap* chars_to_glyph_ids,
        GlyphIdSet* resolved_glyph_ids,
        FontIdMap* fonts) {
    chars_to_glyph_ids_ = new CharacterMap(chars_to_glyph_ids->begin(),
            chars_to_glyph_ids->end());
    resolved_glyph_ids_ = new GlyphIdSet(resolved_glyph_ids->begin(),
            resolved_glyph_ids->end());
    fonts_ = new FontIdMap(fonts->begin(), fonts->end());
}

FontInfo::~FontInfo() {
    delete chars_to_glyph_ids_;
    delete resolved_glyph_ids_;
    delete fonts_;
}

FontDataTable* FontInfo::GetTable(FontId font_id, int32_t tag) {
    if (!fonts_)
        return NULL;
    FontIdMap::iterator it = fonts_->find(font_id);
    if (it == fonts_->end())
        return NULL;
    return it->second->GetTable(tag);
}

const TableMap* FontInfo::GetTableMap(FontId font_id) {
    if (!fonts_)
        return NULL;
    FontIdMap::iterator it = fonts_->find(font_id);
    if (it == fonts_->end())
        return NULL;
    return it->second->GetTableMap();
}

CharacterMap* FontInfo::chars_to_glyph_ids() const { return chars_to_glyph_ids_; }

void FontInfo::set_chars_to_glyph_ids(CharacterMap* chars_to_glyph_ids) {  *chars_to_glyph_ids_ = *chars_to_glyph_ids; }

GlyphIdSet* FontInfo::resolved_glyph_ids() const { return resolved_glyph_ids_; }

void FontInfo::set_resolved_glyph_ids(GlyphIdSet* resolved_glyph_ids) { *resolved_glyph_ids_ = *resolved_glyph_ids; }

FontIdMap* FontInfo::fonts() const { return fonts_; }

void FontInfo::set_fonts(FontIdMap* fonts) {   *fonts_ = *fonts; }

FontSourcedInfoBuilder::FontSourcedInfoBuilder(Font* font, FontId font_id) : font_(font), font_id_(font_id),
predicate_(NULL) { Initialize(); }

FontSourcedInfoBuilder::FontSourcedInfoBuilder(Font* font,
        FontId font_id,
        CharacterPredicate* predicate) : 
    font_(font), font_id_(font_id), predicate_(predicate) { Initialize(); }

FontSourcedInfoBuilder::~FontSourcedInfoBuilder() { }

CALLER_ATTACH FontInfo* FontSourcedInfoBuilder::GetFontInfo() {
    CharacterMap* chars_to_glyph_ids = new CharacterMap;
    bool success = GetCharacterMap(chars_to_glyph_ids);
    if (!success) {
        delete chars_to_glyph_ids;
        PyErr_SetString(Error, "Error creating character map.\n");
        return NULL;
    }
    GlyphIdSet* resolved_glyph_ids = new GlyphIdSet;
    success = ResolveCompositeGlyphs(chars_to_glyph_ids, resolved_glyph_ids);
    if (!success) {
        delete chars_to_glyph_ids;
        delete resolved_glyph_ids;
        PyErr_SetString(Error, "Error resolving composite glyphs.\n");
        return NULL;
    }
    Ptr<FontInfo> font_info = new FontInfo;
    font_info->set_chars_to_glyph_ids(chars_to_glyph_ids);
    font_info->set_resolved_glyph_ids(resolved_glyph_ids);
    FontIdMap* font_id_map = new FontIdMap;
    font_id_map->insert(std::make_pair(font_id_, font_));
    font_info->set_fonts(font_id_map);
    delete chars_to_glyph_ids;
    delete resolved_glyph_ids;
    delete font_id_map;
    return font_info.Detach();
}

bool FontSourcedInfoBuilder::GetCharacterMap(CharacterMap* chars_to_glyph_ids) {
    if (!cmap_ || !chars_to_glyph_ids)
        return false;
    chars_to_glyph_ids->clear();
    CMapTable::CMap::CharacterIterator* character_iterator = cmap_->Iterator();
    if (!character_iterator)
        return false;
    while (character_iterator->HasNext()) {
        int32_t character = character_iterator->Next();
        if (!predicate_ || (*predicate_)(character)) {
            chars_to_glyph_ids->insert
                (std::make_pair(character,
                                GlyphId(cmap_->GlyphId(character), font_id_)));
        }
    }
    delete character_iterator;
    return true;
}

bool FontSourcedInfoBuilder::ResolveCompositeGlyphs(CharacterMap* chars_to_glyph_ids,
        GlyphIdSet* resolved_glyph_ids) {
    if (!chars_to_glyph_ids || !resolved_glyph_ids)
        return false;
    resolved_glyph_ids->clear();
    resolved_glyph_ids->insert(GlyphId(0, font_id_));
    IntegerSet* unresolved_glyph_ids = new IntegerSet;
    // Since composite glyph elements might themselves be composite, we would need
    // to recursively resolve the elements too. To avoid the recursion we
    // create two sets, |unresolved_glyph_ids| for the unresolved glyphs,
    // initially containing all the ids and |resolved_glyph_ids|, initially empty.
    // We'll remove glyph ids from |unresolved_glyph_ids| until it is empty and,
    // if the glyph is composite, add its elements to the unresolved set.
    for (CharacterMap::iterator it = chars_to_glyph_ids->begin(),
            e = chars_to_glyph_ids->end(); it != e; ++it) {
        unresolved_glyph_ids->insert(it->second.glyph_id());
    }
    // As long as there are unresolved glyph ids.
    while (!unresolved_glyph_ids->empty()) {
        // Get the corresponding glyph.
        int32_t glyph_id = *(unresolved_glyph_ids->begin());
        unresolved_glyph_ids->erase(unresolved_glyph_ids->begin());
        if (glyph_id < 0 || glyph_id > loca_table_->num_glyphs()) {
            continue;
        }
        int32_t length = loca_table_->GlyphLength(glyph_id);
        if (length == 0) {
            continue;
        }
        int32_t offset = loca_table_->GlyphOffset(glyph_id);
        GlyphPtr glyph;
        glyph.Attach(glyph_table_->GetGlyph(offset, length));
        if (glyph == NULL) {
            continue;
        }
        // Mark the glyph as resolved.
        resolved_glyph_ids->insert(GlyphId(glyph_id, font_id_));
        // If it is composite, add all its components to the unresolved glyph set.
        if (glyph->GlyphType() == GlyphType::kComposite) {
            Ptr<GlyphTable::CompositeGlyph> composite_glyph =
                down_cast<GlyphTable::CompositeGlyph*>(glyph.p_);
            int32_t num_glyphs = composite_glyph->NumGlyphs();
            for (int32_t i = 0; i < num_glyphs; ++i) {
                int32_t glyph_id = composite_glyph->GlyphIndex(i);
                if (resolved_glyph_ids->find(GlyphId(glyph_id, -1))
                        == resolved_glyph_ids->end()) {
                    unresolved_glyph_ids->insert(glyph_id);
                }
            }
        }
    }
    delete unresolved_glyph_ids;
    return true;
}

void FontSourcedInfoBuilder::Initialize() {
    Ptr<CMapTable> cmap_table = down_cast<CMapTable*>(font_->GetTable(Tag::cmap));
    // We prefer Windows BMP format 4 cmaps.
    cmap_.Attach(cmap_table->GetCMap(CMapTable::WINDOWS_BMP));
    // But if none is found,
    if (!cmap_) {
        return;
    }
    loca_table_ = down_cast<LocaTable*>(font_->GetTable(Tag::loca));
    glyph_table_ = down_cast<GlyphTable*>(font_->GetTable(Tag::glyf));
}


// }}}

// Font Assembler {{{

FontAssembler::FontAssembler(FontInfo* font_info, IntegerSet* table_blacklist)    : 
    table_blacklist_(table_blacklist) {
        font_info_ = font_info;
        Initialize();
    }

FontAssembler::FontAssembler(FontInfo* font_info) : table_blacklist_(NULL) {
    font_info_ = font_info;
    Initialize();
}

FontAssembler::~FontAssembler() { }

// Assemble a new font from the font info object.
CALLER_ATTACH Font* FontAssembler::Assemble() {
    // Assemble tables we can subset.
    if (!AssembleCMapTable() || !AssembleGlyphAndLocaTables()) {
        return NULL;
    }
    // For all other tables, either include them unmodified or don't at all.
    const TableMap* common_table_map =
        font_info_->GetTableMap(font_info_->fonts()->begin()->first);
    for (TableMap::const_iterator it = common_table_map->begin(),
            e = common_table_map->end(); it != e; ++it) {
        if (table_blacklist_
                && table_blacklist_->find(it->first) != table_blacklist_->end()) {
            continue;
        }
        font_builder_->NewTableBuilder(it->first, it->second->ReadFontData());
    }
    return font_builder_->Build();
}

IntegerSet* FontAssembler::table_blacklist() const { return table_blacklist_; }

void FontAssembler::set_table_blacklist(IntegerSet* table_blacklist) {
    table_blacklist_ = table_blacklist;
}

bool FontAssembler::AssembleCMapTable() {
    // Creating the new CMapTable and the new format 4 CMap
    Ptr<CMapTable::Builder> cmap_table_builder =
        down_cast<CMapTable::Builder*>
        (font_builder_->NewTableBuilder(Tag::cmap));
    if (!cmap_table_builder)
        return false;
    Ptr<CMapTable::CMapFormat4::Builder> cmap_builder =
        down_cast<CMapTable::CMapFormat4::Builder*>
        (cmap_table_builder->NewCMapBuilder(CMapFormat::kFormat4,
                                            CMapTable::WINDOWS_BMP));
    if (!cmap_builder)
        return false;
    // Creating the segments and the glyph id array
    CharacterMap* chars_to_glyph_ids = font_info_->chars_to_glyph_ids();
    SegmentList* segment_list = new SegmentList;
    IntegerList* glyph_id_array = new IntegerList;
    int32_t last_chararacter = -2;
    int32_t last_offset = 0;
    Ptr<CMapTable::CMapFormat4::Builder::Segment> current_segment;

    // For simplicity, we will have one segment per contiguous range.
    // To test the algorithm, we've replaced the original CMap with the CMap
    // generated by this code without removing any character.
    // Tuffy.ttf: CMap went from 3146 to 3972 bytes (1.7% to 2.17% of file)
    // AnonymousPro.ttf: CMap went from 1524 to 1900 bytes (0.96% to 1.2%)
    for (CharacterMap::iterator it = chars_to_glyph_ids->begin(),
            e = chars_to_glyph_ids->end(); it != e; ++it) {
        int32_t character = it->first;
        int32_t glyph_id = it->second.glyph_id();
        if (character != last_chararacter + 1) {  // new segment
            if (current_segment != NULL) {
                current_segment->set_end_count(last_chararacter);
                segment_list->push_back(current_segment);
            }
            // start_code = character
            // end_code = -1 (unknown for now)
            // id_delta = 0 (we don't use id_delta for this representation)
            // id_range_offset = last_offset (offset into the glyph_id_array)
            current_segment =
                new CMapTable::CMapFormat4::Builder::
                Segment(character, -1, 0, last_offset);
        }
        glyph_id_array->push_back(glyph_id);
        last_offset += DataSize::kSHORT;
        last_chararacter = character;
    }
    // The last segment is still open.
    if (glyph_id_array->size() < 1) {
        PyErr_SetString(NoGlyphs, "No glyphs for the specified characters found");
        return false;
    }
    current_segment->set_end_count(last_chararacter);
    segment_list->push_back(current_segment);
    // Updating the id_range_offset for every segment.
    for (int32_t i = 0, num_segs = segment_list->size(); i < num_segs; ++i) {
        Ptr<CMapTable::CMapFormat4::Builder::Segment> segment = segment_list->at(i);
        segment->set_id_range_offset(segment->id_range_offset()
                + (num_segs - i + 1) * DataSize::kSHORT);
    }
    // Adding the final, required segment.
    current_segment =
        new CMapTable::CMapFormat4::Builder::Segment(0xffff, 0xffff, 1, 0);
    segment_list->push_back(current_segment);
    // Writing the segments and glyph id array to the CMap
    cmap_builder->set_segments(segment_list);
    cmap_builder->set_glyph_id_array(glyph_id_array);
    delete segment_list;
    delete glyph_id_array;
    return true;
}

bool FontAssembler::AssembleGlyphAndLocaTables() {
    Ptr<LocaTable::Builder> loca_table_builder =
        down_cast<LocaTable::Builder*>
        (font_builder_->NewTableBuilder(Tag::loca));
    Ptr<GlyphTable::Builder> glyph_table_builder =
        down_cast<GlyphTable::Builder*>
        (font_builder_->NewTableBuilder(Tag::glyf));

    GlyphIdSet* resolved_glyph_ids = font_info_->resolved_glyph_ids();
    IntegerList loca_list;
    // Basic sanity check: all LOCA tables are of the same size
    // This is necessary but not sufficient!
    int32_t previous_size = -1;
    for (FontIdMap::iterator it = font_info_->fonts()->begin();
            it != font_info_->fonts()->end(); ++it) {
        Ptr<LocaTable> loca_table =
            down_cast<LocaTable*>(font_info_->GetTable(it->first, Tag::loca));
        int32_t current_size = loca_table->header_length();
        if (previous_size != -1 && current_size != previous_size) {
            return false;
        }
        previous_size = current_size;
    }

    // Assuming all fonts referenced by the FontInfo are the subsets of the same
    // font, their loca tables should all have the same sizes.
    // We'll just get the size of the first font's LOCA table for simplicty.
    Ptr<LocaTable> first_loca_table =
        down_cast<LocaTable*>
        (font_info_->GetTable(font_info_->fonts()->begin()->first, Tag::loca));
    int32_t num_loca_glyphs = first_loca_table->num_glyphs();
    loca_list.resize(num_loca_glyphs);
    loca_list.push_back(0);
    int32_t last_glyph_id = 0;
    int32_t last_offset = 0;
    GlyphTable::GlyphBuilderList* glyph_builders =
        glyph_table_builder->GlyphBuilders();

    for (GlyphIdSet::iterator it = resolved_glyph_ids->begin(),
            e = resolved_glyph_ids->end(); it != e; ++it) {
        // Get the glyph for this resolved_glyph_id.
        int32_t resolved_glyph_id = it->glyph_id();
        int32_t font_id = it->font_id();
        // Get the LOCA table for the current glyph id.
        Ptr<LocaTable> loca_table =
            down_cast<LocaTable*>
            (font_info_->GetTable(font_id, Tag::loca));
        int32_t length = loca_table->GlyphLength(resolved_glyph_id);
        int32_t offset = loca_table->GlyphOffset(resolved_glyph_id);

        // Get the GLYF table for the current glyph id.
        Ptr<GlyphTable> glyph_table =
            down_cast<GlyphTable*>
            (font_info_->GetTable(font_id, Tag::glyf));
        GlyphPtr glyph;
        glyph.Attach(glyph_table->GetGlyph(offset, length));

        // The data reference by the glyph is copied into a new glyph and
        // added to the glyph_builders belonging to the glyph_table_builder.
        // When Build gets called, all the glyphs will be built.
        Ptr<ReadableFontData> data = glyph->ReadFontData();
        Ptr<WritableFontData> copy_data;
        copy_data.Attach(WritableFontData::CreateWritableFontData(data->Length()));
        data->CopyTo(copy_data);
        GlyphBuilderPtr glyph_builder;
        glyph_builder.Attach(glyph_table_builder->GlyphBuilder(copy_data));
        glyph_builders->push_back(glyph_builder);

        // If there are missing glyphs between the last glyph_id and the
        // current resolved_glyph_id, since the LOCA table needs to have the same
        // size, the offset is kept the same.
        for (int32_t i = last_glyph_id + 1; i <= resolved_glyph_id; ++i)
            loca_list[i] = last_offset;
        last_offset += length;
        loca_list[resolved_glyph_id + 1] = last_offset;
        last_glyph_id = resolved_glyph_id + 1;
    }
    // If there are missing glyph ids, their loca entries must all point
    // to the same offset as the last valid glyph id making them all zero length.
    for (int32_t i = last_glyph_id + 1; i <= num_loca_glyphs; ++i)
        loca_list[i] = last_offset;
    loca_table_builder->SetLocaList(&loca_list);
    return true;
}

void FontAssembler::Initialize()   {
    font_factory_.Attach(FontFactory::GetInstance());
    font_builder_.Attach(font_factory_->NewFontBuilder());
}


// }}}

// Subsetters {{{
// Subsets a given font using a character predicate.

PredicateSubsetter::PredicateSubsetter(Font* font, CharacterPredicate* predicate) : font_(font), predicate_(predicate) {}

PredicateSubsetter::~PredicateSubsetter() { }

// Performs subsetting returning the subsetted font.
CALLER_ATTACH Font* PredicateSubsetter::Subset() {
    Ptr<FontSourcedInfoBuilder> info_builder =
        new FontSourcedInfoBuilder(font_, 0, predicate_);

    Ptr<FontInfo> font_info;
    font_info.Attach(info_builder->GetFontInfo());
    if (!font_info) {
        PyErr_SetString(Error, "Could not create font info");
        return NULL;
    }

    IntegerSet* table_blacklist = new IntegerSet;
    table_blacklist->insert(Tag::DSIG);
    Ptr<FontAssembler> font_assembler = new FontAssembler(font_info,
            table_blacklist);
    Ptr<Font> font_subset;
    font_subset.Attach(font_assembler->Assemble());
    delete table_blacklist;
    if (!font_subset) { if (!PyErr_Occurred()) PyErr_SetString(Error, "Could not subset font"); }
    return font_subset.Detach();
}


// }}}

static void get_stats(Font *font, PyObject *dict) {
    PyObject *t;
    const TableMap* tables = font->GetTableMap();
    for (TableMap::const_iterator it = tables->begin(),
            e = tables->end(); it != e; ++it) {
        t = PyInt_FromLong(it->second->DataLength());
        if (t != NULL) {
            PyDict_SetItemString(dict, TagToString(it->first), t);
            Py_DECREF(t);
        }
    }
}

static PyObject*
do_subset(const char *data, Py_ssize_t sz, Ptr<CharacterPredicate> &predicate) {
    FontPtr font;
    Ptr<FontFactory> font_factory;
    FontArray fonts;
    MemoryInputStream stream;
    PyObject *stats, *stats2;

    if (!stream.Attach(reinterpret_cast<const byte_t*>(data), sz))
        return PyErr_NoMemory();
    font_factory.Attach(FontFactory::GetInstance());
    font_factory->LoadFonts(&stream, &fonts);
    if (fonts.empty() || fonts[0] == NULL) {
        PyErr_SetString(Error, "Failed to load font from provided data.");
        return NULL;
    }

    font = fonts[0];
    if (font->num_tables() == 0) {
        PyErr_SetString(Error, "Loaded font has 0 tables.");
        return NULL;
    }
    Ptr<PredicateSubsetter> subsetter = new PredicateSubsetter(font, predicate);
    Ptr<Font> new_font;
    new_font.Attach(subsetter->Subset());
    if (!new_font) return NULL;

    Ptr<FontFactory> ff;
    ff.Attach(FontFactory::GetInstance());
    MemoryOutputStream output_stream;
    ff->SerializeFont(new_font, &output_stream);

    stats = PyDict_New(); stats2 = PyDict_New();
    if (stats == NULL || stats2 == NULL) return PyErr_NoMemory();
    get_stats(font, stats);
    get_stats(new_font, stats2);
    return Py_BuildValue("s#NN", (char*)output_stream.Get(), output_stream.Size(), stats, stats2);
}

static PyObject*
subset(PyObject *self, PyObject *args) {
    const char *data;
    Py_ssize_t sz;
    PyObject *individual_chars, *ranges, *t;
    int32_t temp;

    if (!PyArg_ParseTuple(args, "s#OO", &data, &sz, &individual_chars, &ranges)) return NULL;

    if (!PyTuple_Check(individual_chars) || !PyTuple_Check(ranges)) {
        PyErr_SetString(PyExc_TypeError, "individual_chars and ranges must be tuples");
        return NULL;
    }

    if (PyTuple_Size(ranges) < 1 && PyTuple_Size(individual_chars) < 1) {
        PyErr_SetString(NoGlyphs, "No characters specified");
        return NULL;
    }

    IntegerSet chars;
    for (Py_ssize_t i = 0; i < PyTuple_Size(individual_chars); i++) {
        temp = (int32_t)PyInt_AsLong(PyTuple_GET_ITEM(individual_chars, i));
        if (temp == -1 && PyErr_Occurred()) return NULL;
        chars.insert(temp);
    }

    IntegerList cranges;
    cranges.resize(2*PyTuple_Size(ranges));
    for (Py_ssize_t i = 0; i < PyTuple_Size(ranges); i++) {
        t = PyTuple_GET_ITEM(ranges, i);
        if (!PyTuple_Check(t) || PyTuple_Size(t) != 2) {
            PyErr_SetString(PyExc_TypeError, "ranges must contain only 2-tuples");
            return NULL;
        }
        for (Py_ssize_t j = 0; j < 2; j++) {
            cranges[2*i+j] = (int32_t)PyInt_AsLong(PyTuple_GET_ITEM(t, j));
            if (cranges[2*i+j] == -1 && PyErr_Occurred()) return NULL;
        }
    }

    Ptr<CharacterPredicate> predicate = new (std::nothrow) CompositePredicate(chars, cranges);
    if (predicate == NULL) return PyErr_NoMemory();

    try {
        return do_subset(data, sz, predicate);
    } catch (std::exception &e) {
        PyErr_SetString(Error, e.what());
        return NULL;
    } catch (...) {
        PyErr_SetString(Error, "An unknown exception occurred while subsetting");
        return NULL;
    }

}
 
static 
PyMethodDef methods[] = {
    {"subset", (PyCFunction)subset, METH_VARARGS,
     "subset(bytestring, individual_chars, ranges) -> Subset the sfnt in bytestring, keeping only characters specified by individual_chars and ranges. Returns the subset font as a bytestring and the sizes of all font tables in the old and new fonts."
    },

    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initsfntly(void) {
    PyObject *m;

    m = Py_InitModule3(
            "sfntly", methods,
            "Wrapper for the Google sfntly library"
    );
    if (m == NULL) return;

    Error = PyErr_NewException((char*)"sfntly.Error", NULL, NULL);
    if (Error == NULL) return;
    PyModule_AddObject(m, "Error", Error);

    NoGlyphs = PyErr_NewException((char*)"sfntly.NoGlyphs", NULL, NULL);
    if (NoGlyphs == NULL) return;
    PyModule_AddObject(m, "NoGlyphs", NoGlyphs);
} 



