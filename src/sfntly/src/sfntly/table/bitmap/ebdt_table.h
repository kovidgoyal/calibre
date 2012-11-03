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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_EBDT_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_EBDT_TABLE_H_

#include "sfntly/table/bitmap/bitmap_glyph.h"
#include "sfntly/table/bitmap/bitmap_glyph_info.h"
#include "sfntly/table/subtable_container_table.h"

namespace sfntly {

class EbdtTable : public SubTableContainerTable,
                  public RefCounted<EbdtTable> {
 public:
  struct Offset {
    enum {
      kVersion = 0,
      kHeaderLength = DataSize::kFixed,
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

    void SetLoca(BitmapLocaList* loca_list);
    void GenerateLocaList(BitmapLocaList* output);

    // Gets the List of glyph builders for the glyph table builder. These may be
    // manipulated in any way by the caller and the changes will be reflected in
    // the final glyph table produced.
    // If there is no current data for the glyph builder or the glyph builders
    // have not been previously set then this will return an empty glyph builder
    // List. If there is current data (i.e. data read from an existing font) and
    // the loca list has not been set or is null, empty, or invalid, then an
    // empty glyph builder List will be returned.
    // @return the list of glyph builders
    BitmapGlyphBuilderList* GlyphBuilders();

    // Replace the internal glyph builders with the one provided. The provided
    // list and all contained objects belong to this builder.
    // This call is only required if the entire set of glyphs in the glyph
    // table builder are being replaced. If the glyph builder list provided from
    // the {@link EbdtTable.Builder#glyphBuilders()} is being used and modified
    // then those changes will already be reflected in the glyph table builder.
    // @param glyphBuilders the new glyph builders
    void SetGlyphBuilders(BitmapGlyphBuilderList* glyph_builders);

    void Revert();

    // Create a new builder using the header information and data provided.
    // @param header the header information
    // @param data the data holding the table
    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);
    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                ReadableFontData* data);

   private:
    BitmapGlyphBuilderList* GetGlyphBuilders();
    static void Initialize(ReadableFontData* data,
                           BitmapLocaList* loca_list,
                           BitmapGlyphBuilderList* output);

    static const int32_t kVersion = 0x00020000;  // TODO(stuartg): const/enum
    BitmapLocaList glyph_loca_;
    BitmapGlyphBuilderList glyph_builders_;
  };

  virtual ~EbdtTable();
  int32_t Version();
  CALLER_ATTACH BitmapGlyph* Glyph(int32_t offset,
                                   int32_t length,
                                   int32_t format);
 protected:
  EbdtTable(Header* header, ReadableFontData* data);
};
typedef Ptr<EbdtTable> EbdtTablePtr;
typedef Ptr<EbdtTable::Builder> EbdtTableBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_EBDT_TABLE_H_
