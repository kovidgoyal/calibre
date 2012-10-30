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

#include "sfntly/table/bitmap/index_sub_table_format3.h"

#include "sfntly/table/bitmap/eblc_table.h"

namespace sfntly {
/******************************************************************************
 * IndexSubTableFormat3 class
 ******************************************************************************/
IndexSubTableFormat3::~IndexSubTableFormat3() {
}

int32_t IndexSubTableFormat3::NumGlyphs() {
  return last_glyph_index() - first_glyph_index() + 1;
}

int32_t IndexSubTableFormat3::GlyphStartOffset(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca != -1) {
    return Loca(loca);
  }
  return -1;
}

int32_t IndexSubTableFormat3::GlyphLength(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca != -1) {
    return Loca(glyph_id + 1) - Loca(glyph_id);
  }
  return 0;
}

// static
int32_t IndexSubTableFormat3::GetDataLength(ReadableFontData* data,
                                            int32_t offset,
                                            int32_t first,
                                            int32_t last) {
  UNREFERENCED_PARAMETER(data);
  UNREFERENCED_PARAMETER(offset);
  return (last - first + 1 + 1) * DataSize::kUSHORT;
}

IndexSubTableFormat3::IndexSubTableFormat3(ReadableFontData* data,
                                           int32_t first_glyph_index,
                                           int32_t last_glyph_index)
    : IndexSubTable(data, first_glyph_index, last_glyph_index) {
}

int32_t IndexSubTableFormat3::Loca(int32_t loca) {
  int32_t read_offset =
      data_->ReadUShort(EblcTable::Offset::kIndexSubTable3_offsetArray +
                        loca * DataSize::kUSHORT);
  return read_offset;
}

/******************************************************************************
 * IndexSubTableFormat3::Builder class
 ******************************************************************************/
IndexSubTableFormat3::Builder::~Builder() {
}

int32_t IndexSubTableFormat3::Builder::NumGlyphs() {
  return GetOffsetArray()->size() - 1;
}

int32_t IndexSubTableFormat3::Builder::GlyphStartOffset(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return -1;
  }
  return GetOffsetArray()->at(loca);
}

int32_t IndexSubTableFormat3::Builder::GlyphLength(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return 0;
  }
  IntegerList* offset_array = GetOffsetArray();
  return offset_array->at(loca + 1) - offset_array->at(loca);
}

CALLER_ATTACH IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator*
    IndexSubTableFormat3::Builder::GetIterator() {
  Ptr<IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator> it =
      new IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator(this);
  return it.Detach();
}

void IndexSubTableFormat3::Builder::Revert() {
  offset_array_.clear();
  IndexSubTable::Builder::Revert();
}

void IndexSubTableFormat3::Builder::SetOffsetArray(
    const IntegerList& offset_array) {
  offset_array_.clear();
  offset_array_ = offset_array;
  set_model_changed();
}

