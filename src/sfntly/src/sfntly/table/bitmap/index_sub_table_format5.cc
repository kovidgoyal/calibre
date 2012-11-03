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

#include "sfntly/table/bitmap/index_sub_table_format5.h"

#include <algorithm>

#include "sfntly/table/bitmap/eblc_table.h"

namespace sfntly {
/******************************************************************************
 * IndexSubTableFormat5 class
 ******************************************************************************/
IndexSubTableFormat5::~IndexSubTableFormat5() {
}

int32_t IndexSubTableFormat5::NumGlyphs() {
  return NumGlyphs(data_, 0);
}

int32_t IndexSubTableFormat5::GlyphStartOffset(int32_t glyph_id) {
  int32_t check = CheckGlyphRange(glyph_id);
  if (check == -1) {
    return -1;
  }
  int32_t loca = ReadFontData()->SearchUShort(
      EblcTable::Offset::kIndexSubTable5_glyphArray,
      DataSize::kUSHORT,
      NumGlyphs(),
      glyph_id);
  if (loca == -1) {
    return loca;
  }
  return loca * ImageSize();
}

int32_t IndexSubTableFormat5::GlyphLength(int32_t glyph_id) {
  int32_t check = CheckGlyphRange(glyph_id);
  if (check == -1) {
    return 0;
  }
  return image_size_;
}

int32_t IndexSubTableFormat5::ImageSize() {
  return data_->ReadULongAsInt(EblcTable::Offset::kIndexSubTable5_imageSize);
}

CALLER_ATTACH BigGlyphMetrics* IndexSubTableFormat5::BigMetrics() {
  ReadableFontDataPtr data;
  data.Attach(down_cast<ReadableFontData*>(data_->Slice(
      EblcTable::Offset::kIndexSubTable5_bigGlyphMetrics,
      BigGlyphMetrics::Offset::kMetricsLength)));
  BigGlyphMetricsPtr output = new BigGlyphMetrics(data);
  return output.Detach();
}

IndexSubTableFormat5::IndexSubTableFormat5(ReadableFontData* data,
                                           int32_t first_glyph_index,
                                           int32_t last_glyph_index)
    : IndexSubTable(data, first_glyph_index, last_glyph_index) {
  image_size_ = data_->ReadULongAsInt(
      EblcTable::Offset::kIndexSubTable5_imageSize);
}

// static
int32_t IndexSubTableFormat5::NumGlyphs(ReadableFontData* data,
                                        int32_t table_offset) {
  int32_t num_glyphs = data->ReadULongAsInt(table_offset +
      EblcTable::Offset::kIndexSubTable5_numGlyphs);
  return num_glyphs;
}

/******************************************************************************
 * IndexSubTableFormat5::Builder class
 ******************************************************************************/
IndexSubTableFormat5::Builder::~Builder() {
}

int32_t IndexSubTableFormat5::Builder::NumGlyphs() {
  return GetGlyphArray()->size();
}

int32_t IndexSubTableFormat5::Builder::GlyphLength(int32_t glyph_id) {
  UNREFERENCED_PARAMETER(glyph_id);
  return ImageSize();
}

int32_t IndexSubTableFormat5::Builder::GlyphStartOffset(int32_t glyph_id) {
  int32_t check = CheckGlyphRange(glyph_id);
  if (check == -1) {
    return -1;
  }
  IntegerList* glyph_array = GetGlyphArray();
  IntegerList::iterator it = std::find(glyph_array->begin(),
                                       glyph_array->end(),
                                       glyph_id);
  if (it == glyph_array->end()) {
    return -1;
  }
  return (it - glyph_array->begin()) * ImageSize();
}

CALLER_ATTACH IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator*
    IndexSubTableFormat5::Builder::GetIterator() {
  Ptr<IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator> it =
      new IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator(this);
  return it.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat5::Builder*
IndexSubTableFormat5::Builder::CreateBuilder() {
  IndexSubTableFormat5BuilderPtr output = new IndexSubTableFormat5::Builder();
  return output.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat5::Builder*
IndexSubTableFormat5::Builder::CreateBuilder(ReadableFontData* data,
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
  IndexSubTableFormat5BuilderPtr output =
      new IndexSubTableFormat5::Builder(new_data,
                                        first_glyph_index,
                                        last_glyph_index);
  return output.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat5::Builder*
IndexSubTableFormat5::Builder::CreateBuilder(WritableFontData* data,
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
  IndexSubTableFormat5BuilderPtr output =
      new IndexSubTableFormat5::Builder(new_data,
                                        first_glyph_index,
                                        last_glyph_index);
  return output.Detach();
}

CALLER_ATTACH FontDataTable* IndexSubTableFormat5::Builder::SubBuildTable(
    ReadableFontData* data) {
  IndexSubTableFormat5Ptr output = new IndexSubTableFormat5(
      data, first_glyph_index(), last_glyph_index());
  return output.Detach();
}

void IndexSubTableFormat5::Builder::SubDataSet() {
  Revert();
}

int32_t IndexSubTableFormat5::Builder::SubDataSizeToSerialize() {
  if (glyph_array_.empty()) {
    return InternalReadData()->Length();
  }
  return EblcTable::Offset::kIndexSubTable5_builderDataSize +
         glyph_array_.size() * DataSize::kUSHORT;
}

bool IndexSubTableFormat5::Builder::SubReadyToSerialize() {
  if (!glyph_array_.empty()) {
    return true;
  }
  return false;
}

int32_t IndexSubTableFormat5::Builder::SubSerialize(
    WritableFontData* new_data) {
  int32_t size = SerializeIndexSubHeader(new_data);
  if (!model_changed()) {
    ReadableFontDataPtr source;
    WritableFontDataPtr target;
    source.Attach(down_cast<ReadableFontData*>(InternalReadData()->Slice(
        EblcTable::Offset::kIndexSubTable5_imageSize)));
    target.Attach(down_cast<WritableFontData*>(new_data->Slice(
        EblcTable::Offset::kIndexSubTable5_imageSize)));
    size += source->CopyTo(target);
  } else {
    size += new_data->WriteULong(EblcTable::Offset::kIndexSubTable5_imageSize,
                                 ImageSize());
    WritableFontDataPtr slice;
    slice.Attach(down_cast<WritableFontData*>(new_data->Slice(size)));
    size += BigMetrics()->SubSerialize(slice);
    size += new_data->WriteULong(size, glyph_array_.size());
    for (IntegerList::iterator b = glyph_array_.begin(), e = glyph_array_.end();
                               b != e; b++) {
      size += new_data->WriteUShort(size, *b);
    }
  }
  return size;
}

int32_t IndexSubTableFormat5::Builder::ImageSize() {
  return InternalReadData()->ReadULongAsInt(
      EblcTable::Offset::kIndexSubTable5_imageSize);
}

void IndexSubTableFormat5::Builder::SetImageSize(int32_t image_size) {
  InternalWriteData()->WriteULong(
      EblcTable::Offset::kIndexSubTable5_imageSize, image_size);
}

BigGlyphMetrics::Builder* IndexSubTableFormat5::Builder::BigMetrics() {
  if (metrics_ == NULL) {
    WritableFontDataPtr data;
    data.Attach(down_cast<WritableFontData*>(InternalWriteData()->Slice(
        EblcTable::Offset::kIndexSubTable5_bigGlyphMetrics,
        BigGlyphMetrics::Offset::kMetricsLength)));
    metrics_ = new BigGlyphMetrics::Builder(data);
    set_model_changed();
  }
  return metrics_;
}

IntegerList* IndexSubTableFormat5::Builder::GlyphArray() {
  return GetGlyphArray();
}

void IndexSubTableFormat5::Builder::SetGlyphArray(const IntegerList& v) {
  glyph_array_.clear();
  glyph_array_ = v;
  set_model_changed();
}

void IndexSubTableFormat5::Builder::Revert() {
  glyph_array_.clear();
  IndexSubTable::Builder::Revert();
}

IndexSubTableFormat5::Builder::Builder()
    : IndexSubTable::Builder(EblcTable::Offset::kIndexSubTable5_builderDataSize,
                             IndexSubTable::Format::FORMAT_5) {
}

IndexSubTableFormat5::Builder::Builder(WritableFontData* data,
                                       int32_t first_glyph_index,
                                       int32_t last_glyph_index)
    : IndexSubTable::Builder(data, first_glyph_index, last_glyph_index) {
}

IndexSubTableFormat5::Builder::Builder(ReadableFontData* data,
                                       int32_t first_glyph_index,
                                       int32_t last_glyph_index)
    : IndexSubTable::Builder(data, first_glyph_index, last_glyph_index) {
}

IntegerList* IndexSubTableFormat5::Builder::GetGlyphArray() {
  if (glyph_array_.empty()) {
    Initialize(InternalReadData());
    set_model_changed();
  }
  return &glyph_array_;
}

void IndexSubTableFormat5::Builder::Initialize(ReadableFontData* data) {
  glyph_array_.clear();
  if (data) {
    int32_t num_glyphs = IndexSubTableFormat5::NumGlyphs(data, 0);
    for (int32_t i = 0; i < num_glyphs; ++i) {
      glyph_array_.push_back(data->ReadUShort(
          EblcTable::Offset::kIndexSubTable5_glyphArray +
          i * DataSize::kUSHORT));
    }
  }
}

// static
int32_t IndexSubTableFormat5::Builder::DataLength(
    ReadableFontData* data,
    int32_t index_sub_table_offset,
    int32_t first_glyph_index,
    int32_t last_glyph_index) {
  int32_t num_glyphs = IndexSubTableFormat5::NumGlyphs(data,
                                                       index_sub_table_offset);
  UNREFERENCED_PARAMETER(first_glyph_index);
  UNREFERENCED_PARAMETER(last_glyph_index);
  return EblcTable::Offset::kIndexSubTable5_glyphArray +
         num_glyphs * DataSize::kUSHORT;
}

/******************************************************************************
 * IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator class
 ******************************************************************************/
IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator::BitmapGlyphInfoIterator(
    IndexSubTableFormat5::Builder* container)
    : RefIterator<BitmapGlyphInfo, IndexSubTableFormat5::Builder,
                  IndexSubTable::Builder>(container),
      offset_index_(0) {
}

bool IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator::HasNext() {
  if (offset_index_ < (int32_t)(container()->GetGlyphArray()->size())) {
    return true;
  }
  return false;
}

CALLER_ATTACH BitmapGlyphInfo*
IndexSubTableFormat5::Builder::BitmapGlyphInfoIterator::Next() {
  BitmapGlyphInfoPtr output;
  if (!HasNext()) {
    // Note: In C++, we do not throw exception when there's no element.
    return NULL;
  }
  output = new BitmapGlyphInfo(container()->GetGlyphArray()->at(offset_index_),
                               container()->image_data_offset(),
                               offset_index_ * container()->ImageSize(),
                               container()->ImageSize(),
                               container()->image_format());
  offset_index_++;
  return output.Detach();
}

}  // namespace sfntly
