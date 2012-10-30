/*
 * Copyright 2011 Google Inc. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_TRUETYPE_LOCA_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_TRUETYPE_LOCA_TABLE_H_

#include "sfntly/port/java_iterator.h"
#include "sfntly/table/table.h"
#include "sfntly/table/core/font_header_table.h"

namespace sfntly {

// A Loca table - 'loca'.
class LocaTable : public Table, public RefCounted<LocaTable> {
 public:
  class LocaIterator : public PODIterator<int32_t, LocaTable> {
   public:
    explicit LocaIterator(LocaTable* table);
    virtual ~LocaIterator() {}

    virtual bool HasNext();
    virtual int32_t Next();

   private:
    int32_t index_;
  };

  class Builder : public Table::Builder, public RefCounted<Builder> {
   public:
    // Constructor scope altered to public for base class to instantiate.
    Builder(Header* header, WritableFontData* data);
    Builder(Header* header, ReadableFontData* data);
    virtual ~Builder();

    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);

    // Get the format version that will be used when the loca table is
    // generated.
    // @return the loca table format version
    int32_t format_version();
    void set_format_version(int32_t value);

    // Gets the List of locas for loca table builder. These may be manipulated
    // in any way by the caller and the changes will be reflected in the final
    // loca table produced as long as no subsequent call is made to the
    // SetLocaList(List) method.
    // If there is no current data for the loca table builder or the loca list
    // have not been previously set then this will return an empty List.
    IntegerList* LocaList();

    // Set the list of locas to be used for building this table. If any existing
    // list was already retrieved with the LocaList() method then the
    // connection of that previous list to this builder will be broken.
    void SetLocaList(IntegerList* list);

    // Return the offset for the given glyph id. Valid glyph ids are from 0 to
    // one less than the number of glyphs. The zero entry is the special entry
    // for the notdef glyph. The final entry beyond the last glyph id is used to
    // calculate the size of the last glyph.
    // @param glyphId the glyph id to get the offset for; must be less than or
    //        equal to one more than the number of glyph ids
    // @return the offset in the glyph table to the specified glyph id
    int32_t GlyphOffset(int32_t glyph_id);

    // Get the length of the data in the glyph table for the specified glyph id.
    int32_t GlyphLength(int32_t glyph_id);

    // Set the number of glyphs.
    // This method sets the number of glyphs that the builder will attempt to
    // parse location data for from the raw binary data. This method only needs
    // to be called (and <b>must</b> be) when the raw data for this builder has
    // been changed. It does not by itself reset the data or clear any set loca
    // list.
    void SetNumGlyphs(int32_t num_glyphs);

    // Get the number of glyphs that this builder has support for.
    int NumGlyphs();

    // Revert the loca table builder to the state contained in the last raw data
    // set on the builder. That raw data may be that read from a font file when
    // the font builder was created, that set by a user of the loca table
    // builder, or null data if this builder was created as a new empty builder.
    void Revert();

    // Get the number of locations or locas. This will be one more than the
    // number of glyphs for this table since the last loca position is used to
    // indicate the size of the final glyph.
    int32_t NumLocas();

    // Get the value from the loca table for the index specified. These are the
    // raw values from the table that are used to compute the offset and size of
    // a glyph in the glyph table. Valid index values run from 0 to the number
    // of glyphs in the font.
    int32_t Loca(int32_t index);

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    virtual void SubDataSet();
    virtual int32_t SubDataSizeToSerialize();
    virtual bool SubReadyToSerialize();
    virtual int32_t SubSerialize(WritableFontData* new_data);

   private:
    // Initialize the internal state from the data. Done lazily since in many
    // cases the builder will be just creating a table object with no parsing
    // required.
    // @param data the data to initialize from
    void Initialize(ReadableFontData* data);

    // Checks that the glyph id is within the correct range.
    // @return glyph_id if correct, -1 otherwise.
    int32_t CheckGlyphRange(int32_t glyph_id);

    int32_t LastGlyphIndex();

    // Internal method to get the loca list if already generated and if not to
    // initialize the state of the builder.
    // @return the loca list
    IntegerList* GetLocaList();

    void ClearLoca(bool nullify);

    int32_t format_version_;  // Note: IndexToLocFormat
    int32_t num_glyphs_;
    IntegerList loca_;
  };

  virtual ~LocaTable();

  int32_t format_version();
  int32_t num_glyphs();

  // Return the offset for the given glyph id. Valid glyph ids are from 0 to the
  // one less than the number of glyphs. The zero entry is the special entry for
  // the notdef glyph. The final entry beyond the last glyph id is used to
  // calculate the size of the last glyph.
  // @param glyphId the glyph id to get the offset for; must be less than or
  //        equal to one more than the number of glyph ids
  // @return the offset in the glyph table to the specified glyph id
  int32_t GlyphOffset(int32_t glyph_id);

  // Get the length of the data in the glyph table for the specified glyph id.
  int32_t GlyphLength(int32_t glyph_id);

  // Get the number of locations or locas. This will be one more than the number
  // of glyphs for this table since the last loca position is used to indicate
  // the size of the final glyph.
  int32_t NumLocas();

  // Get the value from the loca table for the index specified. Valid index
  // values run from 0 to the number of glyphs in the font.
  int32_t Loca(int32_t index);

 private:
  LocaTable(Header* header,
            ReadableFontData* data,
            int32_t format_version,
            int32_t num_glyphs);

  int32_t format_version_;  // Note: Java's version, renamed to format_version_
  int32_t num_glyphs_;

  friend class LocaIterator;
};
typedef Ptr<LocaTable> LocaTablePtr;
typedef Ptr<LocaTable::Builder> LocaTableBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_TRUETYPE_LOCA_TABLE_H_
