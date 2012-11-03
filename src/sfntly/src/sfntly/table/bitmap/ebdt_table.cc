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

#include "sfntly/table/bitmap/ebdt_table.h"

#include <stdlib.h>

#include "sfntly/table/bitmap/composite_bitmap_glyph.h"
#include "sfntly/table/bitmap/simple_bitmap_glyph.h"

namespace sfntly {
/******************************************************************************
 * EbdtTable class
 ******************************************************************************/
EbdtTable::~EbdtTable() {
}

int32_t EbdtTable::Version() {
  return data_->ReadFixed(Offset::kVersion);
}

CALLER_ATTACH
BitmapGlyph* EbdtTable::Glyph(int32_t offset, int32_t length, int32_t format) {
  ReadableFontDataPtr glyph_data;
  glyph_data.Attach(down_cast<ReadableFontData*>(data_->Slice(offset, length)));
  return BitmapGlyph::CreateGlyph(glyph_data, format);
}

EbdtTable::EbdtTable(Header* header, ReadableFontData* data)
    : SubTableContainerTable(header, data) {
}

/******************************************************************************
 * EbdtTable::Builder class
 ******************************************************************************/
EbdtTable::Builder::Builder(Header* header, WritableFontData* data)
  : SubTableContainerTable::Builder(header, data) {
}

EbdtTable::Builder::Builder(Header* header, ReadableFontData* data)
  : SubTableContainerTable::Builder(header, data) {
}

EbdtTable::Builder::~Builder() {
}

CALLER_ATTACH FontDataTable*
    EbdtTable::Builder::SubBuildTable(ReadableFontData* data) {
  FontDataTablePtr table = new EbdtTable(header(), data);
  return table.Detach();
}

void EbdtTable::Builder::SubDataSet() {
  Revert();
}

int32_t EbdtTable::Builder::SubDataSizeToSerialize() {
  if (glyph_builders_.empty()) {
    return 0;
  }
  bool fixed = true;
  int32_t size = Offset::kHeaderLength;
  for (BitmapGlyphBuilderList::iterator builder_map = glyph_builders_.begin(),
                                        builder_end = glyph_builders_.end();
                                        builder_map != builder_end;
                                        builder_map++) {
    for (BitmapGlyphBuilderMap::iterator glyph_entry = builder_map->begin(),
                                         glyph_entry_end = builder_map->end();
                                         glyph_entry != glyph_entry_end;
                                         glyph_entry++) {
      int32_t glyph_size = glyph_entry->second->SubDataSizeToSerialize();
      size += abs(glyph_size);
      fixed = (glyph_size <= 0) ? false : fixed;
    }
  }
  return (fixed ? 1 : -1) * size;
}

bool EbdtTable::Builder::SubReadyToSerialize() {
  if (glyph_builders_.empty()) {
    return false;
  }
  return true;
}

int32_t EbdtTable::Builder::SubSerialize(WritableFontData* new_data) {
  int32_t size = 0;
  size += new_data->WriteFixed(Offset::kVersion, kVersion);
  for (BitmapGlyphBuilderList::iterator builder_map = glyph_builders_.begin(),
                                        builder_end = glyph_builders_.end();
                                        builder_map != builder_end;
                                        builder_map++) {
    for (BitmapGlyphBuilderMap::iterator glyph_entry = builder_map->begin(),
                                         glyph_entry_end = builder_map->end();
                                         glyph_entry != glyph_entry_end;
                                         glyph_entry++) {
      WritableFontDataPtr slice;
      slice.Attach(down_cast<WritableFontData*>(new_data->Slice(size)));
      size += glyph_entry->second->SubSerialize(slice);
    }
  }
  return size;
}

void EbdtTable::Builder::SetLoca(BitmapLocaList* loca_list) {
  assert(loca_list);
  Revert();
  glyph_loca_.resize(loca_list->size());
  std::copy(loca_list->begin(), loca_list->end(), glyph_loca_.begin());
}

void EbdtTable::Builder::GenerateLocaList(BitmapLocaList* output) {
  assert(output);
  output->clear();

  if (glyph_builders_.empty()) {
    if (glyph_loca_.empty()) {
      return;
    }
  }

  int start_offset = Offset::kHeaderLength;
  for (BitmapGlyphBuilderList::iterator builder_map = glyph_builders_.begin(),
                                        builder_end = glyph_builders_.end();
                                        builder_map != builder_end;
                                        builder_map++) {
    BitmapGlyphInfoMap new_loca_map;
    int32_t glyph_offset = 0;
    for (BitmapGlyphBuilderMap::iterator glyph_entry = builder_map->begin(),
                                         glyph_end = builder_map->end();
                                         glyph_entry != glyph_end;
                                         glyph_entry++) {
      BitmapGlyphBuilderPtr builder = glyph_entry->second;
      int32_t size = builder->SubDataSizeToSerialize();
      BitmapGlyphInfoPtr info = new BitmapGlyphInfo(glyph_entry->first,
          start_offset + glyph_offset, size, builder->format());
      new_loca_map[glyph_entry->first] = info;
      glyph_offset += size;
    }
    start_offset += glyph_offset;
    output->push_back(new_loca_map);
  }
}

BitmapGlyphBuilderList* EbdtTable::Builder::GlyphBuilders() {
  return GetGlyphBuilders();
}

void EbdtTable::Builder::SetGlyphBuilders(
    BitmapGlyphBuilderList* glyph_builders) {
  glyph_builders_.clear();
  std::copy(glyph_builders->begin(), glyph_builders->end(),
            glyph_builders_.begin());
  set_model_changed();
}

void EbdtTable::Builder::Revert() {
  glyph_loca_.clear();
  glyph_builders_.clear();
  set_model_changed(false);
}

CALLER_ATTACH
EbdtTable::Builder* EbdtTable::Builder::CreateBuilder(Header* header,
                                                      WritableFontData* data) {
  Ptr<EbdtTable::Builder> builder;
  builder = new Builder(header, data);
  return builder.Detach();
}

CALLER_ATTACH
EbdtTable::Builder* EbdtTable::Builder::CreateBuilder(Header* header,
                                                      ReadableFontData* data) {
  Ptr<EbdtTable::Builder> builder;
  builder = new Builder(header, data);
  return builder.Detach();
}

BitmapGlyphBuilderList* EbdtTable::Builder::GetGlyphBuilders() {
  if (glyph_builders_.empty()) {
    if (glyph_loca_.empty()) {
#if !defined (SFNTLY_NO_EXCEPTION)
      throw IllegalStateException(
          "Loca values not set - unable to parse glyph data.");
#endif
      return NULL;
    }
    Initialize(InternalReadData(), &glyph_loca_, &glyph_builders_);
    set_model_changed();
  }
  return &glyph_builders_;
}

void EbdtTable::Builder::Initialize(ReadableFontData* data,
                                    BitmapLocaList* loca_list,
                                    BitmapGlyphBuilderList* output) {
  assert(loca_list);
  assert(output);

  output->clear();
  if (data) {
    for (BitmapLocaList::iterator loca_map = loca_list->begin(),
                                  loca_end = loca_list->end();
                                  loca_map != loca_end; loca_map++) {
      BitmapGlyphBuilderMap glyph_builder_map;
      for (BitmapGlyphInfoMap::iterator entry = loca_map->begin(),
                                        entry_end = loca_map->end();
                                        entry != entry_end; entry++) {
        BitmapGlyphInfoPtr info = entry->second;
        ReadableFontDataPtr slice;
        slice.Attach(down_cast<ReadableFontData*>(data->Slice(
            info->offset(), info->length())));
        BitmapGlyphBuilderPtr glyph_builder;
        glyph_builder.Attach(BitmapGlyph::Builder::CreateGlyphBuilder(
            slice, info->format()));
        glyph_builder_map[entry->first] = glyph_builder;
      }
      output->push_back(glyph_builder_map);
    }
  }
}

}  // namespace sfntly
