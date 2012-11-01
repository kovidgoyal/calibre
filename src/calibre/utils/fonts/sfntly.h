/*
 * sfntly.h
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#pragma once


#include <map>
#include <set>

#include <sfntly/tag.h>
#include <sfntly/font.h>
#include <sfntly/font_factory.h>
#include <sfntly/port/exception_type.h>
#include <sfntly/table/truetype/loca_table.h>
#include <sfntly/table/truetype/glyph_table.h>
#include <sfntly/tools/subsetter/subsetter.h>

using namespace sfntly;

typedef int32_t FontId;
typedef std::map<FontId, Ptr<Font> > FontIdMap;

class CharacterPredicate : virtual public RefCount {
    public:
        CharacterPredicate() {}
        virtual ~CharacterPredicate() {}
        virtual bool operator()(int32_t character) const = 0;
};

class CompositePredicate : public CharacterPredicate,
    public RefCounted<CompositePredicate> {
        public:
            CompositePredicate(IntegerSet &chars, IntegerList &ranges);
            ~CompositePredicate();
            virtual bool operator()(int32_t character) const; 
        private:
            IntegerSet chars;
            IntegerList ranges;
};



// Glyph id pair that contains the loca table glyph id as well as the
// font id that has the glyph table this glyph belongs to.
class GlyphId {
    public:
        GlyphId(int32_t glyph_id, FontId font_id); 
        ~GlyphId();

        bool operator==(const GlyphId& other) const;
        bool operator<(const GlyphId& other) const;

        int32_t glyph_id() const;
        void set_glyph_id(const int32_t glyph_id);
        FontId font_id() const;
        void set_font_id(const FontId font_id);

    private:
        int32_t glyph_id_;
        FontId font_id_;
};

typedef std::map<int32_t, GlyphId> CharacterMap;
typedef std::set<GlyphId> GlyphIdSet;


// Font information used for FontAssembler in the construction of a new font.
// Will make copies of character map, glyph id set and font id map.
class FontInfo : public RefCounted<FontInfo> {
    public:
        // Empty FontInfo object.
        FontInfo();

        // chars_to_glyph_ids maps characters to GlyphIds for CMap construction
        // resolved_glyph_ids defines GlyphIds which should be in the final font
        // fonts is a map of font ids to fonts to reference any needed table
        FontInfo(CharacterMap* chars_to_glyph_ids,
                GlyphIdSet* resolved_glyph_ids,
                FontIdMap* fonts);

        virtual ~FontInfo();

        // Gets the table with the specified tag from the font corresponding to
        // font_id or NULL if there is no such font/table.
        // font_id is the id of the font that contains the table
        // tag identifies the table to be obtained
        virtual FontDataTable* GetTable(FontId font_id, int32_t tag);

        // Gets the table map of the font whose id is font_id
        virtual const TableMap* GetTableMap(FontId font_id);

        CharacterMap* chars_to_glyph_ids() const;
        // Takes ownership of the chars_to_glyph_ids CharacterMap.
        void set_chars_to_glyph_ids(CharacterMap* chars_to_glyph_ids);

        GlyphIdSet* resolved_glyph_ids() const;
        // Takes ownership of the glyph_ids GlyphIdSet.
        void set_resolved_glyph_ids(GlyphIdSet* resolved_glyph_ids);

        FontIdMap* fonts() const;

        // Takes ownership of the fonts FontIdMap.
        void set_fonts(FontIdMap* fonts);

    private:
        CharacterMap* chars_to_glyph_ids_;
        GlyphIdSet* resolved_glyph_ids_;
        FontIdMap* fonts_;
};


// FontSourcedInfoBuilder is used to create a FontInfo object from a Font
// optionally specifying a CharacterPredicate to filter out some of
// the font's characters.
// It does not take ownership or copy the values its constructor receives.
class FontSourcedInfoBuilder :
    public RefCounted<FontSourcedInfoBuilder> {
        public:
            FontSourcedInfoBuilder(Font* font, FontId font_id);

            FontSourcedInfoBuilder(Font* font,
                    FontId font_id,
                    CharacterPredicate* predicate);

            virtual ~FontSourcedInfoBuilder();

            virtual CALLER_ATTACH FontInfo* GetFontInfo();

        protected:
            bool GetCharacterMap(CharacterMap* chars_to_glyph_ids);

            bool ResolveCompositeGlyphs(CharacterMap* chars_to_glyph_ids,
                    GlyphIdSet* resolved_glyph_ids); 

            void Initialize(); 

        private:
            Ptr<Font> font_;
            FontId font_id_;
            CharacterPredicate* predicate_;

            Ptr<CMapTable::CMap> cmap_;
            Ptr<LocaTable> loca_table_;
            Ptr<GlyphTable> glyph_table_;
    };


// Assembles FontInfo into font builders.
// Does not take ownership of data passed to it.
class FontAssembler : public RefCounted<FontAssembler> {
    public:
        // font_info is the FontInfo which will be used for the new font
        // table_blacklist is used to decide which tables to exclude from the
        // final font.
        FontAssembler(FontInfo* font_info, IntegerSet* table_blacklist); 

        explicit FontAssembler(FontInfo* font_info);

        ~FontAssembler();

        // Assemble a new font from the font info object.
        virtual CALLER_ATTACH Font* Assemble();

        IntegerSet* table_blacklist() const; 

        void set_table_blacklist(IntegerSet* table_blacklist); 

    protected:
        virtual bool AssembleCMapTable(); 

        virtual bool AssembleGlyphAndLocaTables(); 

        virtual void Initialize(); 

    private:
        Ptr<FontInfo> font_info_;
        Ptr<FontFactory> font_factory_;
        Ptr<Font::Builder> font_builder_;
        IntegerSet* table_blacklist_;
};

class PredicateSubsetter : public RefCounted<Subsetter> {
    public:
        PredicateSubsetter(Font* font, CharacterPredicate* predicate); 
        virtual ~PredicateSubsetter();

        // Performs subsetting returning the subsetted font.
        virtual CALLER_ATTACH Font* Subset(); 

    private:
        Ptr<Font> font_;
        Ptr<CharacterPredicate> predicate_;
};
