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

#include "sfntly/table/bitmap/eblc_table.h"

#include <stdio.h>
#include <stdlib.h>

#include "sfntly/math/font_math.h"

namespace sfntly {
/******************************************************************************
 * EblcTable class
 ******************************************************************************/
int32_t EblcTable::Version() {
  return data_->ReadFixed(Offset::kVersion);
}

int32_t EblcTable::NumSizes() {
  return data_->ReadULongAsInt(Offset::kNumSizes);
}

BitmapSizeTable* EblcTable::GetBitmapSizeTable(int32_t index) {
  if (index < 0 || index > NumSizes()) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException(
        "Size table index is outside the range of tables.");
#endif
    return NULL;
  }
  BitmapSizeTableList* bitmap_size_table_list = GetBitmapSizeTableList();
  if (bitmap_size_table_list) {
    return (*bitmap_size_table_list)[index];
  }
  return NULL;
}

EblcTable::EblcTable(Header* header, ReadableFontData* data)
    : SubTableContainerTable(header, data) {
}

BitmapSizeTableList* EblcTable::GetBitmapSizeTableList() {
  AutoLock lock(bitmap_size_table_lock_);
  if (bitmap_size_table_.empty()) {
    CreateBitmapSizeTable(data_, NumSizes(), &bitmap_size_table_);
  }
  return &bitmap_size_table_;
}

// static
void EblcTable::CreateBitmapSizeTable(ReadableFontData* data,
                                      int32_t num_sizes,
                                      BitmapSizeTableList* output) {
  assert(data);
  assert(output);
  for (int32_t i = 0; i < num_sizes; ++i) {
    ReadableFontDataPtr new_data;
    new_data.Attach(down_cast<ReadableFontData*>(
        data->Slice(Offset::kBitmapSizeTableArrayStart +
                    i * Offset::kBitmapSizeTableLength,
                    Offset::kBitmapSizeTableLength)));
    BitmapSizeTableBuilderPtr size_builder;
    size_builder.Attach(
        BitmapSizeTable::Builder::CreateBuilder(new_data, data));
    BitmapSizeTablePtr size;
    size.Attach(down_cast<BitmapSizeTable*>(size_builder->Build()));
    output->push_back(size);
  }
}

/******************************************************************************
 * EblcTable::Builder class
 ******************************************************************************/
EblcTable::Builder::Builder(Header* header, WritableFontData* data)
    : SubTableContainerTable::Builder(header, data) {
}

EblcTable::Builder::Builder(Header* header, ReadableFontData* data)
    : SubTableContainerTable::Builder(header, data) {
}

EblcTable::Builder::~Builder() {
}

int32_t EblcTable::Builder::SubSerialize(WritableFontData* new_data) {
  // header
  int32_t size = new_data->WriteFixed(0, kVersion);
  size += new_data->WriteULong(size, size_table_builders_.size());

  // calculate the offsets
  // offset to the start of the size table array
  int32_t size_table_start_offset = size;
  // walking offset in the size table array
  int32_t size_table_offset = size_table_start_offset;
  // offset to the start of the whole index subtable block
  int32_t sub_table_block_start_offset = size_table_offset +
      size_table_builders_.size() * Offset::kBitmapSizeTableLength;
  // walking offset in the index subtable
  // points to the start of the current subtable block
  int32_t current_sub_table_block_start_offset = sub_table_block_start_offset;

#if defined (SFNTLY_DEBUG_BITMAP)
  int32_t size_index = 0;
#endif
  for (BitmapSizeTableBuilderList::iterator
           size_builder = size_table_builders_.begin(),
           size_builder_end = size_table_builders_.end();
       size_builder != size_builder_end; size_builder++) {
    (*size_builder)->SetIndexSubTableArrayOffset(
        current_sub_table_block_start_offset);
    IndexSubTableBuilderList* index_sub_table_builder_list =
        (*size_builder)->IndexSubTableBuilders();

    // walking offset within the current subTable array
    int32_t index_sub_table_array_offset = current_sub_table_block_start_offset;
    // walking offset within the subTable entries
    int32_t index_sub_table_offset = index_sub_table_array_offset +
        index_sub_table_builder_list->size() * Offset::kIndexSubHeaderLength;

#if defined (SFNTLY_DEBUG_BITMAP)
    fprintf(stderr, "size %d: sizeTable=%x, current subTable Block=%x, ",
            size_index, size_table_offset,
            current_sub_table_block_start_offset);
    fprintf(stderr, "index subTableStart=%x\n", index_sub_table_offset);
    size_index++;
    int32_t sub_table_index = 0;
#endif
    for (IndexSubTableBuilderList::iterator
             index_sub_table_builder = index_sub_table_builder_list->begin(),
             index_sub_table_builder_end = index_sub_table_builder_list->end();
         index_sub_table_builder != index_sub_table_builder_end;
         index_sub_table_builder++) {
#if defined (SFNTLY_DEBUG_BITMAP)
      fprintf(stderr, "\tsubTableIndex %d: format=%x, ", sub_table_index,
              (*index_sub_table_builder)->index_format());
      fprintf(stderr, "indexSubTableArrayOffset=%x, indexSubTableOffset=%x\n",
              index_sub_table_array_offset, index_sub_table_offset);
      sub_table_index++;
#endif
      // array entry
      index_sub_table_array_offset += new_data->WriteUShort(
          index_sub_table_array_offset,
          (*index_sub_table_builder)->first_glyph_index());
      index_sub_table_array_offset += new_data->WriteUShort(
          index_sub_table_array_offset,
          (*index_sub_table_builder)->last_glyph_index());
      index_sub_table_array_offset += new_data->WriteULong(
          index_sub_table_array_offset,
          index_sub_table_offset - current_sub_table_block_start_offset);

      // index sub table
      WritableFontDataPtr slice_index_sub_table;
      slice_index_sub_table.Attach(down_cast<WritableFontData*>(
          new_data->Slice(index_sub_table_offset)));
      int32_t current_sub_table_size =
          (*index_sub_table_builder)->SubSerialize(slice_index_sub_table);
      int32_t padding = FontMath::PaddingRequired(current_sub_table_size,
                                                  DataSize::kULONG);
#if defined (SFNTLY_DEBUG_BITMAP)
      fprintf(stderr, "\t\tsubTableSize = %x, padding = %x\n",
              current_sub_table_size, padding);
#endif
      index_sub_table_offset += current_sub_table_size;
      index_sub_table_offset +=
          new_data->WritePadding(index_sub_table_offset, padding);
    }

    // serialize size table
    (*size_builder)->SetIndexTableSize(
        index_sub_table_offset - current_sub_table_block_start_offset);
    WritableFontDataPtr slice_size_table;
    slice_size_table.Attach(down_cast<WritableFontData*>(
        new_data->Slice(size_table_offset)));
    size_table_offset += (*size_builder)->SubSerialize(slice_size_table);

    current_sub_table_block_start_offset = index_sub_table_offset;
  }
  return size + current_sub_table_block_start_offset;
}

