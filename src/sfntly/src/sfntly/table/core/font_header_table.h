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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_FONT_HEADER_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_FONT_HEADER_TABLE_H_

#include "sfntly/table/table.h"
#include "sfntly/table/table_based_table_builder.h"

namespace sfntly {

struct IndexToLocFormat {
  enum {
    kShortOffset = 0,
    kLongOffset = 1
  };
};

struct FontDirectionHint {
  enum {
    kFullyMixed = 0,
    kOnlyStrongLTR = 1,
    kStrongLTRAndNeutral = 2,
    kOnlyStrongRTL = -1,
    kStrongRTLAndNeutral = -2
  };
};

class FontHeaderTable : public Table, public RefCounted<FontHeaderTable> {
 public:
  class Builder : public TableBasedTableBuilder, public RefCounted<Builder> {
   public:
    // Constructor scope altered to public because C++ does not allow base
    // class to instantiate derived class with protected constructors.
    Builder(Header* header, WritableFontData* data);
    Builder(Header* header, ReadableFontData* data);
    virtual ~Builder();
    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);

    virtual int32_t TableVersion();
    virtual void SetTableVersion(int32_t version);
    virtual int32_t FontRevision();
    virtual void SetFontRevision(int32_t revision);
    virtual int64_t ChecksumAdjustment();
    virtual void SetChecksumAdjustment(int64_t adjustment);
    virtual int64_t MagicNumber();
    virtual void SetMagicNumber(int64_t magic_number);
    virtual int32_t FlagsAsInt();
    virtual void SetFlagsAsInt(int32_t flags);
    // TODO(arthurhsu): IMPLEMENT EnumSet<Flags> Flags()
    // TODO(arthurhsu): IMPLEMENT setFlags(EnumSet<Flags> flags)
    virtual int32_t UnitsPerEm();
    virtual void SetUnitsPerEm(int32_t units);
    virtual int64_t Created();
    virtual void SetCreated(int64_t date);
    virtual int64_t Modified();
    virtual void SetModified(int64_t date);
    virtual int32_t XMin();
    virtual void SetXMin(int32_t xmin);
    virtual int32_t YMin();
    virtual void SetYMin(int32_t ymin);
    virtual int32_t XMax();
    virtual void SetXMax(int32_t xmax);
    virtual int32_t YMax();
    virtual void SetYMax(int32_t ymax);
    virtual int32_t MacStyleAsInt();
    virtual void SetMacStyleAsInt(int32_t style);
    // TODO(arthurhsu): IMPLEMENT EnumSet<MacStyle> macStyle()
    // TODO(arthurhsu): IMPLEMENT setMacStyle(EnumSet<MacStyle> style)
    virtual int32_t LowestRecPPEM();
    virtual void SetLowestRecPPEM(int32_t size);
    virtual int32_t FontDirectionHint();
    virtual void SetFontDirectionHint(int32_t hint);
    virtual int32_t IndexToLocFormat();
    virtual void SetIndexToLocFormat(int32_t format);
    virtual int32_t GlyphDataFormat();
    virtual void SetGlyphDataFormat(int32_t format);

    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);
  };

  virtual ~FontHeaderTable();
  int32_t TableVersion();
  int32_t FontRevision();

  // Get the checksum adjustment. To compute: set it to 0, sum the entire font
  // as ULONG, then store 0xB1B0AFBA - sum.
  int64_t ChecksumAdjustment();

  // Get the magic number. Set to 0x5F0F3CF5.
  int64_t MagicNumber();

  // TODO(arthurhsu): IMPLEMENT: EnumSet<Flags>
  int32_t FlagsAsInt();
  // TODO(arthurhsu): IMPLEMENT: Flags() returning EnumSet<Flags>

  int32_t UnitsPerEm();

  // Get the created date. Number of seconds since 12:00 midnight, January 1,
  // 1904. 64-bit integer.
  int64_t Created();
  // Get the modified date. Number of seconds since 12:00 midnight, January 1,
  // 1904. 64-bit integer.
  int64_t Modified();

  // Get the x min. For all glyph bounding boxes.
  int32_t XMin();
  // Get the y min. For all glyph bounding boxes.
  int32_t YMin();
  // Get the x max. For all glyph bounding boxes.
  int32_t XMax();
  // Get the y max. For all glyph bounding boxes.
  int32_t YMax();

  // TODO(arthurhsu): IMPLEMENT: EnumSet<MacStyle>
  int32_t MacStyleAsInt();
  // TODO(arthurhsu): IMPLEMENT: macStyle() returning EnumSet<MacStyle>

  int32_t LowestRecPPEM();
  int32_t FontDirectionHint();  // Note: no AsInt() form, already int
  int32_t IndexToLocFormat();  // Note: no AsInt() form, already int
  int32_t GlyphDataFormat();

 private:
  struct Offset {
    enum {
      kTableVersion = 0,
      kFontRevision = 4,
      kCheckSumAdjustment = 8,
      kMagicNumber = 12,
      kFlags = 16,
      kUnitsPerEm = 18,
      kCreated = 20,
      kModified = 28,
      kXMin = 36,
      kYMin = 38,
      kXMax = 40,
      kYMax = 42,
      kMacStyle = 44,
      kLowestRecPPEM = 46,
      kFontDirectionHint = 48,
      kIndexToLocFormat = 50,
      kGlyphDataFormat = 52
    };
  };

  FontHeaderTable(Header* header, ReadableFontData* data);
};
typedef Ptr<FontHeaderTable> FontHeaderTablePtr;
typedef Ptr<FontHeaderTable::Builder> FontHeaderTableBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_FONT_HEADER_TABLE_H_
