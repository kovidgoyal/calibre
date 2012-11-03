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

#include "sfntly/table/bitmap/index_sub_table_format1.h"

#include "sfntly/table/bitmap/eblc_table.h"

namespace sfntly {
/******************************************************************************
 * IndexSubTableFormat1 class
 ******************************************************************************/
// static
int32_t IndexSubTableFormat1::GetDataLength(ReadableFontData* data,
                                            int32_t offset,
                                            int32_t first,
                                            int32_t last) {
  UNREFERENCED_PARAMETER(data);
  UNREFERENCED_PARAMETER(offset);
  return (last - first + 1 + 1) * DataSize::kULONG;
}

IndexSubTableFormat1::~IndexSubTableFormat1() {
}

int32_t IndexSubTableFormat1::NumGlyphs() {
  return last_glyph_index() - first_glyph_index() + 1;
}

int32_t IndexSubTableFormat1::GlyphStartOffset(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return -1;
  }
  return Loca(loca);
}

int32_t IndexSubTableFormat1::GlyphLength(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return -1;
  }
  return Loca(loca + 1) - Loca(loca);
}

IndexSubTableFormat1::IndexSubTableFormat1(ReadableFontData* data,
                                           int32_t first_glyph_index,
                                           int32_t last_glyph_index)
    : IndexSubTable(data, first_glyph_index, last_glyph_index) {
}

int32_t IndexSubTableFormat1::Loca(int32_t loca) {
  return image_data_offset() +
         data_->ReadULongAsInt(EblcTable::Offset::kIndexSubTable1_offsetArray +
                               loca * DataSize::kULONG);
}

/******************************************************************************
 * IndexSubTableFormat1::Builder class
 ******************************************************************************/
IndexSubTableFormat1::Builder::~Builder() {
}

int32_t IndexSubTableFormat1::Builder::NumGlyphs() {
  return GetOffsetArray()->size() - 1;
}

int32_t IndexSubTableFormat1::Builder::GlyphLength(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return 0;
  }
  IntegerList* offset_array = GetOffsetArray();
  return offset_array->at(loca + 1) - offset_array->at(loca);
}

int32_t IndexSubTableFormat1::Builder::GlyphStartOffset(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return -1;
  }
  return GetOffsetArray()->at(loca);
}

