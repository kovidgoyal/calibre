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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_BITMAP_GLYPH_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_BITMAP_GLYPH_H_

#include <vector>
#include <map>

#include "sfntly/table/subtable.h"

namespace sfntly {

class BitmapGlyph : public SubTable {
 public:
  struct Offset {
    enum {
      // header
      kVersion = 0,

      kSmallGlyphMetricsLength = 5,
      kBigGlyphMetricsLength = 8,
      // format 1
      kGlyphFormat1_imageData = kSmallGlyphMetricsLength,

      // format 2
      kGlyphFormat2_imageData = kSmallGlyphMetricsLength,

      // format 3

      // format 4

      // format 5
      kGlyphFormat5_imageData = 0,

      // format 6
      kGlyphFormat6_imageData = kBigGlyphMetricsLength,

      // format 7
      kGlyphFormat7_imageData = kBigGlyphMetricsLength,

      // format 8
      kGlyphFormat8_numComponents = kSmallGlyphMetricsLength + 1,
      kGlyphFormat8_componentArray = kGlyphFormat8_numComponents +
                                     DataSize::kUSHORT,

      // format 9
      kGlyphFormat9_numComponents = kBigGlyphMetricsLength,
      kGlyphFormat9_componentArray = kGlyphFormat9_numComponents +
                                     DataSize::kUSHORT,

      // ebdtComponent
      kEbdtComponentLength = DataSize::kUSHORT + 2 * DataSize::kCHAR,
      kEbdtComponent_glyphCode = 0,
      kEbdtComponent_xOffset = 2,
      kEbdtComponent_yOffset = 3,
    };
  };

  // TODO(stuartg): builder is not functional at all
  // - need to add subclasses for each type of bitmap glyph
  class Builder : public SubTable::Builder {
   public:
    virtual ~Builder();

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    virtual void SubDataSet();
    virtual int32_t SubDataSizeToSerialize();
    virtual bool SubReadyToSerialize();
    virtual int32_t SubSerialize(WritableFontData* new_data);

    int32_t format() { return format_; }

    static CALLER_ATTACH Builder* CreateGlyphBuilder(ReadableFontData* data,
                                                     int32_t format);

   protected:
    Builder(WritableFontData* data, int32_t format);
    Builder(ReadableFontData* data, int32_t format);

   private:
    int32_t format_;
  };

  virtual ~BitmapGlyph();

  static CALLER_ATTACH BitmapGlyph* CreateGlyph(ReadableFontData* data,
                                                int32_t format);
  int32_t format() { return format_; }

  // UNIMPLEMENTED: toString()

 protected:
  BitmapGlyph(ReadableFontData* data, int32_t format);

 private:
  int32_t format_;
};
typedef Ptr<BitmapGlyph> BitmapGlyphPtr;
typedef Ptr<BitmapGlyph::Builder> BitmapGlyphBuilderPtr;
typedef std::map<int32_t, BitmapGlyphBuilderPtr> BitmapGlyphBuilderMap;
typedef std::vector<BitmapGlyphBuilderMap> BitmapGlyphBuilderList;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_BITMAP_GLYPH_H_
