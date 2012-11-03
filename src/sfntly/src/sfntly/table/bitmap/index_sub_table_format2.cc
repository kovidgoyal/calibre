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

#include "sfntly/table/bitmap/index_sub_table_format2.h"

#include "sfntly/table/bitmap/eblc_table.h"

namespace sfntly {
/******************************************************************************
 * IndexSubTableFormat2 class
 ******************************************************************************/
IndexSubTableFormat2::~IndexSubTableFormat2() {
}

int32_t IndexSubTableFormat2::ImageSize() {
  return data_->ReadULongAsInt(EblcTable::Offset::kIndexSubTable2_imageSize);
}

CALLER_ATTACH BigGlyphMetrics* IndexSubTableFormat2::BigMetrics() {
  ReadableFontDataPtr slice;
  slice.Attach(down_cast<ReadableFontData*>(
      data_->Slice(EblcTable::Offset::kIndexSubTable2_bigGlyphMetrics,
                   BigGlyphMetrics::Offset::kMetricsLength)));
  BigGlyphMetricsPtr output = new BigGlyphMetrics(slice);
  return output.Detach();
}

int32_t IndexSubTableFormat2::NumGlyphs() {
  return last_glyph_index() - first_glyph_index() + 1;
}

int32_t IndexSubTableFormat2::GlyphStartOffset(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return -1;
  }
  return loca * image_size_;
}

int32_t IndexSubTableFormat2::GlyphLength(int32_t glyph_id) {
  if (CheckGlyphRange(glyph_id) == -1) {
    return 0;
  }
  return image_size_;
}

IndexSubTableFormat2::IndexSubTableFormat2(ReadableFontData* data,
                                           int32_t first,
                                           int32_t last)
    : IndexSubTable(data, first, last) {
  image_size_ =
      data_->ReadULongAsInt(EblcTable::Offset::kIndexSubTable2_imageSize);
}

/******************************************************************************
 * IndexSubTableFormat2::Builder class
 ******************************************************************************/
IndexSubTableFormat2::Builder::~Builder() {
}

int32_t IndexSubTableFormat2::Builder::NumGlyphs() {
  return last_glyph_index() - first_glyph_index() + 1;
}

int32_t IndexSubTableFormat2::Builder::GlyphStartOffset(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return -1;
  }
  return loca * ImageSize();
}

int32_t IndexSubTableFormat2::Builder::GlyphLength(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return 0;
  }
  return ImageSize();
}

CALLER_ATTACH IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator*
    IndexSubTableFormat2::Builder::GetIterator() {
  Ptr<IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator> it =
      new IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator(this);
  return it.Detach();
}

int32_t IndexSubTableFormat2::Builder::ImageSize() {
  return InternalReadData()->ReadULongAsInt(
      EblcTable::Offset::kIndexSubTable2_imageSize);
}

void IndexSubTableFormat2::Builder::SetImageSize(int32_t image_size) {
  InternalWriteData()->WriteULong(EblcTable::Offset::kIndexSubTable2_imageSize,
                                  image_size);
}

BigGlyphMetrics::Builder* IndexSubTableFormat2::Builder::BigMetrics() {
  if (metrics_ == NULL) {
    WritableFontDataPtr data;
    data.Attach(down_cast<WritableFontData*>(InternalWriteData()->Slice(
        EblcTable::Offset::kIndexSubTable2_bigGlyphMetrics,
        BigGlyphMetrics::Offset::kMetricsLength)));
    metrics_ = new BigGlyphMetrics::Builder(data);
  }
  return metrics_;
}

