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

// type.h needs to be included first because of building issues on Windows
// Type aliases we delcare are defined in other headers and make the build
// fail otherwise.
#include "sfntly/port/type.h"
#include "sfntly/table/core/cmap_table.h"

#include <stdio.h>
#include <stdlib.h>

#include <utility>

#include "sfntly/font.h"
#include "sfntly/math/font_math.h"
#include "sfntly/port/endian.h"
#include "sfntly/port/exception_type.h"
#include "sfntly/table/core/name_table.h"

namespace sfntly {

const int32_t CMapTable::NOTDEF = 0;

CMapTable::CMapId CMapTable::WINDOWS_BMP = {
  PlatformId::kWindows,
  WindowsEncodingId::kUnicodeUCS2
};
CMapTable::CMapId CMapTable::WINDOWS_UCS4 = {
  PlatformId::kWindows,
  WindowsEncodingId::kUnicodeUCS4
};
CMapTable::CMapId CMapTable::MAC_ROMAN = {
  PlatformId::kWindows,
  MacintoshEncodingId::kRoman
};

/******************************************************************************
 * CMapTable class
 ******************************************************************************/
CMapTable::CMapTable(Header* header, ReadableFontData* data)
  : SubTableContainerTable(header, data) {
}

CMapTable::~CMapTable() {}

CALLER_ATTACH CMapTable::CMap* CMapTable::GetCMap(const int32_t index) {
  if (index < 0 || index > NumCMaps()) {
#ifndef SFNTLY_NO_EXCEPTION
    throw IndexOutOfBoundException("Requested CMap index is out of bounds.");
#else
    return NULL;
#endif
  }
  int32_t platform_id = PlatformId(index);
  int32_t encoding_id = EncodingId(index);
  CMapId cmap_id = NewCMapId(platform_id, encoding_id);
  int32_t offset_ = Offset(index);
  Ptr<FontDataTable::Builder> cmap_builder =
      (CMap::Builder::GetBuilder(data_, offset_, cmap_id));
  if (!cmap_builder) {
#ifndef SFNTLY_NO_EXCEPTION
    throw NoSuchElementException("Cannot find builder for requested CMap.");
#else
    return NULL;
#endif
  }
  return down_cast<CMapTable::CMap*>(cmap_builder->Build());
}

CALLER_ATTACH CMapTable::CMap* CMapTable::GetCMap(const int32_t platform_id,
                                                  const int32_t encoding_id) {
  return GetCMap(NewCMapId(platform_id, encoding_id));
}

CALLER_ATTACH CMapTable::CMap*
CMapTable::GetCMap(const CMapTable::CMapId cmap_id) {
  CMapIdFilter id_filter(cmap_id);
  CMapIterator cmap_iterator(this, &id_filter);
  // There can only be one cmap with a particular CMapId
  if (cmap_iterator.HasNext()) {
    Ptr<CMapTable::CMap> cmap;
    cmap.Attach(cmap_iterator.Next());
    return cmap.Detach();
  }
#ifndef SFNTLY_NO_EXCEPTION
  throw NoSuchElementException();
#else
  return NULL;
#endif
}

int32_t CMapTable::Version() {
  return data_->ReadUShort(Offset::kVersion);
}

int32_t CMapTable::NumCMaps() {
  return data_->ReadUShort(Offset::kNumTables);
}

CMapTable::CMapId CMapTable::GetCMapId(int32_t index) {
  return NewCMapId(PlatformId(index), EncodingId(index));
}

int32_t CMapTable::PlatformId(int32_t index) {
  return data_->ReadUShort(Offset::kEncodingRecordPlatformId +
                           OffsetForEncodingRecord(index));
}

int32_t CMapTable::EncodingId(int32_t index) {
  return data_->ReadUShort(Offset::kEncodingRecordEncodingId +
                           OffsetForEncodingRecord(index));
}

int32_t CMapTable::Offset(int32_t index) {
  return data_->ReadULongAsInt(Offset::kEncodingRecordOffset +
                               OffsetForEncodingRecord(index));
}

int32_t CMapTable::OffsetForEncodingRecord(int32_t index) {
  return Offset::kEncodingRecordStart + index * Offset::kEncodingRecordSize;
}

CMapTable::CMapId CMapTable::NewCMapId(int32_t platform_id,
                                       int32_t encoding_id) {
  CMapId result;
  result.platform_id = platform_id;
  result.encoding_id = encoding_id;
  return result;
}

CMapTable::CMapId CMapTable::NewCMapId(const CMapId& obj) {
  CMapId result;
  result.platform_id = obj.platform_id;
  result.encoding_id = obj.encoding_id;
  return result;
}

/******************************************************************************
 * CMapTable::CMapIterator class
 ******************************************************************************/
CMapTable::CMapIterator::CMapIterator(CMapTable* table,
                                      const CMapFilter* filter)
    : table_index_(0), filter_(filter), table_(table) {
}

bool CMapTable::CMapIterator::HasNext() {
  if (!filter_) {
    if (table_index_ < table_->NumCMaps()) {
      return true;
    }
    return false;
  }

  for (; table_index_ < table_->NumCMaps(); ++table_index_) {
    if (filter_->accept(table_->GetCMapId(table_index_))) {
      return true;
    }
  }
  return false;
}

CALLER_ATTACH CMapTable::CMap* CMapTable::CMapIterator::Next() {
  if (!HasNext()) {
#ifndef SFNTLY_NO_EXCEPTION
    throw NoSuchElementException();
#else
    return NULL;
#endif
  }
  CMapPtr next_cmap;
  next_cmap.Attach(table_->GetCMap(table_index_++));
  if (next_cmap == NULL) {
#ifndef SFNTLY_NO_EXCEPTION
    throw NoSuchElementException("Error during the creation of the CMap");
#else
    return NULL;
#endif
  }
  return next_cmap.Detach();
}

/******************************************************************************
 * CMapTable::CMapId class
 ******************************************************************************/

/******************************************************************************
 * CMapTable::CMapIdComparator class
 ******************************************************************************/

bool CMapTable::CMapIdComparator::operator()(const CMapId& lhs,
                                             const CMapId& rhs) const {
  return ((lhs.platform_id << 8 | lhs.encoding_id) >
      (rhs.platform_id << 8 | rhs.encoding_id));
}

/******************************************************************************
 * CMapTable::CMapIdFilter class
 ******************************************************************************/
CMapTable::CMapIdFilter::CMapIdFilter(const CMapId wanted_id)
    : wanted_id_(wanted_id),
      comparator_(NULL) {
}

CMapTable::CMapIdFilter::CMapIdFilter(const CMapId wanted_id,
                                      const CMapIdComparator* comparator)
    : wanted_id_(wanted_id),
      comparator_(comparator) {
}

bool CMapTable::CMapIdFilter::accept(const CMapId& cmap_id) const {
  if (!comparator_)
    return wanted_id_ == cmap_id;
  return (*comparator_)(wanted_id_, cmap_id);
}

/******************************************************************************
 * CMapTable::CMap class
 ******************************************************************************/
CMapTable::CMap::CMap(ReadableFontData* data, int32_t format,
                      const CMapId& cmap_id)
    : SubTable(data), format_(format), cmap_id_(cmap_id) {
}

CMapTable::CMap::~CMap() {
}

/******************************************************************************
 * CMapTable::CMap::Builder class
 ******************************************************************************/
CMapTable::CMap::Builder::~Builder() {
}

CALLER_ATTACH CMapTable::CMap::Builder*
    CMapTable::CMap::Builder::GetBuilder(ReadableFontData* data, int32_t offset,
                                         const CMapId& cmap_id) {
  // NOT IMPLEMENTED: Java enum value validation
  int32_t format = data->ReadUShort(offset);
  CMapBuilderPtr builder;
  switch (format) {
    case CMapFormat::kFormat0:
      builder.Attach(CMapFormat0::Builder::NewInstance(data, offset, cmap_id));
      break;
    case CMapFormat::kFormat2:
#if defined (SFNTLY_DEBUG_CMAP)
      fprintf(stderr, "Requesting Format2 builder, but it's unsupported; "
              "returning NULL\n");
#endif
      break;
    case CMapFormat::kFormat4:
      builder.Attach(CMapFormat4::Builder::NewInstance(data, offset, cmap_id));
      break;
    default:
#ifdef SFNTLY_DEBUG_CMAP
      fprintf(stderr, "Unknown builder format requested\n");
#endif
      break;
  }
  return builder.Detach();
}

CALLER_ATTACH CMapTable::CMap::Builder*
CMapTable::CMap::Builder::GetBuilder(int32_t format, const CMapId& cmap_id) {
  Ptr<CMapTable::CMap::Builder> builder;
  switch (format) {
    case CMapFormat::kFormat0:
      builder.Attach(CMapFormat0::Builder::NewInstance(cmap_id));
      break;
    case CMapFormat::kFormat2:
#if defined (SFNTLY_DEBUG_CMAP)
      fprintf(stderr, "Requesting Format2 builder, but it's unsupported; "
              "returning NULL\n");
#endif
      break;
    case CMapFormat::kFormat4:
      builder.Attach(CMapFormat4::Builder::NewInstance(cmap_id));
      break;
    default:
#ifdef SFNTLY_DEBUG_CMAP
      fprintf(stderr, "Unknown builder format requested\n");
#endif
      break;
  }
  return builder.Detach();
}

CMapTable::CMap::Builder::Builder(ReadableFontData* data,
                                  int32_t format,
                                  const CMapId& cmap_id)
    : SubTable::Builder(data),
      format_(format),
      cmap_id_(cmap_id),
      language_(0) {
}

CMapTable::CMap::Builder::Builder(WritableFontData* data,
                                  int32_t format,
                                  const CMapId& cmap_id)
    : SubTable::Builder(data),
      format_(format),
      cmap_id_(cmap_id),
      language_(0) {
}

int32_t CMapTable::CMap::Builder::SubSerialize(WritableFontData* new_data) {
  return InternalReadData()->CopyTo(new_data);
}

bool CMapTable::CMap::Builder::SubReadyToSerialize() {
  return true;
}

int32_t CMapTable::CMap::Builder::SubDataSizeToSerialize() {
  ReadableFontDataPtr read_data = InternalReadData();
  if (!read_data)
    return 0;
  return read_data->Length();
}

void CMapTable::CMap::Builder::SubDataSet() {
  // NOP
}

/******************************************************************************
 * CMapTable::CMapFormat0
 ******************************************************************************/
CMapTable::CMapFormat0::~CMapFormat0() {
}

int32_t CMapTable::CMapFormat0::Language() {
  return 0;
}

int32_t CMapTable::CMapFormat0::GlyphId(int32_t character) {
  if (character < 0 || character > 255) {
    return CMapTable::NOTDEF;
  }
  return data_->ReadUByte(character + Offset::kFormat0GlyphIdArray);
}

CMapTable::CMapFormat0::CMapFormat0(ReadableFontData* data,
                                    const CMapId& cmap_id)
    : CMap(data, CMapFormat::kFormat0, cmap_id) {
}

CMapTable::CMap::CharacterIterator* CMapTable::CMapFormat0::Iterator() {
  return new CMapTable::CMapFormat0::CharacterIterator(0, 0xff);
}


/******************************************************************************
 * CMapTable::CMapFormat0::CharacterIterator
 ******************************************************************************/
CMapTable::CMapFormat0::CharacterIterator::CharacterIterator(int32_t start,
                                                             int32_t end)
    : character_(start),
    max_character_(end) {
}

CMapTable::CMapFormat0::CharacterIterator::~CharacterIterator() {}

bool CMapTable::CMapFormat0::CharacterIterator::HasNext() {
  return character_ < max_character_;
}

int32_t CMapTable::CMapFormat0::CharacterIterator::Next() {
  if (HasNext())
    return character_++;
#ifndef SFNTLY_NO_EXCEPTION
  throw NoSuchElementException("No more characters to iterate.");
#endif
  return -1;
}

/******************************************************************************
 * CMapTable::CMapFormat0::Builder
 ******************************************************************************/
// static
CALLER_ATTACH CMapTable::CMapFormat0::Builder*
CMapTable::CMapFormat0::Builder::NewInstance(WritableFontData* data,
                                             int32_t offset,
                                             const CMapId& cmap_id) {
  WritableFontDataPtr wdata;
  if (data) {
    wdata.Attach(down_cast<WritableFontData*>(
        data->Slice(offset,
                    data->ReadUShort(offset + Offset::kFormat0Length))));
  }
  return new Builder(wdata, CMapFormat::kFormat0, cmap_id);
}

// static
CALLER_ATTACH CMapTable::CMapFormat0::Builder*
CMapTable::CMapFormat0::Builder::NewInstance(ReadableFontData* data,
                                             int32_t offset,
                                             const CMapId& cmap_id) {
  ReadableFontDataPtr rdata;
  if (data) {
    rdata.Attach(down_cast<ReadableFontData*>(
        data->Slice(offset,
                    data->ReadUShort(offset + Offset::kFormat0Length))));
  }
  return new Builder(rdata, CMapFormat::kFormat0, cmap_id);
}

// static
CALLER_ATTACH CMapTable::CMapFormat0::Builder*
CMapTable::CMapFormat0::Builder::NewInstance(const CMapId& cmap_id) {
  return new Builder(cmap_id);
}

// Always call NewInstance instead of the constructor for creating a new builder
// object! This refactoring avoids memory leaks when slicing the font data.
CMapTable::CMapFormat0::Builder::Builder(WritableFontData* data, int32_t offset,
                                         const CMapId& cmap_id)
    : CMapTable::CMap::Builder(data, CMapFormat::kFormat0, cmap_id) {
  UNREFERENCED_PARAMETER(offset);
}

CMapTable::CMapFormat0::Builder::Builder(
    ReadableFontData* data,
    int32_t offset,
    const CMapId& cmap_id)
    : CMapTable::CMap::Builder(data, CMapFormat::kFormat0, cmap_id) {
  UNREFERENCED_PARAMETER(offset);
}

CMapTable::CMapFormat0::Builder::Builder(const CMapId& cmap_id)
    : CMap::Builder(reinterpret_cast<ReadableFontData*>(NULL),
                    CMapFormat::kFormat0,
                    cmap_id) {
}

CMapTable::CMapFormat0::Builder::~Builder() {
}

CALLER_ATTACH FontDataTable*
    CMapTable::CMapFormat0::Builder::SubBuildTable(ReadableFontData* data) {
  FontDataTablePtr table = new CMapFormat0(data, cmap_id());
  return table.Detach();
}

/******************************************************************************
 * CMapTable::CMapFormat2
 ******************************************************************************/
CMapTable::CMapFormat2::~CMapFormat2() {
}

int32_t CMapTable::CMapFormat2::Language() {
  return 0;
}

int32_t CMapTable::CMapFormat2::GlyphId(int32_t character) {
  if (character > 0xffff) {
    return CMapTable::NOTDEF;
  }

  uint32_t c = ToBE32(character);
  byte_t high_byte = (c >> 8) & 0xff;
  byte_t low_byte = c & 0xff;
  int32_t offset = SubHeaderOffset(high_byte);

  if (offset == 0) {
    low_byte = high_byte;
    high_byte = 0;
  }

  int32_t first_code = FirstCode(high_byte);
  int32_t entry_count = EntryCount(high_byte);

  if (low_byte < first_code || low_byte >= first_code + entry_count) {
    return CMapTable::NOTDEF;
  }

  int32_t id_range_offset = IdRangeOffset(high_byte);

  // position of idRangeOffset + value of idRangeOffset + index for low byte
  // = firstcode
  int32_t p_location = (offset + Offset::kFormat2SubHeader_idRangeOffset) +
      id_range_offset +
      (low_byte - first_code) * DataSize::kUSHORT;
  int p = data_->ReadUShort(p_location);
  if (p == 0) {
    return CMapTable::NOTDEF;
  }

  if (offset == 0) {
    return p;
  }
  int id_delta = IdDelta(high_byte);
  return (p + id_delta) % 65536;
}

int32_t CMapTable::CMapFormat2::BytesConsumed(int32_t character) {
  uint32_t c = ToBE32(character);
  int32_t high_byte = (c >> 8) & 0xff;
  int32_t offset = SubHeaderOffset(high_byte);
  return (offset == 0) ? 1 : 2;
}

CMapTable::CMapFormat2::CMapFormat2(ReadableFontData* data,
                                    const CMapId& cmap_id)
    : CMap(data, CMapFormat::kFormat2, cmap_id) {
}

int32_t CMapTable::CMapFormat2::SubHeaderOffset(int32_t sub_header_index) {
  return data_->ReadUShort(Offset::kFormat2SubHeaderKeys +
                           sub_header_index * DataSize::kUSHORT);
}

int32_t CMapTable::CMapFormat2::FirstCode(int32_t sub_header_index) {
  int32_t sub_header_offset = SubHeaderOffset(sub_header_index);
  return data_->ReadUShort(sub_header_offset +
                           Offset::kFormat2SubHeaderKeys +
                           Offset::kFormat2SubHeader_firstCode);
}

int32_t CMapTable::CMapFormat2::EntryCount(int32_t sub_header_index) {
  int32_t sub_header_offset = SubHeaderOffset(sub_header_index);
  return data_->ReadUShort(sub_header_offset +
                           Offset::kFormat2SubHeaderKeys +
                           Offset::kFormat2SubHeader_entryCount);
}

int32_t CMapTable::CMapFormat2::IdRangeOffset(int32_t sub_header_index) {
  int32_t sub_header_offset = SubHeaderOffset(sub_header_index);
  return data_->ReadUShort(sub_header_offset +
                           Offset::kFormat2SubHeaderKeys +
                           Offset::kFormat2SubHeader_idRangeOffset);
}

int32_t CMapTable::CMapFormat2::IdDelta(int32_t sub_header_index) {
  int32_t sub_header_offset = SubHeaderOffset(sub_header_index);
  return data_->ReadUShort(sub_header_offset +
                           Offset::kFormat2SubHeaderKeys +
                           Offset::kFormat2SubHeader_idDelta);
}

CMapTable::CMap::CharacterIterator* CMapTable::CMapFormat2::Iterator() {
  // UNIMPLEMENTED
  return NULL;
}

/******************************************************************************
 * CMapTable::CMapFormat2::Builder
 ******************************************************************************/
CMapTable::CMapFormat2::Builder::Builder(WritableFontData* data,
                                         int32_t offset,
                                         const CMapId& cmap_id)
    : CMapTable::CMap::Builder(data ? down_cast<WritableFontData*>(
                                   data->Slice(offset, data->ReadUShort(
                                       offset + Offset::kFormat0Length)))
                               : reinterpret_cast<WritableFontData*>(NULL),
                               CMapFormat::kFormat2, cmap_id) {
  // TODO(arthurhsu): FIXIT: heavy lifting and leak, need fix.
}

CMapTable::CMapFormat2::Builder::Builder(ReadableFontData* data,
                                         int32_t offset,
                                         const CMapId& cmap_id)
    : CMapTable::CMap::Builder(data ? down_cast<ReadableFontData*>(
                                   data->Slice(offset, data->ReadUShort(
                                       offset + Offset::kFormat0Length)))
                               : reinterpret_cast<ReadableFontData*>(NULL),
                               CMapFormat::kFormat2, cmap_id) {
  // TODO(arthurhsu): FIXIT: heavy lifting and leak, need fix.
}

CMapTable::CMapFormat2::Builder::~Builder() {
}

CALLER_ATTACH FontDataTable*
    CMapTable::CMapFormat2::Builder::SubBuildTable(ReadableFontData* data) {
  FontDataTablePtr table = new CMapFormat2(data, cmap_id());
  return table.Detach();
}

/******************************************************************************
 * CMapTable::CMapFormat4
 ******************************************************************************/
CMapTable::CMapFormat4::CMapFormat4(ReadableFontData* data,
                                    const CMapId& cmap_id)
    : CMap(data, CMapFormat::kFormat4, cmap_id),
      seg_count_(SegCount(data)),
      start_code_offset_(StartCodeOffset(seg_count_)),
      end_code_offset_(Offset::kFormat4EndCount),
      id_delta_offset_(IdDeltaOffset(seg_count_)),
      glyph_id_array_offset_(GlyphIdArrayOffset(seg_count_)) {
}

CMapTable::CMapFormat4::~CMapFormat4() {
}

int32_t CMapTable::CMapFormat4::GlyphId(int32_t character) {
  int32_t segment = data_->SearchUShort(StartCodeOffset(seg_count_),
                                        DataSize::kUSHORT,
                                        Offset::kFormat4EndCount,
                                        DataSize::kUSHORT,
                                        seg_count_,
                                        character);
  if (segment == -1) {
    return CMapTable::NOTDEF;
  }
  int32_t start_code = StartCode(segment);
  return RetrieveGlyphId(segment, start_code, character);
}

int32_t CMapTable::CMapFormat4::RetrieveGlyphId(int32_t segment,
                                                int32_t start_code,
                                                int32_t character) {
  if (character < start_code) {
    return CMapTable::NOTDEF;
  }
  int32_t id_range_offset = IdRangeOffset(segment);
  if (id_range_offset == 0) {
    return (character + IdDelta(segment)) % 65536;
  }
  return data_->ReadUShort(id_range_offset +
                           IdRangeOffsetLocation(segment) +
                           2 * (character - start_code));
}

int32_t CMapTable::CMapFormat4::seg_count() {
  return seg_count_;
}

int32_t CMapTable::CMapFormat4::Length() {
  return Length(data_);
}

int32_t CMapTable::CMapFormat4::StartCode(int32_t segment) {
  if (!IsValidIndex(segment)) {
    return -1;
  }
  return StartCode(data_.p_, seg_count_, segment);
}

// static
int32_t CMapTable::CMapFormat4::Language(ReadableFontData* data) {
  int32_t language = data->ReadUShort(Offset::kFormat4Language);
  return language;
}

// static
int32_t CMapTable::CMapFormat4::Length(ReadableFontData* data) {
  int32_t length = data->ReadUShort(Offset::kFormat4Length);
  return length;
}

// static
int32_t CMapTable::CMapFormat4::SegCount(ReadableFontData* data) {
  int32_t seg_count = data->ReadUShort(Offset::kFormat4SegCountX2) / 2;
  return seg_count;
}

// static
int32_t CMapTable::CMapFormat4::StartCode(ReadableFontData* data,
                                          int32_t seg_count,
                                          int32_t index) {
  int32_t start_code = data->ReadUShort(StartCodeOffset(seg_count) +
                                        index * DataSize::kUSHORT);
  return start_code;
}

// static
int32_t CMapTable::CMapFormat4::StartCodeOffset(int32_t seg_count) {
  int32_t start_code_offset = Offset::kFormat4EndCount +
      (seg_count + 1) * DataSize::kUSHORT;
  return start_code_offset;
}

// static
int32_t CMapTable::CMapFormat4::EndCode(ReadableFontData* data,
                                        int32_t seg_count,
                                        int32_t index) {
  UNREFERENCED_PARAMETER(seg_count);
  int32_t end_code = data->ReadUShort(Offset::kFormat4EndCount +
                                      index * DataSize::kUSHORT);
  return end_code;
}

// static
int32_t CMapTable::CMapFormat4::IdDelta(ReadableFontData* data,
                                        int32_t seg_count,
                                        int32_t index) {
  int32_t id_delta = data->ReadUShort(IdDeltaOffset(seg_count) +
                                      index * DataSize::kUSHORT);
  return id_delta;
}

// static
int32_t CMapTable::CMapFormat4::IdDeltaOffset(int32_t seg_count) {
  int32_t id_delta_offset =
      Offset::kFormat4EndCount + (2 * seg_count + 1) * DataSize::kUSHORT;
  return id_delta_offset;
}

// static
int32_t CMapTable::CMapFormat4::IdRangeOffset(ReadableFontData* data,
                                              int32_t seg_count,
                                              int32_t index) {
  int32_t id_range_offset =
      data->ReadUShort(IdRangeOffsetOffset(seg_count)
                       + index * DataSize::kUSHORT);
  return id_range_offset;
}

// static
int32_t CMapTable::CMapFormat4::IdRangeOffsetOffset(int32_t seg_count) {
  int32_t id_range_offset_offset =
      Offset::kFormat4EndCount + (2 * seg_count + 1) * DataSize::kUSHORT +
      seg_count * DataSize::kSHORT;
  return id_range_offset_offset;
}

// static
int32_t CMapTable::CMapFormat4::GlyphIdArrayOffset(int32_t seg_count) {
  int32_t glyph_id_array_offset =
      Offset::kFormat4EndCount + (3 * seg_count + 1) * DataSize::kUSHORT +
      seg_count * DataSize::kSHORT;
  return glyph_id_array_offset;
}

int32_t CMapTable::CMapFormat4::EndCode(int32_t segment) {
  if (IsValidIndex(segment)) {
    return EndCode(data_, seg_count_, segment);
  }
#if defined (SFNTLY_NO_EXCEPTION)
  return -1;
#else
  throw IllegalArgumentException();
#endif
}

bool CMapTable::CMapFormat4::IsValidIndex(int32_t segment) {
  if (segment < 0 || segment >= seg_count_) {
#if defined (SFNTLY_NO_EXCEPTION)
    return false;
#else
    throw IllegalArgumentException();
#endif
  }
  return true;
}

int32_t CMapTable::CMapFormat4::IdDelta(int32_t segment) {
  if (IsValidIndex(segment))
    return IdDelta(data_, seg_count_, segment);
  return -1;
}

int32_t CMapTable::CMapFormat4::IdRangeOffset(int32_t segment) {
  if (IsValidIndex(segment))
    return data_->ReadUShort(IdRangeOffsetLocation(segment));
  return -1;
}

int32_t CMapTable::CMapFormat4::IdRangeOffsetLocation(int32_t segment) {
  if (IsValidIndex(segment))
    return IdRangeOffsetOffset(seg_count_) + segment * DataSize::kUSHORT;
  return -1;
}

int32_t CMapTable::CMapFormat4::GlyphIdArray(int32_t index) {
  return data_->ReadUShort(glyph_id_array_offset_ + index * DataSize::kUSHORT);
}

int32_t CMapTable::CMapFormat4::Language() {
  return Language(data_);
}


CMapTable::CMap::CharacterIterator* CMapTable::CMapFormat4::Iterator() {
  return new CharacterIterator(this);
}

/******************************************************************************
 * CMapTable::CMapFormat4::CharacterIterator class
 ******************************************************************************/
CMapTable::CMapFormat4::CharacterIterator::CharacterIterator(
    CMapFormat4* parent)
    : parent_(parent),
      segment_index_(0),
      first_char_in_segment_(-1),
      last_char_in_segment_(-1),
      next_char_(-1),
      next_char_set_(false) {
}

bool CMapTable::CMapFormat4::CharacterIterator::HasNext() {
  if (next_char_set_)
    return true;
  while (segment_index_ < parent_->seg_count_) {
    if (first_char_in_segment_ < 0) {
      first_char_in_segment_ = parent_->StartCode(segment_index_);
      last_char_in_segment_ = parent_->EndCode(segment_index_);
      next_char_ = first_char_in_segment_;
      next_char_set_ = true;
      return true;
    }
    if (next_char_ < last_char_in_segment_) {
      next_char_++;
      next_char_set_ = true;
      return true;
    }
    segment_index_++;
    first_char_in_segment_ = -1;
  }
  return false;
}

int32_t CMapTable::CMapFormat4::CharacterIterator::Next() {
  if (!next_char_set_) {
    if (!HasNext()) {
#if defined (SFNTLY_NO_EXCEPTION)
      return -1;
#else
      throw NoSuchElementException("No more characters to iterate.");
#endif
    }
  }
  next_char_set_ = false;
  return next_char_;
}

/******************************************************************************
 * CMapTable::CMapFormat4::Builder::Segment class
 ******************************************************************************/
CMapTable::CMapFormat4::Builder::Segment::Segment() {}

CMapTable::CMapFormat4::Builder::Segment::Segment(Segment* other)
    : start_count_(other->start_count_),
      end_count_(other->end_count_),
      id_delta_(other->id_delta_),
      id_range_offset_(other->id_range_offset_) {
}

CMapTable::CMapFormat4::Builder::Segment::Segment(int32_t start_count,
                                                  int32_t end_count,
                                                  int32_t id_delta,
                                                  int32_t id_range_offset)
    : start_count_(start_count),
      end_count_(end_count),
      id_delta_(id_delta),
      id_range_offset_(id_range_offset) {
}

CMapTable::CMapFormat4::Builder::Segment::~Segment() {}

int32_t CMapTable::CMapFormat4::Builder::Segment::start_count() {
  return start_count_;
}

void
CMapTable::CMapFormat4::Builder::Segment::set_start_count(int32_t start_count) {
  start_count_ = start_count;
}

int32_t CMapTable::CMapFormat4::Builder::Segment::end_count() {
  return end_count_;
}

void
CMapTable::CMapFormat4::Builder::Segment::set_end_count(int32_t end_count) {
  end_count_ = end_count;
}

int32_t CMapTable::CMapFormat4::Builder::Segment::id_delta() {
  return id_delta_;
}

void
CMapTable::CMapFormat4::Builder::Segment::set_id_delta(int32_t id_delta) {
  id_delta_ = id_delta;
}

int32_t CMapTable::CMapFormat4::Builder::Segment::id_range_offset() {
  return id_range_offset_;
}

void
CMapTable::CMapFormat4::Builder::Segment::
set_id_range_offset(int32_t id_range_offset) {
  id_range_offset_ = id_range_offset;
}

// static
CALLER_ATTACH SegmentList*
CMapTable::CMapFormat4::Builder::Segment::DeepCopy(SegmentList* original) {
  SegmentList* list = new SegmentList;
  for (SegmentList::iterator it = original->begin(),
           e = original->end(); it != e; ++it) {
    list->push_back(*it);
  }
  return list;
}

/******************************************************************************
 * CMapTable::CMapFormat4::Builder class
 ******************************************************************************/
CALLER_ATTACH CMapTable::CMapFormat4::Builder*
CMapTable::CMapFormat4::Builder::NewInstance(ReadableFontData* data,
                                             int32_t offset,
                                             const CMapId& cmap_id) {
  ReadableFontDataPtr rdata;
  if (data) {
    rdata.Attach
        (down_cast<ReadableFontData*>
         (data->Slice(offset,
                      data->ReadUShort(offset + Offset::kFormat4Length))));
  }
  return new Builder(rdata, CMapFormat::kFormat4, cmap_id);
}

CALLER_ATTACH CMapTable::CMapFormat4::Builder*
CMapTable::CMapFormat4::Builder::NewInstance(WritableFontData* data,
                                             int32_t offset,
                                             const CMapId& cmap_id) {
  WritableFontDataPtr wdata;
  if (data) {
    wdata.Attach
        (down_cast<WritableFontData*>
         (data->Slice(offset,
                      data->ReadUShort(offset + Offset::kFormat4Length))));
  }
  return new Builder(wdata, CMapFormat::kFormat4, cmap_id);
}

CALLER_ATTACH CMapTable::CMapFormat4::Builder*
CMapTable::CMapFormat4::Builder::NewInstance(const CMapId& cmap_id) {
  return new Builder(cmap_id);
}

CMapTable::CMapFormat4::Builder::Builder(ReadableFontData* data, int32_t offset,
                                         const CMapId& cmap_id)
    : CMap::Builder(data, CMapFormat::kFormat4, cmap_id) {
  UNREFERENCED_PARAMETER(offset);
}

CMapTable::CMapFormat4::Builder::Builder(WritableFontData* data, int32_t offset,
                                         const CMapId& cmap_id)
    : CMap::Builder(data, CMapFormat::kFormat4, cmap_id) {
  UNREFERENCED_PARAMETER(offset);
}

CMapTable::CMapFormat4::Builder::Builder(SegmentList* segments,
                                         IntegerList* glyph_id_array,
                                         const CMapId& cmap_id)
    : CMap::Builder(reinterpret_cast<ReadableFontData*>(NULL),
                    CMapFormat::kFormat4, cmap_id),
      segments_(segments->begin(), segments->end()),
      glyph_id_array_(glyph_id_array->begin(), glyph_id_array->end()) {
  set_model_changed();
}

CMapTable::CMapFormat4::Builder::Builder(const CMapId& cmap_id)
    : CMap::Builder(reinterpret_cast<ReadableFontData*>(NULL),
                    CMapFormat::kFormat4, cmap_id) {
}

CMapTable::CMapFormat4::Builder::~Builder() {}

void CMapTable::CMapFormat4::Builder::Initialize(ReadableFontData* data) {
  if (data == NULL || data->Length() == 0)
    return;

  // build segments
  int32_t seg_count = CMapFormat4::SegCount(data);
  for (int32_t index = 0; index < seg_count; ++index) {
    Ptr<Segment> segment = new Segment;
    segment->set_start_count(CMapFormat4::StartCode(data, seg_count, index));
#if defined SFNTLY_DEBUG_CMAP
    fprintf(stderr, "Segment %d; start %d\n", index, segment->start_count());
#endif
    segment->set_end_count(CMapFormat4::EndCode(data, seg_count, index));
    segment->set_id_delta(CMapFormat4::IdDelta(data, seg_count, index));
    segment->set_id_range_offset(CMapFormat4::IdRangeOffset(data,
                                                           seg_count,
                                                           index));
    segments_.push_back(segment);
  }

  // build glyph id array
  int32_t glyph_id_array_offset = CMapFormat4::GlyphIdArrayOffset(seg_count);
  int32_t glyph_id_array_length =
      (CMapFormat4::Length(data) - glyph_id_array_offset)
      / DataSize::kUSHORT;
  fprintf(stderr, "id array size %d\n", glyph_id_array_length);
  for (int32_t i = 0; i < glyph_id_array_length; i += DataSize::kUSHORT) {
    glyph_id_array_.push_back(data->ReadUShort(glyph_id_array_offset + i));
  }
}

SegmentList* CMapTable::CMapFormat4::Builder::segments() {
  if (segments_.empty()) {
    Initialize(InternalReadData());
    set_model_changed();
  }
  return &segments_;
}

void CMapTable::CMapFormat4::Builder::set_segments(SegmentList* segments) {
  segments_.assign(segments->begin(), segments->end());
  set_model_changed();
}

IntegerList* CMapTable::CMapFormat4::Builder::glyph_id_array() {
  if (glyph_id_array_.empty()) {
    Initialize(InternalReadData());
    set_model_changed();
  }
  return &glyph_id_array_;
}

void CMapTable::CMapFormat4::Builder::
set_glyph_id_array(IntegerList* glyph_id_array) {
  glyph_id_array_.assign(glyph_id_array->begin(), glyph_id_array->end());
  set_model_changed();
}

CALLER_ATTACH FontDataTable*
CMapTable::CMapFormat4::Builder::SubBuildTable(ReadableFontData* data) {
  FontDataTablePtr table = new CMapFormat4(data, cmap_id());
  return table.Detach();
}

void CMapTable::CMapFormat4::Builder::SubDataSet() {
  segments_.clear();
  glyph_id_array_.clear();
  set_model_changed();
}

int32_t CMapTable::CMapFormat4::Builder::SubDataSizeToSerialize() {
  if (!model_changed()) {
    return CMap::Builder::SubDataSizeToSerialize();
  }
  int32_t size = Offset::kFormat4FixedSize + segments_.size()
      * (3 * DataSize::kUSHORT + DataSize::kSHORT)
      + glyph_id_array_.size() * DataSize::kSHORT;
  return size;
}

bool CMapTable::CMapFormat4::Builder::SubReadyToSerialize() {
  if (!model_changed()) {
    return CMap::Builder::SubReadyToSerialize();
  }
  if (!segments()->empty()) {
    return true;
  }
  return false;
}

int32_t
CMapTable::CMapFormat4::Builder::SubSerialize(WritableFontData* new_data) {
  if (!model_changed()) {
    return CMap::Builder::SubSerialize(new_data);
  }
  int32_t index = 0;
  index += new_data->WriteUShort(index, CMapFormat::kFormat4);
  index += DataSize::kUSHORT;  // length - write this at the end
  index += new_data->WriteUShort(index, language());

  int32_t seg_count = segments_.size();
  index += new_data->WriteUShort(index, seg_count * 2);
  int32_t log2_seg_count = FontMath::Log2(seg_count);
  int32_t search_range = 1 << (log2_seg_count + 1);
  index += new_data->WriteUShort(index, search_range);
  int32_t entry_selector = log2_seg_count;
  index += new_data->WriteUShort(index, entry_selector);
  int32_t range_shift = 2 * seg_count - search_range;
  index += new_data->WriteUShort(index, range_shift);

  for (int32_t i = 0; i < seg_count; ++i) {
    index += new_data->WriteUShort(index, segments_[i]->end_count());
  }
  index += new_data->WriteUShort(index, 0);  // reserved ushort
  for (int32_t i = 0; i < seg_count; ++i) {
#if defined SFNTLY_DEBUG_CMAP
    fprintf(stderr, "Segment %d; start %d\n", i, segments_[i]->start_count());
#endif
    index += new_data->WriteUShort(index, segments_[i]->start_count());
  }
  for (int32_t i = 0; i < seg_count; ++i) {
    index += new_data->WriteShort(index, segments_[i]->id_delta());
  }
  for (int32_t i = 0; i < seg_count; ++i) {
    index += new_data->WriteUShort(index, segments_[i]->id_range_offset());
  }

#if defined SFNTLY_DEBUG_CMAP
  fprintf(stderr, "Glyph id array size %lu\n", glyph_id_array_.size());
#endif
  for (size_t i = 0; i < glyph_id_array_.size(); ++i) {
    index += new_data->WriteUShort(index, glyph_id_array_[i]);
  }

  new_data->WriteUShort(Offset::kFormat4Length, index);
  return index;
}

/******************************************************************************
 * CMapTable::Builder class
 ******************************************************************************/
CMapTable::Builder::Builder(Header* header, WritableFontData* data)
    : SubTableContainerTable::Builder(header, data), version_(0) {
}

CMapTable::Builder::Builder(Header* header, ReadableFontData* data)
    : SubTableContainerTable::Builder(header, data), version_(0) {
}

CMapTable::Builder::~Builder() {
}

int32_t CMapTable::Builder::SubSerialize(WritableFontData* new_data) {
  int32_t size = new_data->WriteUShort(CMapTable::Offset::kVersion,
                                       version_);
  size += new_data->WriteUShort(CMapTable::Offset::kNumTables,
                                GetCMapBuilders()->size());

  int32_t index_offset = size;
  size += GetCMapBuilders()->size() * CMapTable::Offset::kEncodingRecordSize;
  for (CMapBuilderMap::iterator it = GetCMapBuilders()->begin(),
           e = GetCMapBuilders()->end(); it != e; ++it) {
    CMapBuilderPtr b = it->second;
    // header entry
    index_offset += new_data->WriteUShort(index_offset, b->platform_id());
    index_offset += new_data->WriteUShort(index_offset, b->encoding_id());
    index_offset += new_data->WriteULong(index_offset, size);

    // cmap
    FontDataPtr slice;
    slice.Attach(new_data->Slice(size));
    size += b->SubSerialize(down_cast<WritableFontData*>(slice.p_));
  }
  return size;
}

bool CMapTable::Builder::SubReadyToSerialize() {
  if (GetCMapBuilders()->empty())
    return false;

  // check each table
  for (CMapBuilderMap::iterator it = GetCMapBuilders()->begin(),
           e = GetCMapBuilders()->end(); it != e; ++it) {
    if (!it->second->SubReadyToSerialize())
      return false;
  }
  return true;
}

int32_t CMapTable::Builder::SubDataSizeToSerialize() {
  if (GetCMapBuilders()->empty())
    return 0;

  bool variable = false;
  int32_t size = CMapTable::Offset::kEncodingRecordStart +
      GetCMapBuilders()->size() * CMapTable::Offset::kEncodingRecordSize;

  // calculate size of each table
  for (CMapBuilderMap::iterator it = GetCMapBuilders()->begin(),
           e = GetCMapBuilders()->end(); it != e; ++it) {
    int32_t cmap_size = it->second->SubDataSizeToSerialize();
    size += abs(cmap_size);
    variable |= cmap_size <= 0;
  }
  return variable ? -size : size;
}

void CMapTable::Builder::SubDataSet() {
  GetCMapBuilders()->clear();
  Table::Builder::set_model_changed();
}

CALLER_ATTACH FontDataTable*
    CMapTable::Builder::SubBuildTable(ReadableFontData* data) {
  FontDataTablePtr table = new CMapTable(header(), data);
  return table.Detach();
}

CALLER_ATTACH CMapTable::Builder*
    CMapTable::Builder::CreateBuilder(Header* header,
                                      WritableFontData* data) {
  Ptr<CMapTable::Builder> builder;
  builder = new CMapTable::Builder(header, data);
  return builder.Detach();
}

// static
CALLER_ATTACH CMapTable::CMap::Builder*
    CMapTable::Builder::CMapBuilder(ReadableFontData* data, int32_t index) {
  if (index < 0 || index > NumCMaps(data)) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException(
              "CMap table is outside of the bounds of the known tables.");
#endif
    return NULL;
  }

