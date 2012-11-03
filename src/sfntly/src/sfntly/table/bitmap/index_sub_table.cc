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

#include "sfntly/table/bitmap/index_sub_table.h"

#include "sfntly/table/bitmap/eblc_table.h"
#include "sfntly/table/bitmap/index_sub_table_format1.h"
#include "sfntly/table/bitmap/index_sub_table_format2.h"
#include "sfntly/table/bitmap/index_sub_table_format3.h"
#include "sfntly/table/bitmap/index_sub_table_format4.h"
#include "sfntly/table/bitmap/index_sub_table_format5.h"

namespace sfntly {
/******************************************************************************
 * IndexSubTable class
 ******************************************************************************/
CALLER_ATTACH BitmapGlyphInfo* IndexSubTable::GlyphInfo(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return NULL;
  }
  if (GlyphStartOffset(glyph_id) == -1) {
    return NULL;
  }
  BitmapGlyphInfoPtr output = new BitmapGlyphInfo(glyph_id,
                                                  image_data_offset(),
                                                  GlyphStartOffset(glyph_id),
                                                  GlyphLength(glyph_id),
                                                  image_format());
  return output.Detach();
}

int32_t IndexSubTable::GlyphOffset(int32_t glyph_id) {
  int32_t glyph_start_offset = GlyphStartOffset(glyph_id);
  if (glyph_start_offset == -1) {
    return -1;
  }
  return image_data_offset() + glyph_start_offset;
}

// static
CALLER_ATTACH IndexSubTable*
    IndexSubTable::CreateIndexSubTable(ReadableFontData* data,
                                       int32_t offset_to_index_sub_table_array,
                                       int32_t array_index) {
  IndexSubTableBuilderPtr builder;
  builder.Attach(IndexSubTable::Builder::CreateBuilder(
      data, offset_to_index_sub_table_array, array_index));
  return down_cast<IndexSubTable*>(builder->Build());
}

IndexSubTable::IndexSubTable(ReadableFontData* data,
                             int32_t first_glyph_index,
                             int32_t last_glyph_index)
    : SubTable(data),
      first_glyph_index_(first_glyph_index),
      last_glyph_index_(last_glyph_index) {
  index_format_ =
      data_->ReadUShort(EblcTable::Offset::kIndexSubHeader_indexFormat);
  image_format_ =
      data_->ReadUShort(EblcTable::Offset::kIndexSubHeader_imageFormat);
  image_data_offset_ =
      data_->ReadULongAsInt(EblcTable::Offset::kIndexSubHeader_imageDataOffset);
}

int32_t IndexSubTable::CheckGlyphRange(int32_t glyph_id) {
  return CheckGlyphRange(glyph_id, first_glyph_index(), last_glyph_index());
}

// static
int32_t IndexSubTable::CheckGlyphRange(int32_t glyph_id,
                                       int32_t first_glyph_id,
                                       int32_t last_glyph_id) {
  if (glyph_id < first_glyph_id || glyph_id > last_glyph_id) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException("Glyph ID is outside of the allowed range.");
#endif
    return -1;
  }
  return glyph_id - first_glyph_id;
}

/******************************************************************************
 * IndexSubTable::Builder class
 ******************************************************************************/
IndexSubTable::Builder::~Builder() {
}

void IndexSubTable::Builder::Revert() {
  set_model_changed(false);
  Initialize(InternalReadData());
}

CALLER_ATTACH BitmapGlyphInfo* IndexSubTable::Builder::GlyphInfo(
    int32_t glyph_id) {
  BitmapGlyphInfoPtr glyph_info =
      new BitmapGlyphInfo(glyph_id,
                          image_data_offset(),
                          GlyphStartOffset(glyph_id),
                          GlyphLength(glyph_id),
                          image_format());
  return glyph_info.Detach();
}

int32_t IndexSubTable::Builder::GlyphOffset(int32_t glyph_id) {
  return image_data_offset() + GlyphStartOffset(glyph_id);
}

// static
CALLER_ATTACH IndexSubTable::Builder*
IndexSubTable::Builder::CreateBuilder(int32_t index_format) {
  switch (index_format) {
    case Format::FORMAT_1:
      return IndexSubTableFormat1::Builder::CreateBuilder();
    case Format::FORMAT_2:
      return IndexSubTableFormat2::Builder::CreateBuilder();
    case Format::FORMAT_3:
      return IndexSubTableFormat3::Builder::CreateBuilder();
    case Format::FORMAT_4:
      return IndexSubTableFormat4::Builder::CreateBuilder();
    case Format::FORMAT_5:
      return IndexSubTableFormat5::Builder::CreateBuilder();
    default:
#if !defined (SFNTLY_NO_EXCEPTION)
      throw IllegalArgumentException("Invalid index subtable format");
#endif
      return NULL;
  }
}

