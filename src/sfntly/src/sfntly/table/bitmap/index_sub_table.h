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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_INDEX_SUBTABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_INDEX_SUBTABLE_H_

#include <vector>

#include "sfntly/port/java_iterator.h"
#include "sfntly/table/subtable.h"
#include "sfntly/table/bitmap/bitmap_glyph_info.h"

namespace sfntly {

class IndexSubTable : public SubTable {
 public:
  struct Format {
    enum {
      FORMAT_1 = 1,
      FORMAT_2 = 2,
      FORMAT_3 = 3,
      FORMAT_4 = 4,
      FORMAT_5 = 5,
    };
  };

  class Builder : public SubTable::Builder {
   public:
    virtual ~Builder();

    void Revert();

    int32_t index_format() { return index_format_; }
    int32_t first_glyph_index() { return first_glyph_index_; }
    void set_first_glyph_index(int32_t v) { first_glyph_index_ = v; }
    int32_t last_glyph_index() { return last_glyph_index_; }
    void set_last_glyph_index(int32_t v) { last_glyph_index_ = v; }
    int32_t image_format() { return image_format_; }
    void set_image_format(int32_t v) { image_format_ = v; }
    int32_t image_data_offset() { return image_data_offset_; }
    void set_image_data_offset(int32_t v) { image_data_offset_ = v; }

    virtual int32_t NumGlyphs() = 0;

    // Gets the glyph info for the specified glyph id.
    // @param glyphId the glyph id to look up
    // @return the glyph info
    CALLER_ATTACH virtual BitmapGlyphInfo* GlyphInfo(int32_t glyph_id);

    // Gets the full offset of the glyph within the EBDT table.
    // @param glyphId the glyph id
    // @return the glyph offset
    virtual int32_t GlyphOffset(int32_t glyph_id);

    // Gets the offset of the glyph relative to the block for this index
    // subtable.
    // @param glyphId the glyph id
    // @return the glyph offset
    virtual int32_t GlyphStartOffset(int32_t glyph_id) = 0;

    // Gets the length of the glyph within the EBDT table.
    // @param glyphId the glyph id
    // @return the glyph offset
    virtual int32_t GlyphLength(int32_t glyph_id) = 0;

    // Note: renamed from java iterator()
    CALLER_ATTACH virtual Iterator<BitmapGlyphInfo, IndexSubTable::Builder>*
        GetIterator() = 0;

    // Static instantiation function.
    static CALLER_ATTACH Builder* CreateBuilder(int32_t index_format);
    static CALLER_ATTACH Builder*
        CreateBuilder(ReadableFontData* data,
                      int32_t offset_to_index_sub_table_array,
                      int32_t array_index);

    // The following methods will never be called but they need to be here to
    // allow the BitmapSizeTable to see these methods through an abstract
    // reference.
    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    virtual void SubDataSet();
    virtual int32_t SubDataSizeToSerialize();
    virtual bool SubReadyToSerialize();
    virtual int32_t SubSerialize(WritableFontData* new_data);

   protected:
    Builder(int32_t data_size, int32_t index_format);
    Builder(int32_t index_format,
            int32_t image_format,
            int32_t image_data_offset,
            int32_t data_size);
    Builder(WritableFontData* data,
            int32_t first_glyph_index,
            int32_t last_glyph_index);
    Builder(ReadableFontData* data,
            int32_t first_glyph_index,
            int32_t last_glyph_index);

    // Checks that the glyph id is within the correct range. If it returns the
    // offset of the glyph id from the start of the range.
    // @param glyphId
    // @return the offset of the glyphId from the start of the glyph range
    // @throws IndexOutOfBoundsException if the glyph id is not within the
    //         correct range
    int32_t CheckGlyphRange(int32_t glyph_id);
    int32_t SerializeIndexSubHeader(WritableFontData* data);

   private:
    void Initialize(ReadableFontData* data);

    int32_t first_glyph_index_;
    int32_t last_glyph_index_;
    int32_t index_format_;
    int32_t image_format_;
    int32_t image_data_offset_;
  };

  int32_t index_format() { return index_format_; }
  int32_t first_glyph_index() { return first_glyph_index_; }
  int32_t last_glyph_index() { return last_glyph_index_; }
  int32_t image_format() { return image_format_; }
  int32_t image_data_offset() { return image_data_offset_; }

  CALLER_ATTACH BitmapGlyphInfo* GlyphInfo(int32_t glyph_id);
  virtual int32_t GlyphOffset(int32_t glyph_id);
  virtual int32_t GlyphStartOffset(int32_t glyph_id) = 0;
  virtual int32_t GlyphLength(int32_t glyph_id) = 0;
  virtual int32_t NumGlyphs() = 0;

  static CALLER_ATTACH IndexSubTable*
      CreateIndexSubTable(ReadableFontData* data,
                          int32_t offset_to_index_sub_table_array,
                          int32_t array_index);

 protected:
  // Note: the constructor does not implement offset/length form provided in
  //       Java to avoid heavy lifting in constructors.  Callers to call
  //       GetDataLength() static method of the derived class to get proper
  //       length and slice ahead.
  IndexSubTable(ReadableFontData* data,
                int32_t first_glyph_index,
                int32_t last_glyph_index);

  int32_t CheckGlyphRange(int32_t glyph_id);
  static int32_t CheckGlyphRange(int32_t glyph_id,
                                 int32_t first_glyph_id,
                                 int32_t last_glyph_id);

 private:
  int32_t first_glyph_index_;
  int32_t last_glyph_index_;
  int32_t index_format_;
  int32_t image_format_;
  int32_t image_data_offset_;
};
typedef Ptr<IndexSubTable> IndexSubTablePtr;
typedef std::vector<IndexSubTablePtr> IndexSubTableList;
typedef Ptr<IndexSubTable::Builder> IndexSubTableBuilderPtr;
typedef std::vector<IndexSubTableBuilderPtr> IndexSubTableBuilderList;
typedef Iterator<BitmapGlyphInfo, IndexSubTable::Builder> BitmapGlyphInfoIter;
typedef Ptr<BitmapGlyphInfoIter> BitmapGlyphInfoIterPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_INDEX_SUBTABLE_H_