// static
CALLER_ATTACH IndexSubTableFormat3::Builder*
IndexSubTableFormat3::Builder::CreateBuilder() {
  IndexSubTableFormat3BuilderPtr output = new IndexSubTableFormat3::Builder();
  return output.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat3::Builder*
IndexSubTableFormat3::Builder::CreateBuilder(ReadableFontData* data,
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
  IndexSubTableFormat3BuilderPtr output =
      new IndexSubTableFormat3::Builder(new_data,
                                        first_glyph_index,
                                        last_glyph_index);
  return output.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat3::Builder*
IndexSubTableFormat3::Builder::CreateBuilder(WritableFontData* data,
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
  IndexSubTableFormat3BuilderPtr output =
      new IndexSubTableFormat3::Builder(new_data,
                                        first_glyph_index,
                                        last_glyph_index);
  return output.Detach();
}

CALLER_ATTACH FontDataTable* IndexSubTableFormat3::Builder::SubBuildTable(
    ReadableFontData* data) {
  IndexSubTableFormat3Ptr output = new IndexSubTableFormat3(
      data, first_glyph_index(), last_glyph_index());
  return output.Detach();
}

void IndexSubTableFormat3::Builder::SubDataSet() {
  Revert();
}

int32_t IndexSubTableFormat3::Builder::SubDataSizeToSerialize() {
  if (offset_array_.empty()) {
    return InternalReadData()->Length();
  }
  return EblcTable::Offset::kIndexSubHeaderLength +
         offset_array_.size() * DataSize::kULONG;
}

bool IndexSubTableFormat3::Builder::SubReadyToSerialize() {
  if (!offset_array_.empty()) {
    return true;
  }
  return false;
}

int32_t IndexSubTableFormat3::Builder::SubSerialize(
    WritableFontData* new_data) {
  int32_t size = SerializeIndexSubHeader(new_data);
  if (!model_changed()) {
    if (InternalReadData() == NULL) {
      return size;
    }
    ReadableFontDataPtr source;
    WritableFontDataPtr target;
    source.Attach(down_cast<ReadableFontData*>(InternalReadData()->Slice(
        EblcTable::Offset::kIndexSubTable3_offsetArray)));
    target.Attach(down_cast<WritableFontData*>(new_data->Slice(
        EblcTable::Offset::kIndexSubTable3_offsetArray)));
    size += source->CopyTo(target);
  } else {
    for (IntegerList::iterator b = GetOffsetArray()->begin(),
                               e = GetOffsetArray()->end(); b != e; b++) {
      size += new_data->WriteUShort(size, *b);
    }
  }
  return size;
}

IndexSubTableFormat3::Builder::Builder()
    : IndexSubTable::Builder(EblcTable::Offset::kIndexSubTable3_builderDataSize,
                             IndexSubTable::Format::FORMAT_3) {
}

IndexSubTableFormat3::Builder::Builder(WritableFontData* data,
                                       int32_t first_glyph_index,
                                       int32_t last_glyph_index)
    : IndexSubTable::Builder(data, first_glyph_index, last_glyph_index) {
}

IndexSubTableFormat3::Builder::Builder(ReadableFontData* data,
                                       int32_t first_glyph_index,
                                       int32_t last_glyph_index)
    : IndexSubTable::Builder(data, first_glyph_index, last_glyph_index) {
}

IntegerList* IndexSubTableFormat3::Builder::GetOffsetArray() {
  if (offset_array_.empty()) {
    Initialize(InternalReadData());
    set_model_changed();
  }
  return &offset_array_;
}

void IndexSubTableFormat3::Builder::Initialize(ReadableFontData* data) {
  offset_array_.clear();
  if (data) {
    int32_t num_offsets = (last_glyph_index() - first_glyph_index() + 1) + 1;
    for (int32_t i = 0; i < num_offsets; ++i) {
      offset_array_.push_back(data->ReadUShort(
         EblcTable::Offset::kIndexSubTable3_offsetArray +
         i * DataSize::kUSHORT));
    }
  }
}

// static
int32_t IndexSubTableFormat3::Builder::DataLength(
    ReadableFontData* data,
    int32_t index_sub_table_offset,
    int32_t first_glyph_index,
    int32_t last_glyph_index) {
  UNREFERENCED_PARAMETER(data);
  UNREFERENCED_PARAMETER(index_sub_table_offset);
  return EblcTable::Offset::kIndexSubHeaderLength +
         (last_glyph_index - first_glyph_index + 1 + 1) * DataSize::kUSHORT;
}

/******************************************************************************
 * IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator class
 ******************************************************************************/
IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator::BitmapGlyphInfoIterator(
    IndexSubTableFormat3::Builder* container)
    : RefIterator<BitmapGlyphInfo, IndexSubTableFormat3::Builder,
                  IndexSubTable::Builder>(container) {
  glyph_id_ = container->first_glyph_index();
}

bool IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator::HasNext() {
  if (glyph_id_ <= container()->last_glyph_index()) {
    return true;
  }
  return false;
}

CALLER_ATTACH BitmapGlyphInfo*
IndexSubTableFormat3::Builder::BitmapGlyphInfoIterator::Next() {
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