// static
CALLER_ATTACH IndexSubTable::Builder*
IndexSubTable::Builder::CreateBuilder(ReadableFontData* data,
    int32_t offset_to_index_sub_table_array, int32_t array_index) {
  int32_t index_sub_table_entry_offset =
      offset_to_index_sub_table_array +
      array_index * EblcTable::Offset::kIndexSubTableEntryLength;
  int32_t first_glyph_index =
      data->ReadUShort(index_sub_table_entry_offset +
                       EblcTable::Offset::kIndexSubTableEntry_firstGlyphIndex);
  int32_t last_glyph_index =
      data->ReadUShort(index_sub_table_entry_offset +
                       EblcTable::Offset::kIndexSubTableEntry_lastGlyphIndex);
  int32_t additional_offset_to_index_subtable = data->ReadULongAsInt(
      index_sub_table_entry_offset +
      EblcTable::Offset::kIndexSubTableEntry_additionalOffsetToIndexSubTable);
  int32_t index_sub_table_offset = offset_to_index_sub_table_array +
                                   additional_offset_to_index_subtable;
  int32_t index_format = data->ReadUShort(index_sub_table_offset);
  switch (index_format) {
    case 1:
      return IndexSubTableFormat1::Builder::CreateBuilder(
          data, index_sub_table_offset, first_glyph_index, last_glyph_index);
    case 2:
      return IndexSubTableFormat2::Builder::CreateBuilder(
          data, index_sub_table_offset, first_glyph_index, last_glyph_index);
    case 3:
      return IndexSubTableFormat3::Builder::CreateBuilder(
          data, index_sub_table_offset, first_glyph_index, last_glyph_index);
    case 4:
      return IndexSubTableFormat4::Builder::CreateBuilder(
          data, index_sub_table_offset, first_glyph_index, last_glyph_index);
    case 5:
      return IndexSubTableFormat5::Builder::CreateBuilder(
          data, index_sub_table_offset, first_glyph_index, last_glyph_index);
    default:
      // Unknown format and unable to process.
#if !defined (SFNTLY_NO_EXCEPTION)
      throw IllegalArgumentException("Invalid Index Subtable Format");
#endif
      break;
  }
  return NULL;
}

CALLER_ATTACH
FontDataTable* IndexSubTable::Builder::SubBuildTable(ReadableFontData* data) {
  UNREFERENCED_PARAMETER(data);
  return NULL;
}

void IndexSubTable::Builder::SubDataSet() {
  // NOP
}

int32_t IndexSubTable::Builder::SubDataSizeToSerialize() {
  return 0;
}

bool IndexSubTable::Builder::SubReadyToSerialize() {
  return false;
}

int32_t IndexSubTable::Builder::SubSerialize(WritableFontData* new_data) {
  UNREFERENCED_PARAMETER(new_data);
  return 0;
}

IndexSubTable::Builder::Builder(int32_t data_size, int32_t index_format)
    : SubTable::Builder(data_size),
      first_glyph_index_(0),
      last_glyph_index_(0),
      index_format_(index_format),
      image_format_(0),
      image_data_offset_(0) {
}

IndexSubTable::Builder::Builder(int32_t index_format,
                                int32_t image_format,
                                int32_t image_data_offset,
                                int32_t data_size)
    : SubTable::Builder(data_size),
      first_glyph_index_(0),
      last_glyph_index_(0),
      index_format_(index_format),
      image_format_(image_format),
      image_data_offset_(image_data_offset) {
}

IndexSubTable::Builder::Builder(WritableFontData* data,
                                int32_t first_glyph_index,
                                int32_t last_glyph_index)
    : SubTable::Builder(data),
      first_glyph_index_(first_glyph_index),
      last_glyph_index_(last_glyph_index) {
  Initialize(data);
}

IndexSubTable::Builder::Builder(ReadableFontData* data,
                                int32_t first_glyph_index,
                                int32_t last_glyph_index)
    : SubTable::Builder(data),
      first_glyph_index_(first_glyph_index),
      last_glyph_index_(last_glyph_index) {
  Initialize(data);
}

int32_t IndexSubTable::Builder::CheckGlyphRange(int32_t glyph_id) {
  return IndexSubTable::CheckGlyphRange(glyph_id,
                                        first_glyph_index(),
                                        last_glyph_index());
}

int32_t IndexSubTable::Builder::SerializeIndexSubHeader(
    WritableFontData* data) {
  int32_t size =
      data->WriteUShort(EblcTable::Offset::kIndexSubHeader_indexFormat,
                        index_format());
  size += data->WriteUShort(EblcTable::Offset::kIndexSubHeader_imageFormat,
                            image_format());
  size += data->WriteULong(EblcTable::Offset::kIndexSubHeader_imageDataOffset,
                           image_data_offset());
  return size;
}

void IndexSubTable::Builder::Initialize(ReadableFontData* data) {
  index_format_ =
      data->ReadUShort(EblcTable::Offset::kIndexSubHeader_indexFormat);
  image_format_ =
      data->ReadUShort(EblcTable::Offset::kIndexSubHeader_imageFormat);
  image_data_offset_ =
      data->ReadULongAsInt(EblcTable::Offset::kIndexSubHeader_imageDataOffset);
}

}  // namespace sfntly
