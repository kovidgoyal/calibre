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

#include "sfntly/table/bitmap/index_sub_table_format4.h"

#include "sfntly/table/bitmap/eblc_table.h"

namespace sfntly {
/******************************************************************************
 * IndexSubTableFormat4 class
 ******************************************************************************/
IndexSubTableFormat4::~IndexSubTableFormat4() {
}

int32_t IndexSubTableFormat4::NumGlyphs() {
  return IndexSubTableFormat4::NumGlyphs(data_, 0);
}

int32_t IndexSubTableFormat4::GlyphStartOffset(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return -1;
  }
  int32_t pair_index = FindCodeOffsetPair(glyph_id);
  if (pair_index < 0) {
    return -1;
  }
  return data_->ReadUShort(EblcTable::Offset::kIndexSubTable4_glyphArray +
                           pair_index *
                           EblcTable::Offset::kCodeOffsetPairLength +
                           EblcTable::Offset::kCodeOffsetPair_offset);
}

int32_t IndexSubTableFormat4::GlyphLength(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return -1;
  }

  int32_t pair_index = FindCodeOffsetPair(glyph_id);
  if (pair_index < 0) {
    return -1;
  }
  return data_->ReadUShort(
             EblcTable::Offset::kIndexSubTable4_glyphArray +
             (pair_index + 1) * EblcTable::Offset::kCodeOffsetPairLength +
             EblcTable::Offset::kCodeOffsetPair_offset) -
         data_->ReadUShort(
             EblcTable::Offset::kIndexSubTable4_glyphArray +
             (pair_index) * EblcTable::Offset::kCodeOffsetPairLength +
             EblcTable::Offset::kCodeOffsetPair_offset);
}

IndexSubTableFormat4::IndexSubTableFormat4(ReadableFontData* data,
                                           int32_t first,
                                           int32_t last)
    : IndexSubTable(data, first, last) {
}

int32_t IndexSubTableFormat4::FindCodeOffsetPair(int32_t glyph_id) {
  return data_->SearchUShort(EblcTable::Offset::kIndexSubTable4_glyphArray,
                             EblcTable::Offset::kCodeOffsetPairLength,
                             NumGlyphs(),
                             glyph_id);
}

int32_t IndexSubTableFormat4::NumGlyphs(ReadableFontData* data,
                                        int32_t table_offset) {
  int32_t num_glyphs = data->ReadULongAsInt(table_offset +
      EblcTable::Offset::kIndexSubTable4_numGlyphs);
  return num_glyphs;
}

/******************************************************************************
 * IndexSubTableFormat4::CodeOffsetPair related class
 ******************************************************************************/
IndexSubTableFormat4::CodeOffsetPair::CodeOffsetPair(int32_t glyph_code,
                                                     int32_t offset)
    : glyph_code_(glyph_code), offset_(offset) {
}

IndexSubTableFormat4::CodeOffsetPairBuilder::CodeOffsetPairBuilder()
    : CodeOffsetPair(0, 0) {
}

IndexSubTableFormat4::CodeOffsetPairBuilder::CodeOffsetPairBuilder(
    int32_t glyph_code, int32_t offset)
    : CodeOffsetPair(glyph_code, offset) {
}

bool IndexSubTableFormat4::CodeOffsetPairGlyphCodeComparator::operator()(
    const CodeOffsetPair& lhs, const CodeOffsetPair& rhs) {
  return lhs.glyph_code() < rhs.glyph_code();
}

/******************************************************************************
 * IndexSubTableFormat4::Builder class
 ******************************************************************************/
IndexSubTableFormat4::Builder::~Builder() {
}

int32_t IndexSubTableFormat4::Builder::NumGlyphs() {
  return GetOffsetArray()->size() - 1;
}

int32_t IndexSubTableFormat4::Builder::GlyphLength(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return 0;
  }
  int32_t pair_index = FindCodeOffsetPair(glyph_id);
  if (pair_index == -1) {
    return 0;
  }
  return GetOffsetArray()->at(pair_index + 1).offset() -
         GetOffsetArray()->at(pair_index).offset();
}

