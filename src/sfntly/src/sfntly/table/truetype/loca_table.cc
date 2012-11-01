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

#include "sfntly/table/truetype/loca_table.h"
#include "sfntly/port/exception_type.h"

namespace sfntly {
/******************************************************************************
 * LocaTable class
 ******************************************************************************/
LocaTable::~LocaTable() {}

int32_t LocaTable::GlyphOffset(int32_t glyph_id) {
  if (glyph_id < 0 || glyph_id >= num_glyphs_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException("Glyph ID is out of bounds.");
#endif
    return 0;
  }
  return Loca(glyph_id);
}

int32_t LocaTable::GlyphLength(int32_t glyph_id) {
  if (glyph_id < 0 || glyph_id >= num_glyphs_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException("Glyph ID is out of bounds.");
#endif
    return 0;
  }
  return Loca(glyph_id + 1) - Loca(glyph_id);
}

int32_t LocaTable::NumLocas() {
  return num_glyphs_ + 1;
}

// Changed by Kovid: The following two methods must not have inline
// definitions, otherwise they give incorrect results when compiled with gcc
// and -fPIC, leading to corrupted font generation.
int32_t LocaTable::num_glyphs() {
    return num_glyphs_;
}

int32_t LocaTable::format_version() {
    return format_version_;
}

int32_t LocaTable::Loca(int32_t index) {
  if (index > num_glyphs_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException();
#endif
    return 0;
  }
  if (format_version_ == IndexToLocFormat::kShortOffset) {
    return 2 * data_->ReadUShort(index * DataSize::kUSHORT);
  }
  return data_->ReadULongAsInt(index * DataSize::kULONG);
}

LocaTable::LocaTable(Header* header,
                     ReadableFontData* data,
                     int32_t format_version,
                     int32_t num_glyphs)
    : Table(header, data),
      format_version_(format_version),
      num_glyphs_(num_glyphs) {
}

/******************************************************************************
 * LocaTable::Iterator class
 ******************************************************************************/
LocaTable::LocaIterator::LocaIterator(LocaTable* table)
    : PODIterator<int32_t, LocaTable>(table), index_(-1) {
}

bool LocaTable::LocaIterator::HasNext() {
  return index_ <= container()->num_glyphs_;
}

int32_t LocaTable::LocaIterator::Next() {
  return container()->Loca(index_++);
}

/******************************************************************************
 * LocaTable::Builder class
 ******************************************************************************/
LocaTable::Builder::Builder(Header* header, WritableFontData* data)
    : Table::Builder(header, data),
      format_version_(IndexToLocFormat::kLongOffset),
      num_glyphs_(-1) {
}

LocaTable::Builder::Builder(Header* header, ReadableFontData* data)
    : Table::Builder(header, data),
      format_version_(IndexToLocFormat::kLongOffset),
      num_glyphs_(-1) {
}

LocaTable::Builder::~Builder() {}

// Changed by Kovid: The following two methods must not have inline
// definitions, otherwise they give incorrect results when compiled with gcc
// and -fPIC, leading to corrupted font generation.
int32_t LocaTable::Builder::format_version() { return format_version_; }

void LocaTable::Builder::set_format_version(int32_t value) { format_version_ = value; }

CALLER_ATTACH
LocaTable::Builder* LocaTable::Builder::CreateBuilder(Header* header,
                                                      WritableFontData* data) {
  Ptr<LocaTable::Builder> builder;
  builder = new LocaTable::Builder(header, data);
  return builder.Detach();
}

IntegerList* LocaTable::Builder::LocaList() {
  return GetLocaList();
}

void LocaTable::Builder::SetLocaList(IntegerList* list) {
  loca_.clear();
  if (list) {
    loca_ = *list;
    set_model_changed();
  }
}

int32_t LocaTable::Builder::GlyphOffset(int32_t glyph_id) {
  if (CheckGlyphRange(glyph_id) == -1) {
    return 0;
  }
  return GetLocaList()->at(glyph_id);
}

int32_t LocaTable::Builder::GlyphLength(int32_t glyph_id) {
  if (CheckGlyphRange(glyph_id) == -1) {
    return 0;
  }
  return GetLocaList()->at(glyph_id + 1) - GetLocaList()->at(glyph_id);
}

void LocaTable::Builder::SetNumGlyphs(int32_t num_glyphs) {
  num_glyphs_ = num_glyphs;
}

int32_t LocaTable::Builder::NumGlyphs() {
  return LastGlyphIndex() - 1;
}

void LocaTable::Builder::Revert() {
  loca_.clear();
  set_model_changed(false);
}

int32_t LocaTable::Builder::NumLocas() {
  return GetLocaList()->size();
}

int32_t LocaTable::Builder::Loca(int32_t index) {
  return GetLocaList()->at(index);
}

CALLER_ATTACH
FontDataTable* LocaTable::Builder::SubBuildTable(ReadableFontData* data) {
  FontDataTablePtr table =
      new LocaTable(header(), data, format_version_, num_glyphs_);
  return table.Detach();
}

void LocaTable::Builder::SubDataSet() {
  Initialize(InternalReadData());
}

int32_t LocaTable::Builder::SubDataSizeToSerialize() {
  if (loca_.empty()) {
    return 0;
  }
  if (format_version_ == IndexToLocFormat::kLongOffset) {
    return loca_.size() * DataSize::kULONG;
  }
  return loca_.size() * DataSize::kUSHORT;
}

bool LocaTable::Builder::SubReadyToSerialize() {
  return !loca_.empty();
}

int32_t LocaTable::Builder::SubSerialize(WritableFontData* new_data) {
  int32_t size = 0;
  for (IntegerList::iterator l = loca_.begin(), end = loca_.end();
                             l != end; ++l) {
    if (format_version_ == IndexToLocFormat::kLongOffset) {
      size += new_data->WriteULong(size, *l);
    } else {
      size += new_data->WriteUShort(size, *l / 2);
    }
  }
  num_glyphs_ = loca_.size() - 1;
  return size;
}

void LocaTable::Builder::Initialize(ReadableFontData* data) {
  ClearLoca(false);
  if (data) {
    if (NumGlyphs() < 0) {
#if !defined (SFNTLY_NO_EXCEPTION)
      throw IllegalStateException("numglyphs not set on LocaTable Builder.");
#endif
      return;
    }
    LocaTablePtr table =
        new LocaTable(header(), data, format_version_, num_glyphs_);
    Ptr<LocaTable::LocaIterator> loca_iter =
        new LocaTable::LocaIterator(table);
    while (loca_iter->HasNext()) {
      loca_.push_back(loca_iter->Next());
    }
  }
}

int32_t LocaTable::Builder::CheckGlyphRange(int32_t glyph_id) {
  if (glyph_id < 0 || glyph_id > LastGlyphIndex()) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundsException("Glyph ID is outside of the allowed range");
#endif
    return -1;
  }
  return glyph_id;
}

int32_t LocaTable::Builder::LastGlyphIndex() {
  return !loca_.empty() ? loca_.size() - 2 : num_glyphs_ - 1;
}

IntegerList* LocaTable::Builder::GetLocaList() {
  if (loca_.empty()) {
    Initialize(InternalReadData());
    set_model_changed();
  }
  return &loca_;
}

void LocaTable::Builder::ClearLoca(bool nullify) {
  // Note: in C++ port, nullify is not used at all.
  UNREFERENCED_PARAMETER(nullify);
  loca_.clear();
  set_model_changed(false);
}

}  // namespace sfntly
