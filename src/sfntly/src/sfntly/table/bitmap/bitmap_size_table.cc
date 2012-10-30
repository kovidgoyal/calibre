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

#include "sfntly/table/bitmap/bitmap_size_table.h"

#include <stdio.h>
#include <stdlib.h>

#include "sfntly/math/font_math.h"
#include "sfntly/table/bitmap/eblc_table.h"
#include "sfntly/table/bitmap/index_sub_table_format1.h"
#include "sfntly/table/bitmap/index_sub_table_format2.h"
#include "sfntly/table/bitmap/index_sub_table_format3.h"
#include "sfntly/table/bitmap/index_sub_table_format4.h"
#include "sfntly/table/bitmap/index_sub_table_format5.h"

namespace sfntly {
/******************************************************************************
 * BitmapSizeTable class
 ******************************************************************************/
BitmapSizeTable::~BitmapSizeTable() {
}

int32_t BitmapSizeTable::IndexSubTableArrayOffset() {
  return data_->ReadULongAsInt(
      EblcTable::Offset::kBitmapSizeTable_indexSubTableArrayOffset);
}

int32_t BitmapSizeTable::IndexTableSize() {
  return data_->ReadULongAsInt(
      EblcTable::Offset::kBitmapSizeTable_indexTableSize);
}

int32_t BitmapSizeTable::NumberOfIndexSubTables() {
  return NumberOfIndexSubTables(data_, 0);
}

int32_t BitmapSizeTable::ColorRef() {
  return data_->ReadULongAsInt(EblcTable::Offset::kBitmapSizeTable_colorRef);
}

int32_t BitmapSizeTable::StartGlyphIndex() {
  return data_->ReadUShort(EblcTable::Offset::kBitmapSizeTable_startGlyphIndex);
}

int32_t BitmapSizeTable::EndGlyphIndex() {
  return data_->ReadUShort(EblcTable::Offset::kBitmapSizeTable_endGlyphIndex);
}

int32_t BitmapSizeTable::PpemX() {
  return data_->ReadByte(EblcTable::Offset::kBitmapSizeTable_ppemX);
}

int32_t BitmapSizeTable::PpemY() {
  return data_->ReadByte(EblcTable::Offset::kBitmapSizeTable_ppemY);
}

int32_t BitmapSizeTable::BitDepth() {
  return data_->ReadByte(EblcTable::Offset::kBitmapSizeTable_bitDepth);
}

int32_t BitmapSizeTable::FlagsAsInt() {
  return data_->ReadChar(EblcTable::Offset::kBitmapSizeTable_flags);
}

IndexSubTable* BitmapSizeTable::GetIndexSubTable(int32_t index) {
  IndexSubTableList* subtable_list = GetIndexSubTableList();
  if (index >= 0 && (size_t)index < subtable_list->size()) {
    return (*subtable_list)[index];
  }
  return NULL;
}

int32_t BitmapSizeTable::GlyphOffset(int32_t glyph_id) {
  IndexSubTable* subtable = SearchIndexSubTables(glyph_id);
  if (subtable == NULL) {
    return -1;
  }
  return subtable->GlyphOffset(glyph_id);
}

int32_t BitmapSizeTable::GlyphLength(int32_t glyph_id) {
  IndexSubTable* subtable = SearchIndexSubTables(glyph_id);
  if (subtable == NULL) {
    return -1;
  }
  return subtable->GlyphLength(glyph_id);
}

CALLER_ATTACH BitmapGlyphInfo* BitmapSizeTable::GlyphInfo(int32_t glyph_id) {
  IndexSubTable* sub_table = SearchIndexSubTables(glyph_id);
  if (sub_table == NULL) {
    return NULL;
  }
  return sub_table->GlyphInfo(glyph_id);
}

int32_t BitmapSizeTable::GlyphFormat(int32_t glyph_id) {
  IndexSubTable* subtable = SearchIndexSubTables(glyph_id);
  if (subtable == NULL) {
    return -1;
  }
  return subtable->image_format();
}

BitmapSizeTable::BitmapSizeTable(ReadableFontData* data,
                                 ReadableFontData* master_data)
    : SubTable(data, master_data) {
}

// static
int32_t BitmapSizeTable::NumberOfIndexSubTables(ReadableFontData* data,
                                                int32_t table_offset) {
  return data->ReadULongAsInt(table_offset +
      EblcTable::Offset::kBitmapSizeTable_numberOfIndexSubTables);
}

IndexSubTable* BitmapSizeTable::SearchIndexSubTables(int32_t glyph_id) {
  // would be faster to binary search but too many size tables don't have
  // sorted subtables
#if (SFNTLY_BITMAPSIZE_USE_BINARY_SEARCH)
  return BinarySearchIndexSubTables(glyph_id);
#else
  return LinearSearchIndexSubTables(glyph_id);
#endif
}

IndexSubTable* BitmapSizeTable::LinearSearchIndexSubTables(int32_t glyph_id) {
  IndexSubTableList* subtable_list = GetIndexSubTableList();
  for (IndexSubTableList::iterator b = subtable_list->begin(),
                                   e = subtable_list->end(); b != e; b++) {
    if ((*b)->first_glyph_index() <= glyph_id &&
        (*b)->last_glyph_index() >= glyph_id) {
      return *b;
    }
  }
  return NULL;
}

IndexSubTable* BitmapSizeTable::BinarySearchIndexSubTables(int32_t glyph_id) {
  IndexSubTableList* subtable_list = GetIndexSubTableList();
  int32_t index = 0;
  int32_t bottom = 0;
  int32_t top = subtable_list->size();
  while (top != bottom) {
    index = (top + bottom) / 2;
    IndexSubTable* subtable = (*subtable_list)[index];
    if (glyph_id < subtable->first_glyph_index()) {
      // Location beow current location
      top = index;
    } else {
      if (glyph_id <= subtable->last_glyph_index()) {
        return subtable;
      } else {
        bottom = index + 1;
      }
    }
  }
  return NULL;
}

CALLER_ATTACH
IndexSubTable* BitmapSizeTable::CreateIndexSubTable(int32_t index) {
  return IndexSubTable::CreateIndexSubTable(master_read_data(),
                                            IndexSubTableArrayOffset(),
                                            index);
}

IndexSubTableList* BitmapSizeTable::GetIndexSubTableList() {
  AutoLock lock(index_subtables_lock_);
  if (index_subtables_.empty()) {
    for (int32_t i = 0; i < NumberOfIndexSubTables(); ++i) {
      IndexSubTablePtr table;
      table.Attach(CreateIndexSubTable(i));
      index_subtables_.push_back(table);
    }
  }
  return &index_subtables_;
}

/******************************************************************************
 * BitmapSizeTable::Builder class
 ******************************************************************************/
BitmapSizeTable::Builder::~Builder() {
}

CALLER_ATTACH
FontDataTable* BitmapSizeTable::Builder::SubBuildTable(ReadableFontData* data) {
  BitmapSizeTablePtr output = new BitmapSizeTable(data, master_read_data());
  return output.Detach();
}

void BitmapSizeTable::Builder::SubDataSet() {
  Revert();
}

int32_t BitmapSizeTable::Builder::SubDataSizeToSerialize() {
  IndexSubTableBuilderList* builders = IndexSubTableBuilders();
  if (builders->empty()) {
    return 0;
  }
  int32_t size = EblcTable::Offset::kBitmapSizeTableLength;
  bool variable = false;
  for (IndexSubTableBuilderList::iterator b = builders->begin(),
                                          e = builders->end(); b != e; b++) {
    size += EblcTable::Offset::kIndexSubTableEntryLength;
    int32_t sub_table_size = (*b)->SubDataSizeToSerialize();
    int32_t padding = FontMath::PaddingRequired(abs(sub_table_size),
                                                DataSize::kULONG);
#if defined (SFNTLY_DEBUG_BITMAP)
    fprintf(stderr, "subtable size=%d\n", sub_table_size);
#endif
    variable = (sub_table_size > 0) ? variable : true;
    size += abs(sub_table_size) + padding;
  }
#if defined (SFNTLY_DEBUG_BITMAP)
  fprintf(stderr, "bitmap table size=%d\n", variable ? -size : size);
#endif
  return variable ? -size : size;
}

bool BitmapSizeTable::Builder::SubReadyToSerialize() {
  if (IndexSubTableBuilders()->empty()) {
    return false;
  }
  return true;
}

int32_t BitmapSizeTable::Builder::SubSerialize(WritableFontData* new_data) {
  SetNumberOfIndexSubTables(IndexSubTableBuilders()->size());
  int32_t size = InternalReadData()->CopyTo(new_data);
  return size;
}

CALLER_ATTACH BitmapSizeTable::Builder*
BitmapSizeTable::Builder::CreateBuilder(WritableFontData* data,
                                        ReadableFontData* master_data) {
  BitmapSizeTableBuilderPtr output =
      new BitmapSizeTable::Builder(data, master_data);
  return output.Detach();
}

CALLER_ATTACH BitmapSizeTable::Builder*
BitmapSizeTable::Builder::CreateBuilder(ReadableFontData* data,
                                        ReadableFontData* master_data) {
  BitmapSizeTableBuilderPtr output =
      new BitmapSizeTable::Builder(data, master_data);
  return output.Detach();
}

int32_t BitmapSizeTable::Builder::IndexSubTableArrayOffset() {
  return InternalReadData()->ReadULongAsInt(
      EblcTable::Offset::kBitmapSizeTable_indexSubTableArrayOffset);
}

void BitmapSizeTable::Builder::SetIndexSubTableArrayOffset(int32_t offset) {
  InternalWriteData()->WriteULong(
      EblcTable::Offset::kBitmapSizeTable_indexSubTableArrayOffset, offset);
}

int32_t BitmapSizeTable::Builder::IndexTableSize() {
  return InternalReadData()->ReadULongAsInt(
      EblcTable::Offset::kBitmapSizeTable_indexTableSize);
}

void BitmapSizeTable::Builder::SetIndexTableSize(int32_t size) {
  InternalWriteData()->WriteULong(
      EblcTable::Offset::kBitmapSizeTable_indexTableSize, size);
}

int32_t BitmapSizeTable::Builder::NumberOfIndexSubTables() {
  return GetIndexSubTableBuilders()->size();
}

int32_t BitmapSizeTable::Builder::ColorRef() {
  return InternalReadData()->ReadULongAsInt(
      EblcTable::Offset::kBitmapSizeTable_colorRef);
}

int32_t BitmapSizeTable::Builder::StartGlyphIndex() {
  return InternalReadData()->ReadUShort(
      EblcTable::Offset::kBitmapSizeTable_startGlyphIndex);
}

int32_t BitmapSizeTable::Builder::EndGlyphIndex() {
  return InternalReadData()->ReadUShort(
      EblcTable::Offset::kBitmapSizeTable_endGlyphIndex);
}

int32_t BitmapSizeTable::Builder::PpemX() {
  return InternalReadData()->ReadByte(
      EblcTable::Offset::kBitmapSizeTable_ppemX);
}

int32_t BitmapSizeTable::Builder::PpemY() {
  return InternalReadData()->ReadByte(
      EblcTable::Offset::kBitmapSizeTable_ppemY);
}

int32_t BitmapSizeTable::Builder::BitDepth() {
  return InternalReadData()->ReadByte(
      EblcTable::Offset::kBitmapSizeTable_bitDepth);
}

int32_t BitmapSizeTable::Builder::FlagsAsInt() {
  return InternalReadData()->ReadChar(
      EblcTable::Offset::kBitmapSizeTable_flags);
}

IndexSubTable::Builder* BitmapSizeTable::Builder::IndexSubTableBuilder(
    int32_t index) {
  IndexSubTableBuilderList* sub_table_list = GetIndexSubTableBuilders();
  return sub_table_list->at(index);
}

CALLER_ATTACH BitmapGlyphInfo* BitmapSizeTable::Builder::GlyphInfo(
    int32_t glyph_id) {
  IndexSubTable::Builder* sub_table = SearchIndexSubTables(glyph_id);
  if (sub_table == NULL) {
    return NULL;
  }
  return sub_table->GlyphInfo(glyph_id);
}

int32_t BitmapSizeTable::Builder::GlyphOffset(int32_t glyph_id) {
  IndexSubTable::Builder* subtable = SearchIndexSubTables(glyph_id);
  if (subtable == NULL) {
    return -1;
  }
  return subtable->GlyphOffset(glyph_id);
}

int32_t BitmapSizeTable::Builder::GlyphLength(int32_t glyph_id) {
  IndexSubTable::Builder* subtable = SearchIndexSubTables(glyph_id);
  if (subtable == NULL) {
    return -1;
  }
  return subtable->GlyphLength(glyph_id);
}

int32_t BitmapSizeTable::Builder::GlyphFormat(int32_t glyph_id) {
  IndexSubTable::Builder* subtable = SearchIndexSubTables(glyph_id);
  if (subtable == NULL) {
    return -1;
  }
  return subtable->image_format();
}

IndexSubTableBuilderList* BitmapSizeTable::Builder::IndexSubTableBuilders() {
  return GetIndexSubTableBuilders();
}

CALLER_ATTACH BitmapSizeTable::Builder::BitmapGlyphInfoIterator*
BitmapSizeTable::Builder::GetIterator() {
  Ptr<BitmapSizeTable::Builder::BitmapGlyphInfoIterator> output =
      new BitmapSizeTable::Builder::BitmapGlyphInfoIterator(this);
  return output.Detach();
}

void BitmapSizeTable::Builder::GenerateLocaMap(BitmapGlyphInfoMap* output) {
  assert(output);
  Ptr<BitmapSizeTable::Builder::BitmapGlyphInfoIterator> it;
  it.Attach(GetIterator());
  while (it->HasNext()) {
    BitmapGlyphInfoPtr info;
    info.Attach(it->Next());
    (*output)[info->glyph_id()] = info;
  }
}

void BitmapSizeTable::Builder::Revert() {
  index_sub_tables_.clear();
  set_model_changed(false);
}

BitmapSizeTable::Builder::Builder(WritableFontData* data,
                                  ReadableFontData* master_data)
    : SubTable::Builder(data, master_data) {
}

BitmapSizeTable::Builder::Builder(ReadableFontData* data,
                                  ReadableFontData* master_data)
    : SubTable::Builder(data, master_data) {
}

void BitmapSizeTable::Builder::SetNumberOfIndexSubTables(int32_t count) {
  InternalWriteData()->WriteULong(
      EblcTable::Offset::kBitmapSizeTable_numberOfIndexSubTables, count);
}

IndexSubTable::Builder* BitmapSizeTable::Builder::SearchIndexSubTables(
    int32_t glyph_id) {
  // would be faster to binary search but too many size tables don't have
  // sorted subtables
#if (SFNTLY_BITMAPSIZE_USE_BINARY_SEARCH)
  return BinarySearchIndexSubTables(glyph_id);
#else
  return LinearSearchIndexSubTables(glyph_id);
#endif
}

IndexSubTable::Builder* BitmapSizeTable::Builder::LinearSearchIndexSubTables(
    int32_t glyph_id) {
  IndexSubTableBuilderList* subtable_list = GetIndexSubTableBuilders();
  for (IndexSubTableBuilderList::iterator b = subtable_list->begin(),
                                          e = subtable_list->end();
                                          b != e; b++) {
    if ((*b)->first_glyph_index() <= glyph_id &&
        (*b)->last_glyph_index() >= glyph_id) {
      return *b;
    }
  }
  return NULL;
}

IndexSubTable::Builder* BitmapSizeTable::Builder::BinarySearchIndexSubTables(
    int32_t glyph_id) {
  IndexSubTableBuilderList* subtable_list = GetIndexSubTableBuilders();
  int32_t index = 0;
  int32_t bottom = 0;
  int32_t top = subtable_list->size();
  while (top != bottom) {
    index = (top + bottom) / 2;
    IndexSubTable::Builder* subtable = subtable_list->at(index);
    if (glyph_id < subtable->first_glyph_index()) {
      // Location beow current location
      top = index;
    } else {
      if (glyph_id <= subtable->last_glyph_index()) {
        return subtable;
      } else {
        bottom = index + 1;
      }
    }
  }
  return NULL;
}

IndexSubTableBuilderList* BitmapSizeTable::Builder::GetIndexSubTableBuilders() {
  if (index_sub_tables_.empty()) {
    Initialize(InternalReadData());
    set_model_changed();
  }
  return &index_sub_tables_;
}

void BitmapSizeTable::Builder::Initialize(ReadableFontData* data) {
  index_sub_tables_.clear();
  if (data) {
    int32_t number_of_index_subtables =
        BitmapSizeTable::NumberOfIndexSubTables(data, 0);
    index_sub_tables_.resize(number_of_index_subtables);
    for (int32_t i = 0; i < number_of_index_subtables; ++i) {
      index_sub_tables_[i].Attach(CreateIndexSubTableBuilder(i));
    }
  }
}

CALLER_ATTACH IndexSubTable::Builder*
BitmapSizeTable::Builder::CreateIndexSubTableBuilder(int32_t index) {
  return IndexSubTable::Builder::CreateBuilder(master_read_data(),
                                               IndexSubTableArrayOffset(),
                                               index);
}

/******************************************************************************
 * BitmapSizeTable::Builder::BitmapGlyphInfoIterator class
 ******************************************************************************/
BitmapSizeTable::Builder::BitmapGlyphInfoIterator::BitmapGlyphInfoIterator(
    BitmapSizeTable::Builder* container)
    : RefIterator<BitmapGlyphInfo, BitmapSizeTable::Builder>(container) {
  sub_table_iter_ = container->IndexSubTableBuilders()->begin();
  sub_table_glyph_info_iter_.Attach((*sub_table_iter_)->GetIterator());
}

bool BitmapSizeTable::Builder::BitmapGlyphInfoIterator::HasNext() {
  if (sub_table_glyph_info_iter_ && HasNext(sub_table_glyph_info_iter_)) {
    return true;
  }
  while (++sub_table_iter_ != container()->IndexSubTableBuilders()->end()) {
    sub_table_glyph_info_iter_.Attach((*sub_table_iter_)->GetIterator());
    if (HasNext(sub_table_glyph_info_iter_)) {
      return true;
    }
  }
  return false;
}

CALLER_ATTACH
BitmapGlyphInfo* BitmapSizeTable::Builder::BitmapGlyphInfoIterator::Next() {
  if (!HasNext()) {
    // Note: In C++, we do not throw exception when there's no element.
    return NULL;
  }
  return Next(sub_table_glyph_info_iter_);
}

bool BitmapSizeTable::Builder::BitmapGlyphInfoIterator::HasNext(
    BitmapGlyphInfoIter* iterator_base) {
  if (iterator_base) {
    switch (iterator_base->container_base()->index_format()) {
      case 1: {
        IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator* it =
            down_cast<IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator*>(
                iterator_base);
        return it->HasNext();
      }

      case 2: {
        IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator* it =
            down_cast<IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator*>(
                iterator_base);
        return it->HasNext();
      }

      case 3: {
        IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator* it =
            down_cast<IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator*>(
                iterator_base);
        return it->HasNext();
      }

      case 4: {
        IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator* it =
            down_cast<IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator*>(
                iterator_base);
        return it->HasNext();
      }

      case 5: {
        IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator* it =
            down_cast<IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator*>(
                iterator_base);
        return it->HasNext();
      }

      default:
        break;
    }
  }
  return false;
}

CALLER_ATTACH
BitmapGlyphInfo* BitmapSizeTable::Builder::BitmapGlyphInfoIterator::Next(
    BitmapGlyphInfoIter* iterator_base) {
  if (iterator_base) {
    switch (iterator_base->container_base()->index_format()) {
      case 1: {
        IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator* it =
            down_cast<IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator*>(
                iterator_base);
        return it->Next();
      }

      case 2: {
        IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator* it =
            down_cast<IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator*>(
                iterator_base);
        return it->Next();
      }

      case 3: {
        IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator* it =
            down_cast<IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator*>(
                iterator_base);
        return it->Next();
      }

      case 4: {
        IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator* it =
            down_cast<IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator*>(
                iterator_base);
        return it->Next();
      }

      case 5: {
        IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator* it =
            down_cast<IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator*>(
                iterator_base);
        return it->Next();
      }

      default:
        break;
    }
  }
  return NULL;
}

}  // namespace sfntly