// static
CALLER_ATTACH IndexSubTableFormat2::Builder*
IndexSubTableFormat2::Builder::CreateBuilder() {
  IndexSubTableFormat2BuilderPtr output = new IndexSubTableFormat2::Builder();
  return output.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat2::Builder*
IndexSubTableFormat2::Builder::CreateBuilder(ReadableFontData* data,
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
  IndexSubTableFormat2BuilderPtr output =
      new IndexSubTableFormat2::Builder(new_data,
                                        first_glyph_index,
                                        last_glyph_index);
  return output.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat2::Builder*
IndexSubTableFormat2::Builder::CreateBuilder(WritableFontData* data,
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
  IndexSubTableFormat2BuilderPtr output =
      new IndexSubTableFormat2::Builder(new_data,
                                        first_glyph_index,
                                        last_glyph_index);
  return output.Detach();
}

CALLER_ATTACH FontDataTable* IndexSubTableFormat2::Builder::SubBuildTable(
    ReadableFontData* data) {
  IndexSubTableFormat2Ptr output = new IndexSubTableFormat2(
      data, first_glyph_index(), last_glyph_index());
  return output.Detach();
}

void IndexSubTableFormat2::Builder::SubDataSet() {
  Revert();
}

int32_t IndexSubTableFormat2::Builder::SubDataSizeToSerialize() {
  return EblcTable::Offset::kIndexSubTable2Length;
}

bool IndexSubTableFormat2::Builder::SubReadyToSerialize() {
  return true;
}

int32_t IndexSubTableFormat2::Builder::SubSerialize(
    WritableFontData* new_data) {
  int32_t size = SerializeIndexSubHeader(new_data);
  if (metrics_ == NULL) {
    ReadableFontDataPtr source;
    WritableFontDataPtr target;
    source.Attach(down_cast<ReadableFontData*>(
        InternalReadData()->Slice(size)));
    target.Attach(down_cast<WritableFontData*>(new_data->Slice(size)));
    size += source->CopyTo(target);
  } else {
    WritableFontDataPtr slice;
    size += new_data->WriteLong(EblcTable::Offset::kIndexSubTable2_imageSize,
                                ImageSize());
    slice.Attach(down_cast<WritableFontData*>(new_data->Slice(size)));
    size += metrics_->SubSerialize(slice);
  }
  return size;
}

IndexSubTableFormat2::Builder::Builder()
    : IndexSubTable::Builder(EblcTable::Offset::kIndexSubTable3_builderDataSize,
                             IndexSubTable::Format::FORMAT_2) {
  metrics_.Attach(BigGlyphMetrics::Builder::CreateBuilder());
}

IndexSubTableFormat2::Builder::Builder(WritableFontData* data,
                                       int32_t first_glyph_index,
                                       int32_t last_glyph_index)
    : IndexSubTable::Builder(data, first_glyph_index, last_glyph_index) {
}

IndexSubTableFormat2::Builder::Builder(ReadableFontData* data,
                                       int32_t first_glyph_index,
                                       int32_t last_glyph_index)
    : IndexSubTable::Builder(data, first_glyph_index, last_glyph_index) {
}

// static
int32_t IndexSubTableFormat2::Builder::DataLength(
    ReadableFontData* data,
    int32_t index_sub_table_offset,
    int32_t first_glyph_index,
    int32_t last_glyph_index) {
  UNREFERENCED_PARAMETER(data);
  UNREFERENCED_PARAMETER(index_sub_table_offset);
  UNREFERENCED_PARAMETER(first_glyph_index);
  UNREFERENCED_PARAMETER(last_glyph_index);
  return EblcTable::Offset::kIndexSubTable2Length;
}

/******************************************************************************
 * IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator class
 ******************************************************************************/
IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator::BitmapGlyphInfoIterator(
    IndexSubTableFormat2::Builder* container)
    : RefIterator<BitmapGlyphInfo, IndexSubTableFormat2::Builder,
                  IndexSubTable::Builder>(container) {
  glyph_id_ = container->first_glyph_index();
}

bool IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator::HasNext() {
  if (glyph_id_ <= container()->last_glyph_index()) {
    return true;
  }
  return false;
}

CALLER_ATTACH BitmapGlyphInfo*
IndexSubTableFormat2::Builder::BitmapGlyphInfoIterator::Next() {
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
