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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_EBLC_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_EBLC_TABLE_H_

#include "sfntly/port/lock.h"
#include "sfntly/table/bitmap/big_glyph_metrics.h"
#include "sfntly/table/bitmap/bitmap_glyph.h"
#include "sfntly/table/bitmap/bitmap_size_table.h"
#include "sfntly/table/subtable_container_table.h"

namespace sfntly {

class EblcTable : public SubTableContainerTable,
                  public RefCounted<EblcTable> {
 public:
  struct Offset {
    enum {
      // header
      kVersion = 0,
      kNumSizes = 4,
      kHeaderLength = kNumSizes + DataSize::kULONG,

      // bitmapSizeTable
      kBitmapSizeTableArrayStart = kHeaderLength,
      kBitmapSizeTableLength = 48,
      kBitmapSizeTable_indexSubTableArrayOffset = 0,
      kBitmapSizeTable_indexTableSize = 4,
      kBitmapSizeTable_numberOfIndexSubTables = 8,
      kBitmapSizeTable_colorRef = 12,
      kBitmapSizeTable_hori = 16,
      kBitmapSizeTable_vert = 28,
      kBitmapSizeTable_startGlyphIndex = 40,
      kBitmapSizeTable_endGlyphIndex = 42,
      kBitmapSizeTable_ppemX = 44,
      kBitmapSizeTable_ppemY = 45,
      kBitmapSizeTable_bitDepth = 46,
      kBitmapSizeTable_flags = 47,

      // sbitLineMetrics
      kSbitLineMetricsLength = 12,
      kSbitLineMetrics_ascender = 0,
      kSbitLineMetrics_descender = 1,
      kSbitLineMetrics_widthMax = 2,
      kSbitLineMetrics_caretSlopeNumerator = 3,
      kSbitLineMetrics_caretSlopeDenominator = 4,
      kSbitLineMetrics_caretOffset = 5,
      kSbitLineMetrics_minOriginSB = 6,
      kSbitLineMetrics_minAdvanceSB = 7,
      kSbitLineMetrics_maxBeforeBL = 8,
      kSbitLineMetrics_minAfterBL = 9,
      kSbitLineMetrics_pad1 = 10,
      kSbitLineMetrics_pad2 = 11,

      // indexSubTable
      kIndexSubTableEntryLength = 8,
      kIndexSubTableEntry_firstGlyphIndex = 0,
      kIndexSubTableEntry_lastGlyphIndex = 2,
      kIndexSubTableEntry_additionalOffsetToIndexSubTable = 4,

      // indexSubHeader
      kIndexSubHeaderLength = 8,
      kIndexSubHeader_indexFormat = 0,
      kIndexSubHeader_imageFormat = 2,
      kIndexSubHeader_imageDataOffset = 4,

      // indexSubTable - all offset relative to the subtable start

      // indexSubTable1
      kIndexSubTable1_offsetArray = kIndexSubHeaderLength,
      kIndexSubTable1_builderDataSize = kIndexSubHeaderLength,

      // kIndexSubTable2
      kIndexSubTable2Length = kIndexSubHeaderLength +
                              DataSize::kULONG +
                              BitmapGlyph::Offset::kBigGlyphMetricsLength,
      kIndexSubTable2_imageSize = kIndexSubHeaderLength,
      kIndexSubTable2_bigGlyphMetrics = kIndexSubTable2_imageSize +
                                        DataSize::kULONG,
      kIndexSubTable2_builderDataSize = kIndexSubTable2_bigGlyphMetrics +
                                        BigGlyphMetrics::Offset::kMetricsLength,

      // kIndexSubTable3
      kIndexSubTable3_offsetArray = kIndexSubHeaderLength,
      kIndexSubTable3_builderDataSize = kIndexSubTable3_offsetArray,

      // kIndexSubTable4
      kIndexSubTable4_numGlyphs = kIndexSubHeaderLength,
      kIndexSubTable4_glyphArray = kIndexSubTable4_numGlyphs +
                                   DataSize::kULONG,
      kIndexSubTable4_codeOffsetPairLength = 2 * DataSize::kUSHORT,
      kIndexSubTable4_codeOffsetPair_glyphCode = 0,
      kIndexSubTable4_codeOffsetPair_offset = DataSize::kUSHORT,
      kIndexSubTable4_builderDataSize = kIndexSubTable4_glyphArray,

      // kIndexSubTable5
      kIndexSubTable5_imageSize = kIndexSubHeaderLength,
      kIndexSubTable5_bigGlyphMetrics = kIndexSubTable5_imageSize +
                                        DataSize::kULONG,
      kIndexSubTable5_numGlyphs = kIndexSubTable5_bigGlyphMetrics +
                                  BitmapGlyph::Offset::kBigGlyphMetricsLength,
      kIndexSubTable5_glyphArray = kIndexSubTable5_numGlyphs +
                                   DataSize::kULONG,
      kIndexSubTable5_builderDataSize = kIndexSubTable5_glyphArray,

      // codeOffsetPair
      kCodeOffsetPairLength = 2 * DataSize::kUSHORT,
      kCodeOffsetPair_glyphCode = 0,
      kCodeOffsetPair_offset = DataSize::kUSHORT,
    };
  };

  class Builder : public SubTableContainerTable::Builder,
                  public RefCounted<Builder> {
   public:
    // Constructor scope altered to public because C++ does not allow base
    // class to instantiate derived class with protected constructors.
    Builder(Header* header, WritableFontData* data);
    Builder(Header* header, ReadableFontData* data);
    virtual ~Builder();

    virtual int32_t SubSerialize(WritableFontData* new_data);
    virtual bool SubReadyToSerialize();
    virtual int32_t SubDataSizeToSerialize();
    virtual void SubDataSet();
    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);

    BitmapSizeTableBuilderList* BitmapSizeBuilders();
    void Revert();

    // Generates the loca list for the EBDT table. The list is intended to be
    // used by the EBDT to allow it to parse the glyph data and generate glyph
    // objects. After returning from this method the list belongs to the caller.
    // The list entries are in the same order as the size table builders are at
    // the time of this call.
    // @return the list of loca maps with one for each size table builder
    void GenerateLocaList(BitmapLocaList* output);

    // Create a new builder using the header information and data provided.
    // @param header the header information
    // @param data the data holding the table
    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);
    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                ReadableFontData* data);

   private:
    BitmapSizeTableBuilderList* GetSizeList();
    void Initialize(ReadableFontData* data, BitmapSizeTableBuilderList* output);

    static const int32_t kVersion = 0x00020000;
    BitmapSizeTableBuilderList size_table_builders_;
  };

  int32_t Version();
  int32_t NumSizes();
  // UNIMPLEMENTED: toString()

  BitmapSizeTable* GetBitmapSizeTable(int32_t index);

  static const int32_t NOTDEF = -1;

 protected:
  EblcTable(Header* header, ReadableFontData* data);

 private:
  BitmapSizeTableList* GetBitmapSizeTableList();

  static void CreateBitmapSizeTable(ReadableFontData* data,
                                    int32_t num_sizes,
                                    BitmapSizeTableList* output);

  Lock bitmap_size_table_lock_;
  BitmapSizeTableList bitmap_size_table_;
};
typedef Ptr<EblcTable> EblcTablePtr;
typedef Ptr<EblcTable::Builder> EblcTableBuilderPtr;
}

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_EBLC_TABLE_H_