  int32_t platform_id = data->ReadUShort(Offset::kEncodingRecordPlatformId +
                                         OffsetForEncodingRecord(index));
  int32_t encoding_id = data->ReadUShort(Offset::kEncodingRecordEncodingId +
                                         OffsetForEncodingRecord(index));
  int32_t offset = data->ReadULongAsInt(Offset::kEncodingRecordOffset +
                                        OffsetForEncodingRecord(index));
  return CMap::Builder::GetBuilder(data, offset,
                                   NewCMapId(platform_id, encoding_id));
}

// static
int32_t CMapTable::Builder::NumCMaps(ReadableFontData* data) {
  if (data == NULL) {
    return 0;
  }
  return data->ReadUShort(Offset::kNumTables);
}

int32_t CMapTable::Builder::NumCMaps() {
  return GetCMapBuilders()->size();
}

void CMapTable::Builder::Initialize(ReadableFontData* data) {
  int32_t num_cmaps = NumCMaps(data);
  for (int32_t i = 0; i < num_cmaps; ++i) {
    CMapTable::CMap::Builder* cmap_builder = CMapBuilder(data, i);
    if (!cmap_builder)
      continue;
    cmap_builders_[cmap_builder->cmap_id()] = cmap_builder;
  }
}

CMapTable::CMap::Builder* CMapTable::Builder::NewCMapBuilder(
    const CMapId& cmap_id,
    ReadableFontData* data) {
  Ptr<WritableFontData> wfd;
  wfd.Attach(WritableFontData::CreateWritableFontData(data->Size()));
  data->CopyTo(wfd.p_);
  CMapTable::CMapBuilderPtr builder;
  builder.Attach(CMap::Builder::GetBuilder(wfd.p_, 0, cmap_id));
  CMapBuilderMap* cmap_builders = CMapTable::Builder::GetCMapBuilders();
  cmap_builders->insert(std::make_pair(cmap_id, builder.p_));
  return builder.Detach();
}