int32_t IndexSubTableFormat4::Builder::GlyphStartOffset(int32_t glyph_id) {
  int32_t loca = CheckGlyphRange(glyph_id);
  if (loca == -1) {
    return -1;
  }
  int32_t pair_index = FindCodeOffsetPair(glyph_id);
  if (pair_index == -1) {
    return -1;
  }
  return GetOffsetArray()->at(pair_index).offset();
}

CALLER_ATTACH IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator*
    IndexSubTableFormat4::Builder::GetIterator() {
  Ptr<IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator> it =
      new IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator(this);
  return it.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat4::Builder*
IndexSubTableFormat4::Builder::CreateBuilder() {
  IndexSubTableFormat4BuilderPtr output = new IndexSubTableFormat4::Builder();
  return output.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat4::Builder*
IndexSubTableFormat4::Builder::CreateBuilder(ReadableFontData* data,
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
  IndexSubTableFormat4BuilderPtr output =
      new IndexSubTableFormat4::Builder(new_data,
                                        first_glyph_index,
                                        last_glyph_index);
  return output.Detach();
}

// static
CALLER_ATTACH IndexSubTableFormat4::Builder*
IndexSubTableFormat4::Builder::CreateBuilder(WritableFontData* data,
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
  IndexSubTableFormat4BuilderPtr output =
      new IndexSubTableFormat4::Builder(new_data,
                                        first_glyph_index,
                                        last_glyph_index);
  return output.Detach();
}

CALLER_ATTACH FontDataTable* IndexSubTableFormat4::Builder::SubBuildTable(
    ReadableFontData* data) {
  IndexSubTableFormat4Ptr output = new IndexSubTableFormat4(
      data, first_glyph_index(), last_glyph_index());
  return output.Detach();
}

void IndexSubTableFormat4::Builder::SubDataSet() {
  Revert();
}

int32_t IndexSubTableFormat4::Builder::SubDataSizeToSerialize() {
  if (offset_pair_array_.empty()) {
    return InternalReadData()->Length();
  }
  return EblcTable::Offset::kIndexSubHeaderLength + DataSize::kULONG +
         GetOffsetArray()->size() *
         EblcTable::Offset::kIndexSubTable4_codeOffsetPairLength;
}

bool IndexSubTableFormat4::Builder::SubReadyToSerialize() {
  if (!offset_pair_array_.empty()) {
    return true;
  }
  return false;
}

int32_t IndexSubTableFormat4::Builder::SubSerialize(
    WritableFontData* new_data) {
  int32_t size = SerializeIndexSubHeader(new_data);
  if (!model_changed()) {
    if (InternalReadData() == NULL) {
      return size;
    }
    ReadableFontDataPtr source;
    WritableFontDataPtr target;
    source.Attach(down_cast<ReadableFontData*>(InternalReadData()->Slice(
        EblcTable::Offset::kIndexSubTable4_glyphArray)));
    target.Attach(down_cast<WritableFontData*>(new_data->Slice(
        EblcTable::Offset::kIndexSubTable4_glyphArray)));
    size += source->CopyTo(target);
  } else {
    size += new_data->WriteLong(size, offset_pair_array_.size() - 1);
    for (std::vector<CodeOffsetPairBuilder>::iterator
             b = GetOffsetArray()->begin(), e = GetOffsetArray()->end();
             b != e; b++) {
      size += new_data->WriteUShort(size, b->glyph_code());
      size += new_data->WriteUShort(size, b->offset());
    }
  }
  return size;
}

void IndexSubTableFormat4::Builder::Revert() {
  offset_pair_array_.clear();
  IndexSubTable::Builder::Revert();
}

void IndexSubTableFormat4::Builder::SetOffsetArray(
    const std::vector<CodeOffsetPairBuilder>& pair_array) {
  offset_pair_array_.clear();
  offset_pair_array_ = pair_array;
  set_model_changed();
}

IndexSubTableFormat4::Builder::Builder()
  : IndexSubTable::Builder(EblcTable::Offset::kIndexSubTable4_builderDataSize,
                           Format::FORMAT_4) {
}

IndexSubTableFormat4::Builder::Builder(WritableFontData* data,
                                       int32_t first_glyph_index,
                                       int32_t last_glyph_index)
    : IndexSubTable::Builder(data, first_glyph_index, last_glyph_index) {
}

IndexSubTableFormat4::Builder::Builder(ReadableFontData* data,
                                       int32_t first_glyph_index,
                                       int32_t last_glyph_index)
    : IndexSubTable::Builder(data, first_glyph_index, last_glyph_index) {
}

std::vector<IndexSubTableFormat4::CodeOffsetPairBuilder>*
IndexSubTableFormat4::Builder::GetOffsetArray() {
  if (offset_pair_array_.empty()) {
    Initialize(InternalReadData());
    set_model_changed();
  }
  return &offset_pair_array_;
}

void IndexSubTableFormat4::Builder::Initialize(ReadableFontData* data) {
  offset_pair_array_.clear();
  if (data) {
    int32_t num_pairs = IndexSubTableFormat4::NumGlyphs(data, 0) + 1;
    int32_t offset = EblcTable::Offset::kIndexSubTable4_glyphArray;
    for (int32_t i = 0; i < num_pairs; ++i) {
      int32_t glyph_code = data->ReadUShort(offset +
          EblcTable::Offset::kIndexSubTable4_codeOffsetPair_glyphCode);
      int32_t glyph_offset = data->ReadUShort(offset +
          EblcTable::Offset::kIndexSubTable4_codeOffsetPair_offset);
      offset += EblcTable::Offset::kIndexSubTable4_codeOffsetPairLength;
      CodeOffsetPairBuilder pair_builder(glyph_code, glyph_offset);
      offset_pair_array_.push_back(pair_builder);
    }
  }
}

int32_t IndexSubTableFormat4::Builder::FindCodeOffsetPair(int32_t glyph_id) {
  std::vector<CodeOffsetPairBuilder>* pair_list = GetOffsetArray();
  int32_t location = 0;
  int32_t bottom = 0;
  int32_t top = pair_list->size();
  while (top != bottom) {
    location = (top + bottom) / 2;
    CodeOffsetPairBuilder* pair = &(pair_list->at(location));
    if (glyph_id < pair->glyph_code()) {
      // location is below current location
      top = location;
    } else if (glyph_id > pair->glyph_code()) {
      // location is above current location
      bottom = location + 1;
    } else {
      return location;
    }
  }
  return -1;
}

// static
int32_t IndexSubTableFormat4::Builder::DataLength(
    ReadableFontData* data,
    int32_t index_sub_table_offset,
    int32_t first_glyph_index,
    int32_t last_glyph_index) {
  int32_t num_glyphs = IndexSubTableFormat4::NumGlyphs(data,
                                                       index_sub_table_offset);
  UNREFERENCED_PARAMETER(first_glyph_index);
  UNREFERENCED_PARAMETER(last_glyph_index);
  return EblcTable::Offset::kIndexSubTable4_glyphArray +
         num_glyphs * EblcTable::Offset::kIndexSubTable4_codeOffsetPair_offset;
}


/******************************************************************************
 * IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator class
 ******************************************************************************/
IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator::BitmapGlyphInfoIterator(
    IndexSubTableFormat4::Builder* container)
    : RefIterator<BitmapGlyphInfo, IndexSubTableFormat4::Builder,
                  IndexSubTable::Builder>(container),
      code_offset_pair_index_(0) {
}

bool IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator::HasNext() {
  if (code_offset_pair_index_ <
      (int32_t)(container()->GetOffsetArray()->size() - 1)) {
    return true;
  }
  return false;
}

CALLER_ATTACH BitmapGlyphInfo*
IndexSubTableFormat4::Builder::BitmapGlyphInfoIterator::Next() {
  BitmapGlyphInfoPtr output;
  if (!HasNext()) {
    // Note: In C++, we do not throw exception when there's no element.
    return NULL;
  }
  std::vector<CodeOffsetPairBuilder>* offset_array =
      container()->GetOffsetArray();
  int32_t offset = offset_array->at(code_offset_pair_index_).offset();
  int32_t next_offset = offset_array->at(code_offset_pair_index_ + 1).offset();
  int32_t glyph_code = offset_array->at(code_offset_pair_index_).glyph_code();
  output = new BitmapGlyphInfo(glyph_code,
                               container()->image_data_offset(),
                               offset,
                               next_offset - offset,
                               container()->image_format());
  code_offset_pair_index_++;
  return output.Detach();
}

}  // namespace sfntly
