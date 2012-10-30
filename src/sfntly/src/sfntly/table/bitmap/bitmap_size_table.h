/*
 * Copyright 2011 Google Inc. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0  = the "License");
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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_BITMAP_SIZE_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_BITMAP_SIZE_TABLE_H_

#include "sfntly/port/lock.h"
#include "sfntly/table/bitmap/bitmap_glyph_info.h"
#include "sfntly/table/bitmap/index_sub_table.h"

namespace sfntly {
// Binary search would be faster but many fonts have index subtables that
// aren't sorted.
// Note: preprocessor define is used to avoid const expression warnings in C++
//       code.
#define SFNTLY_BITMAPSIZE_USE_BINARY_SEARCH 0

class BitmapSizeTable : public SubTable,
                        public RefCounted<BitmapSizeTable> {
 public:
  class Builder : public SubTable::Builder,
                  public RefCounted<Builder> {
   public:
    class BitmapGlyphInfoIterator :
        public RefIterator<BitmapGlyphInfo, Builder> {
     public:
      explicit BitmapGlyphInfoIterator(Builder* container);
      virtual ~BitmapGlyphInfoIterator() {}

      virtual bool HasNext();
      CALLER_ATTACH virtual BitmapGlyphInfo* Next();

     private:
      bool HasNext(BitmapGlyphInfoIter* iterator_base);
      CALLER_ATTACH BitmapGlyphInfo* Next(BitmapGlyphInfoIter* iterator_base);

      IndexSubTableBuilderList::iterator sub_table_iter_;
      BitmapGlyphInfoIterPtr sub_table_glyph_info_iter_;
    };

    virtual ~Builder();

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    virtual void SubDataSet();
    virtual int32_t SubDataSizeToSerialize();
    virtual bool SubReadyToSerialize();
    virtual int32_t SubSerialize(WritableFontData* new_data);

    static CALLER_ATTACH Builder* CreateBuilder(WritableFontData* data,
                                                ReadableFontData* master_data);
    static CALLER_ATTACH Builder* CreateBuilder(ReadableFontData* data,
                                                ReadableFontData* master_data);
    // Gets the subtable array offset as set in the original table as read from
    // the font file. This value cannot be explicitly set and will be generated
    // during table building.
    // @return the subtable array offset
    int32_t IndexSubTableArrayOffset();

    // Sets the subtable array offset. This is used only during the building
    // process when the objects are being serialized.
    // @param offset the offset to the index subtable array
    void SetIndexSubTableArrayOffset(int32_t offset);

    // Gets the subtable array size as set in the original table as read from
    // the font file. This value cannot be explicitly set and will be generated
    // during table building.
    // @return the subtable array size
    int32_t IndexTableSize();

    // Sets the subtable size. This is used only during the building process
    // when the objects are being serialized.
    // @param size the offset to the index subtable array
    void SetIndexTableSize(int32_t size);

    int32_t NumberOfIndexSubTables();
    int32_t ColorRef();
    // TODO(stuartg): SBitLineMetrics hori();
    // TODO(stuartg): SBitLineMetrics vert();
    int32_t StartGlyphIndex();
    int32_t EndGlyphIndex();
    int32_t PpemX();
    int32_t PpemY();
    int32_t BitDepth();
    int32_t FlagsAsInt();

    IndexSubTable::Builder* IndexSubTableBuilder(int32_t index);
    CALLER_ATTACH BitmapGlyphInfo* GlyphInfo(int32_t glyph_id);
    int32_t GlyphOffset(int32_t glyph_id);
    int32_t GlyphLength(int32_t glyph_id);
    int32_t GlyphFormat(int32_t glyph_id);
    IndexSubTableBuilderList* IndexSubTableBuilders();
    // Note: renamed from iterator(), type is the derived type.
    CALLER_ATTACH BitmapGlyphInfoIterator* GetIterator();
    void GenerateLocaMap(BitmapGlyphInfoMap* output);

   protected:
    void Revert();

   private:
    Builder(WritableFontData* data, ReadableFontData* master_data);
    Builder(ReadableFontData* data, ReadableFontData* master_data);

    void SetNumberOfIndexSubTables(int32_t count);
    IndexSubTable::Builder* SearchIndexSubTables(int32_t glyph_id);
    IndexSubTable::Builder* LinearSearchIndexSubTables(int32_t glyph_id);
    IndexSubTable::Builder* BinarySearchIndexSubTables(int32_t glyph_id);
    IndexSubTableBuilderList* GetIndexSubTableBuilders();
    void Initialize(ReadableFontData* data);
    CALLER_ATTACH IndexSubTable::Builder* CreateIndexSubTableBuilder(
        int32_t index);

    IndexSubTableBuilderList index_sub_tables_;
  };

  virtual ~BitmapSizeTable();

  int32_t IndexSubTableArrayOffset();
  int32_t IndexTableSize();
  int32_t NumberOfIndexSubTables();
  int32_t ColorRef();
  // TODO(stuartg): SBitLineMetrics hori();
  // TODO(stuartg): SBitLineMetrics vert();
  int32_t StartGlyphIndex();
  int32_t EndGlyphIndex();
  int32_t PpemX();
  int32_t PpemY();
  int32_t BitDepth();
  int32_t FlagsAsInt();

  // Note: renamed from indexSubTable()
  IndexSubTable* GetIndexSubTable(int32_t index);
  int32_t GlyphOffset(int32_t glyph_id);
  int32_t GlyphLength(int32_t glyph_id);
  CALLER_ATTACH BitmapGlyphInfo* GlyphInfo(int32_t glyph_id);
  int32_t GlyphFormat(int32_t glyph_id);

 protected:
  BitmapSizeTable(ReadableFontData* data,
                  ReadableFontData* master_data);

 private:
  static int32_t NumberOfIndexSubTables(ReadableFontData* data,
                                        int32_t table_offset);
  IndexSubTable* SearchIndexSubTables(int32_t glyph_id);
  IndexSubTable* LinearSearchIndexSubTables(int32_t glyph_id);
  IndexSubTable* BinarySearchIndexSubTables(int32_t glyph_id);
  CALLER_ATTACH IndexSubTable* CreateIndexSubTable(int32_t index);
  IndexSubTableList* GetIndexSubTableList();

  Lock index_subtables_lock_;
  IndexSubTableList index_subtables_;
};
typedef Ptr<BitmapSizeTable> BitmapSizeTablePtr;
typedef std::vector<BitmapSizeTablePtr> BitmapSizeTableList;
typedef Ptr<BitmapSizeTable::Builder> BitmapSizeTableBuilderPtr;
typedef std::vector<BitmapSizeTableBuilderPtr> BitmapSizeTableBuilderList;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_BITMAP_SIZE_TABLE_H_