CALLER_ATTACH IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator*
    IndexSubTableFormat1::Builder::GetIterator() {
  Ptr<IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator> it =
      new IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator(this);
  return it.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat1::Builder*
IndexSubTableFormat1::Builder::CreateBuilder() {
  IndexSubTableFormat1BuilderPtr output = new IndexSubTableFormat1::Builder();
  return output.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat1::Builder*
IndexSubTableFormat1::Builder::CreateBuilder(ReadableFontData* data,
                                             int32_t index_sub_table_offset,
                                             int32_t first_glyph_index,
                                             int32_t last_glyph_index) {
  int32_t length = Builder::DataLength(data,
                                       index_sub_table_offset,
                                       first_glyph_index,
                                       last_glyph_index);
  ReadableFontDataPtr new_data;
  new_data.Attach(down_cast<ReadableFontData*>(
      data->Slice(index_sub_table_offset, length)));
  IndexSubTableFormat1BuilderPtr output =
      new IndexSubTableFormat1::Builder(new_data,
                                        first_glyph_index,
                                        last_glyph_index);
  return output.Detach();
}


// static
CALLER_ATTACH IndexSubTableFormat1::Builder*
IndexSubTableFormat1::Builder::CreateBuilder(WritableFontData* data,
                                             int32_t index_sub_table_offset,
                                             int32_t first_glyph_index,
                                             int32_t last_glyph_index) {
  int32_t length = Builder::DataLength(data,
                                       index_sub_table_offset,
                                       first_glyph_index,
                                       last_glyph_index);
  WritableFontDataPtr new_data;
  new_data.Attach(down_cast<WritableFontData*>(
      data->Slice(index_sub_table_offset, length)));
  IndexSubTableFormat1BuilderPtr output =
      new IndexSubTableFormat1::Builder(new_data,
                                        first_glyph_index,
                                        last_glyph_index);
  return output.Detach();
}

CALLER_ATTACH FontDataTable* IndexSubTableFormat1::Builder::SubBuildTable(
    ReadableFontData* data) {
  IndexSubTableFormat1Ptr output = new IndexSubTableFormat1(
      data, first_glyph_index(), last_glyph_index());
  return output.Detach();
}

void IndexSubTableFormat1::Builder::SubDataSet() {
  Revert();
}

int32_t IndexSubTableFormat1::Builder::SubDataSizeToSerialize() {
  if (offset_array_.empty()) {
    return InternalReadData()->Length();
  }
  return EblcTable::Offset::kIndexSubHeaderLength +
         offset_array_.size() * DataSize::kULONG;
}

bool IndexSubTableFormat1::Builder::SubReadyToSerialize() {
  if (!offset_array_.empty()) {
    return true;
  }
  return false;
}

int32_t IndexSubTableFormat1::Builder::SubSerialize(
    WritableFontData* new_data) {
  int32_t size = SerializeIndexSubHeader(new_data);
  if (!model_changed()) {
    if (InternalReadData() == NULL) {
      return size;
    }
    ReadableFontDataPtr source;
    WritableFontDataPtr target;
    source.Attach(down_cast<ReadableFontData*>(InternalReadData()->Slice(
        EblcTable::Offset::kIndexSubTable1_offsetArray)));
    target.Attach(down_cast<WritableFontData*>(new_data->Slice(
        EblcTable::Offset::kIndexSubTable1_offsetArray)));
    size += source->CopyTo(target);
  } else {
    for (IntegerList::iterator b = GetOffsetArray()->begin(),
                               e = GetOffsetArray()->end(); b != e; b++) {
      size += new_data->WriteLong(size, *b);
    }
  }
  return size;
}

IntegerList* IndexSubTableFormat1::Builder::OffsetArray() {
  return GetOffsetArray();
}

void IndexSubTableFormat1::Builder::SetOffsetArray(
    const IntegerList& offset_array) {
  offset_array_.clear();
  offset_array_ = offset_array;
  set_model_changed();
}

void IndexSubTableFormat1::Builder::Revert() {
  offset_array_.clear();
  IndexSubTable::Builder::Revert();
}

IndexSubTableFormat1::Builder::Builder()
    : IndexSubTable::Builder(EblcTable::Offset::kIndexSubTable1_builderDataSize,
                             IndexSubTable::Format::FORMAT_1) {
}

IndexSubTableFormat1::Builder::Builder(WritableFontData* data,
                                       int32_t first_glyph_index,
                                       int32_t last_glyph_index)
    : IndexSubTable::Builder(data, first_glyph_index, last_glyph_index) {
}

IndexSubTableFormat1::Builder::Builder(ReadableFontData* data,
                                       int32_t first_glyph_index,
                                       int32_t last_glyph_index)
    : IndexSubTable::Builder(data, first_glyph_index, last_glyph_index) {
}

IntegerList* IndexSubTableFormat1::Builder::GetOffsetArray() {
  if (offset_array_.empty()) {
    Initialize(InternalReadData());
    set_model_changed();
  }
  return &offset_array_;
}

void IndexSubTableFormat1::Builder::Initialize(ReadableFontData* data) {
  offset_array_.clear();
  if (data) {
    int32_t num_offsets = (last_glyph_index() - first_glyph_index() + 1) + 1;
    for (int32_t i = 0; i < num_offsets; ++i) {
      offset_array_.push_back(data->ReadULongAsInt(
          EblcTable::Offset::kIndexSubTable1_offsetArray +
          i * DataSize::kULONG));
    }
  }
}

// static
int32_t IndexSubTableFormat1::Builder::DataLength(
    ReadableFontData* data,
    int32_t index_sub_table_offset,
    int32_t first_glyph_index,
    int32_t last_glyph_index) {
  UNREFERENCED_PARAMETER(data);
  UNREFERENCED_PARAMETER(index_sub_table_offset);
  return EblcTable::Offset::kIndexSubHeaderLength +
         (last_glyph_index - first_glyph_index + 1 + 1) * DataSize::kULONG;
}

/******************************************************************************
 * IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator class
 ******************************************************************************/
IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator::BitmapGlyphInfoIterator(
    IndexSubTableFormat1::Builder* container)
    : RefIterator<BitmapGlyphInfo, IndexSubTableFormat1::Builder,
                  IndexSubTable::Builder>(container) {
  glyph_id_ = container->first_glyph_index();
}

bool IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator::HasNext() {
  if (glyph_id_ <= container()->last_glyph_index()) {
    return true;
  }
  return false;
}

CALLER_ATTACH BitmapGlyphInfo*
IndexSubTableFormat1::Builder::BitmapGlyphInfoIterator::Next() {
  BitmapGlyphInfoPtr output;
  if (!HasNext()) {
    // Note: In C++, we do not throw exception when there's no element.
    return NULL;
  }
  output = new BitmapGlyphInfo(glyph_id_,
                               container()->image_data_offset(),
                               container()->GlyphStartOffset(glyph_id_),
                               container()->GlyphLength(glyph_id_),
                               container()->image_format());
  glyph_id_++;
  return output.Detach();
}

}  // namespace sfntly