CMapTable::CMap::Builder*
CMapTable::Builder::NewCMapBuilder(int32_t format, const CMapId& cmap_id) {
  Ptr<CMapTable::CMap::Builder> cmap_builder;
  cmap_builder.Attach(CMap::Builder::GetBuilder(format, cmap_id));
  CMapBuilderMap* cmap_builders = CMapTable::Builder::GetCMapBuilders();
  cmap_builders->insert(std::make_pair(cmap_id, cmap_builder.p_));
  return cmap_builder.Detach();
}

CMapTable::CMap::Builder*
CMapTable::Builder::CMapBuilder(const CMapId& cmap_id) {
  CMapBuilderMap* cmap_builders = this->GetCMapBuilders();
  CMapBuilderMap::iterator builder = cmap_builders->find(cmap_id);
  if (builder != cmap_builders->end())
    return builder->second;
#ifndef SFNTLY_NO_EXCEPTION
  throw NoSuchElementException("No builder found for cmap_id");
#else
  return NULL;
#endif
}

CMapTable::CMapBuilderMap* CMapTable::Builder::GetCMapBuilders() {
  if (cmap_builders_.empty()) {
    Initialize(InternalReadData());
    set_model_changed();
  }
  return &cmap_builders_;
}

}  // namespace sfntly