bool EblcTable::Builder::SubReadyToSerialize() {
  if (size_table_builders_.empty()) {
    return false;
  }
  for (BitmapSizeTableBuilderList::iterator b = size_table_builders_.begin(),
                                            e = size_table_builders_.end();
                                            b != e; b++) {
    if (!(*b)->SubReadyToSerialize()) {
      return false;
    }
  }
  return true;
}

int32_t EblcTable::Builder::SubDataSizeToSerialize() {
  if (size_table_builders_.empty()) {
    return 0;
  }
  int32_t size = Offset::kHeaderLength;
  bool variable = false;
#if defined (SFNTLY_DEBUG_BITMAP)
  size_t size_index = 0;
#endif
  for (BitmapSizeTableBuilderList::iterator b = size_table_builders_.begin(),
                                            e = size_table_builders_.end();
                                            b != e; b++) {
    int32_t size_builder_size = (*b)->SubDataSizeToSerialize();
#if defined (SFNTLY_DEBUG_BITMAP)
    fprintf(stderr, "sizeIndex = %d, sizeBuilderSize=0x%x (%d)\n",
            size_index++, size_builder_size, size_builder_size);
#endif
    variable = size_builder_size > 0 ? variable : true;
    size += abs(size_builder_size);
  }
#if defined (SFNTLY_DEBUG_BITMAP)
  fprintf(stderr, "eblc size=%d\n", size);
#endif
  return variable ? -size : size;
}

void EblcTable::Builder::SubDataSet() {
  Revert();
}

BitmapSizeTableBuilderList* EblcTable::Builder::BitmapSizeBuilders() {
  return GetSizeList();
}

void EblcTable::Builder::Revert() {
  size_table_builders_.clear();
  set_model_changed(false);
}

void EblcTable::Builder::GenerateLocaList(BitmapLocaList* output) {
  assert(output);
  BitmapSizeTableBuilderList* size_builder_list = GetSizeList();
  output->clear();
#if defined (SFNTLY_DEBUG_BITMAP)
  int32_t size_index = 0;
#endif
  for (BitmapSizeTableBuilderList::iterator b = size_builder_list->begin(),
                                            e = size_builder_list->end();
                                            b != e; b++) {
#if defined (SFNTLY_DEBUG_BITMAP)
    fprintf(stderr, "size table = %d\n", size_index++);
#endif
    BitmapGlyphInfoMap loca_map;
    (*b)->GenerateLocaMap(&loca_map);
    output->push_back(loca_map);
  }
}

CALLER_ATTACH
FontDataTable* EblcTable::Builder::SubBuildTable(ReadableFontData* data) {
  Ptr<EblcTable> new_table = new EblcTable(header(), data);
  return new_table.Detach();
}

// static
CALLER_ATTACH EblcTable::Builder*
    EblcTable::Builder::CreateBuilder(Header* header, WritableFontData* data) {
  Ptr<EblcTable::Builder> new_builder = new EblcTable::Builder(header, data);
  return new_builder.Detach();
}

// static
CALLER_ATTACH EblcTable::Builder*
    EblcTable::Builder::CreateBuilder(Header* header, ReadableFontData* data) {
  Ptr<EblcTable::Builder> new_builder = new EblcTable::Builder(header, data);
  return new_builder.Detach();
}

BitmapSizeTableBuilderList* EblcTable::Builder::GetSizeList() {
  if (size_table_builders_.empty()) {
    Initialize(InternalReadData(), &size_table_builders_);
    set_model_changed();
  }
  return &size_table_builders_;
}

void EblcTable::Builder::Initialize(ReadableFontData* data,
                                    BitmapSizeTableBuilderList* output) {
  assert(output);
  if (data) {
    int32_t num_sizes = data->ReadULongAsInt(Offset::kNumSizes);
    for (int32_t i = 0; i < num_sizes; ++i) {
      ReadableFontDataPtr new_data;
      new_data.Attach(down_cast<ReadableFontData*>(
          data->Slice(Offset::kBitmapSizeTableArrayStart +
                      i * Offset::kBitmapSizeTableLength,
                      Offset::kBitmapSizeTableLength)));
      BitmapSizeTableBuilderPtr size_builder;
      size_builder.Attach(BitmapSizeTable::Builder::CreateBuilder(
          new_data, data));
      output->push_back(size_builder);
    }
  }
}

}  // namespace sfntly
