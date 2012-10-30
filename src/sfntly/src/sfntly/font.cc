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

#include "sfntly/font.h"

#include <stdio.h>

#include <functional>
#include <algorithm>
#include <map>
#include <string>
#include <typeinfo>
#include <iterator>

#include "sfntly/data/font_input_stream.h"
#include "sfntly/font_factory.h"
#include "sfntly/math/fixed1616.h"
#include "sfntly/math/font_math.h"
#include "sfntly/port/exception_type.h"
#include "sfntly/table/core/font_header_table.h"
#include "sfntly/table/core/horizontal_device_metrics_table.h"
#include "sfntly/table/core/horizontal_header_table.h"
#include "sfntly/table/core/horizontal_metrics_table.h"
#include "sfntly/table/core/maximum_profile_table.h"
#include "sfntly/table/truetype/loca_table.h"
#include "sfntly/tag.h"

namespace sfntly {

const int32_t SFNTVERSION_MAJOR = 1;
const int32_t SFNTVERSION_MINOR = 0;

/******************************************************************************
 * Font class
 ******************************************************************************/
Font::~Font() {}

bool Font::HasTable(int32_t tag) {
  TableMap::const_iterator result = tables_.find(tag);
  TableMap::const_iterator end = tables_.end();
  return (result != end);
}

// Changed by Kovid: these four methods cannot be inlined, if they are they
// return incorrect values when compiled with -fPIC
int32_t Font::sfnt_version() { return sfnt_version_; }

ByteVector* Font::digest() { return &digest_; }

int64_t Font::checksum() { return checksum_; }

int32_t Font::num_tables() { return (int32_t)tables_.size(); }


Table* Font::GetTable(int32_t tag) {
  if (!HasTable(tag)) {
    return NULL;
  }
  return tables_[tag];
}

const TableMap* Font::GetTableMap() {
  return &tables_;
}

void Font::Serialize(OutputStream* os, IntegerList* table_ordering) {
  assert(table_ordering);
  IntegerList final_table_ordering;
  GenerateTableOrdering(table_ordering, &final_table_ordering);
  TableHeaderList table_records;
  BuildTableHeadersForSerialization(&final_table_ordering, &table_records);

  FontOutputStream fos(os);
  SerializeHeader(&fos, &table_records);
  SerializeTables(&fos, &table_records);
}

Font::Font(int32_t sfnt_version, ByteVector* digest)
    : sfnt_version_(sfnt_version) {
  // non-trivial assignments that makes debugging hard if placed in
  // initialization list
  digest_ = *digest;
}

void Font::BuildTableHeadersForSerialization(IntegerList* table_ordering,
                                             TableHeaderList* table_headers) {
  assert(table_headers);
  assert(table_ordering);

  IntegerList final_table_ordering;
  GenerateTableOrdering(table_ordering, &final_table_ordering);
  int32_t table_offset = Offset::kTableRecordBegin + num_tables() *
                         Offset::kTableRecordSize;
  for (IntegerList::iterator tag = final_table_ordering.begin(),
                             tag_end = final_table_ordering.end();
                             tag != tag_end; ++tag) {
    if (tables_.find(*tag) == tables_.end()) {
      continue;
    }
    TablePtr table = tables_[*tag];
    if (table != NULL) {
      HeaderPtr header =
          new Header(*tag, table->CalculatedChecksum(), table_offset,
                     table->header()->length());
      table_headers->push_back(header);
      table_offset += (table->DataLength() + 3) & ~3;
    }
  }
}

void Font::SerializeHeader(FontOutputStream* fos,
                           TableHeaderList* table_headers) {
  fos->WriteFixed(sfnt_version_);
  fos->WriteUShort(table_headers->size());
  int32_t log2_of_max_power_of_2 = FontMath::Log2(table_headers->size());
  int32_t search_range = 2 << (log2_of_max_power_of_2 - 1 + 4);
  fos->WriteUShort(search_range);
  fos->WriteUShort(log2_of_max_power_of_2);
  fos->WriteUShort((table_headers->size() * 16) - search_range);

  HeaderTagSortedSet sorted_headers;
  std::copy(table_headers->begin(),
            table_headers->end(),
            std::inserter(sorted_headers, sorted_headers.end()));

  for (HeaderTagSortedSet::iterator record = sorted_headers.begin(),
                                    record_end = sorted_headers.end();
                                    record != record_end; ++record) {
    fos->WriteULong((*record)->tag());
    fos->WriteULong((int32_t)((*record)->checksum()));
    fos->WriteULong((*record)->offset());
    fos->WriteULong((*record)->length());
  }
}

void Font::SerializeTables(FontOutputStream* fos,
                           TableHeaderList* table_headers) {
  assert(fos);
  assert(table_headers);
  for (TableHeaderList::iterator record = table_headers->begin(),
                                 end_of_headers = table_headers->end();
                                 record != end_of_headers; ++record) {
    TablePtr target_table = GetTable((*record)->tag());
    if (target_table == NULL) {
#if !defined (SFNTLY_NO_EXCEPTION)
      throw IOException("Table out of sync with font header.");
#endif
      return;
    }
    int32_t table_size = target_table->Serialize(fos);
    if (table_size != (*record)->length()) {
      assert(false);
    }
    int32_t filler_size = ((table_size + 3) & ~3) - table_size;
    for (int32_t i = 0; i < filler_size; ++i) {
      fos->Write(static_cast<byte_t>(0));
    }
  }
}

void Font::GenerateTableOrdering(IntegerList* default_table_ordering,
                                 IntegerList* table_ordering) {
  assert(default_table_ordering);
  assert(table_ordering);
  table_ordering->clear();
  if (default_table_ordering->empty()) {
    DefaultTableOrdering(default_table_ordering);
  }

  typedef std::map<int32_t, bool> Int2Bool;
  typedef std::pair<int32_t, bool> Int2BoolEntry;
  Int2Bool tables_in_font;
  for (TableMap::iterator table = tables_.begin(), table_end = tables_.end();
                          table != table_end; ++table) {
    tables_in_font.insert(Int2BoolEntry(table->first, false));
  }
  for (IntegerList::iterator tag = default_table_ordering->begin(),
                             tag_end = default_table_ordering->end();
                             tag != tag_end; ++tag) {
    if (HasTable(*tag)) {
      table_ordering->push_back(*tag);
      tables_in_font[*tag] = true;
    }
  }
  for (Int2Bool::iterator table = tables_in_font.begin(),
                          table_end = tables_in_font.end();
                          table != table_end; ++table) {
    if (table->second == false)
      table_ordering->push_back(table->first);
  }
}

void Font::DefaultTableOrdering(IntegerList* default_table_ordering) {
  assert(default_table_ordering);
  default_table_ordering->clear();
  if (HasTable(Tag::CFF)) {
    default_table_ordering->resize(CFF_TABLE_ORDERING_SIZE);
    std::copy(CFF_TABLE_ORDERING, CFF_TABLE_ORDERING + CFF_TABLE_ORDERING_SIZE,
              default_table_ordering->begin());
    return;
  }
  default_table_ordering->resize(TRUE_TYPE_TABLE_ORDERING_SIZE);
  std::copy(TRUE_TYPE_TABLE_ORDERING,
            TRUE_TYPE_TABLE_ORDERING + TRUE_TYPE_TABLE_ORDERING_SIZE,
            default_table_ordering->begin());
}

/******************************************************************************
 * Font::Builder class
 ******************************************************************************/
Font::Builder::~Builder() {}

CALLER_ATTACH Font::Builder* Font::Builder::GetOTFBuilder(FontFactory* factory,
                                                          InputStream* is) {
  FontBuilderPtr builder = new Builder(factory);
  builder->LoadFont(is);
  return builder.Detach();
}

CALLER_ATTACH Font::Builder* Font::Builder::GetOTFBuilder(
    FontFactory* factory,
    WritableFontData* wfd,
    int32_t offset_to_offset_table) {
  FontBuilderPtr builder = new Builder(factory);
  builder->LoadFont(wfd, offset_to_offset_table);
  return builder.Detach();
}

CALLER_ATTACH Font::Builder* Font::Builder::GetOTFBuilder(
    FontFactory* factory) {
  FontBuilderPtr builder = new Builder(factory);
  return builder.Detach();
}

bool Font::Builder::ReadyToBuild() {
  // just read in data with no manipulation
  if (table_builders_.empty() && !data_blocks_.empty()) {
    return true;
  }

  // TODO(stuartg): font level checks - required tables etc?
  for (TableBuilderMap::iterator table_builder = table_builders_.begin(),
                                 table_builder_end = table_builders_.end();
                                 table_builder != table_builder_end;
                                 ++table_builder) {
    if (!table_builder->second->ReadyToBuild())
      return false;
  }
  return true;
}

CALLER_ATTACH Font* Font::Builder::Build() {
  FontPtr font = new Font(sfnt_version_, &digest_);

  if (!table_builders_.empty()) {
    // Note: Different from Java. Directly use font->tables_ here to avoid
    //       STL container copying.
    BuildTablesFromBuilders(font, &table_builders_, &font->tables_);
  }

  table_builders_.clear();
  data_blocks_.clear();
  return font.Detach();
}

void Font::Builder::SetDigest(ByteVector* digest) {
  digest_.clear();
  digest_ = *digest;
}

void Font::Builder::ClearTableBuilders() {
  table_builders_.clear();
}

bool Font::Builder::HasTableBuilder(int32_t tag) {
  return (table_builders_.find(tag) != table_builders_.end());
}

Table::Builder* Font::Builder::GetTableBuilder(int32_t tag) {
  if (HasTableBuilder(tag))
    return table_builders_[tag];
  return NULL;
}

Table::Builder* Font::Builder::NewTableBuilder(int32_t tag) {
  HeaderPtr header = new Header(tag);
  TableBuilderPtr builder;
  builder.Attach(Table::Builder::GetBuilder(header, NULL));
  table_builders_.insert(TableBuilderEntry(header->tag(), builder));
  return builder;
}

Table::Builder* Font::Builder::NewTableBuilder(int32_t tag,
                                               ReadableFontData* src_data) {
  assert(src_data);
  WritableFontDataPtr data;
  data.Attach(WritableFontData::CreateWritableFontData(src_data->Length()));
  // TODO(stuarg): take over original data instead?
  src_data->CopyTo(data);

  HeaderPtr header = new Header(tag, data->Length());
  TableBuilderPtr builder;
  builder.Attach(Table::Builder::GetBuilder(header, data));
  table_builders_.insert(TableBuilderEntry(tag, builder));
  return builder;
}

void Font::Builder::RemoveTableBuilder(int32_t tag) {
  TableBuilderMap::iterator target = table_builders_.find(tag);
  if (target != table_builders_.end()) {
    table_builders_.erase(target);
  }
}

Font::Builder::Builder(FontFactory* factory)
    : factory_(factory),
      sfnt_version_(Fixed1616::Fixed(SFNTVERSION_MAJOR, SFNTVERSION_MINOR)) {
}

void Font::Builder::LoadFont(InputStream* is) {
  // Note: we do not throw exception here for is.  This is more of an assertion.
  assert(is);
  FontInputStream font_is(is);
  HeaderOffsetSortedSet records;
  ReadHeader(&font_is, &records);
  LoadTableData(&records, &font_is, &data_blocks_);
  BuildAllTableBuilders(&data_blocks_, &table_builders_);
  font_is.Close();
}

void Font::Builder::LoadFont(WritableFontData* wfd,
                             int32_t offset_to_offset_table) {
  // Note: we do not throw exception here for is.  This is more of an assertion.
  assert(wfd);
  HeaderOffsetSortedSet records;
  ReadHeader(wfd, offset_to_offset_table, &records);
  LoadTableData(&records, wfd, &data_blocks_);
  BuildAllTableBuilders(&data_blocks_, &table_builders_);
}

int32_t Font::Builder::SfntWrapperSize() {
  return Offset::kSfntHeaderSize +
         (Offset::kTableRecordSize * table_builders_.size());
}

void Font::Builder::BuildAllTableBuilders(DataBlockMap* table_data,
                                          TableBuilderMap* builder_map) {
  for (DataBlockMap::iterator record = table_data->begin(),
                              record_end = table_data->end();
                              record != record_end; ++record) {
    TableBuilderPtr builder;
    builder.Attach(GetTableBuilder(record->first.p_, record->second.p_));
    builder_map->insert(TableBuilderEntry(record->first->tag(), builder));
  }
  InterRelateBuilders(&table_builders_);
}

CALLER_ATTACH
Table::Builder* Font::Builder::GetTableBuilder(Header* header,
                                               WritableFontData* data) {
  return Table::Builder::GetBuilder(header, data);
}

void Font::Builder::BuildTablesFromBuilders(Font* font,
                                            TableBuilderMap* builder_map,
                                            TableMap* table_map) {
  UNREFERENCED_PARAMETER(font);
  InterRelateBuilders(builder_map);

  // Now build all the tables.
  for (TableBuilderMap::iterator builder = builder_map->begin(),
                                 builder_end = builder_map->end();
                                 builder != builder_end; ++builder) {
    TablePtr table;
    if (builder->second && builder->second->ReadyToBuild()) {
      table.Attach(down_cast<Table*>(builder->second->Build()));
    }
    if (table == NULL) {
      table_map->clear();
#if !defined (SFNTLY_NO_EXCEPTION)
      std::string builder_string = "Unable to build table - ";
      char* table_name = TagToString(builder->first);
      builder_string += table_name;
      delete[] table_name;
      throw RuntimeException(builder_string.c_str());
#endif
      return;
    }
    table_map->insert(TableMapEntry(table->header()->tag(), table));
  }
}

static Table::Builder* GetBuilder(TableBuilderMap* builder_map, int32_t tag) {
  if (builder_map) {
    TableBuilderMap::iterator target = builder_map->find(tag);
    if (target != builder_map->end()) {
      return target->second.p_;
    }
  }

  return NULL;
}

void Font::Builder::InterRelateBuilders(TableBuilderMap* builder_map) {
  Table::Builder* raw_head_builder = GetBuilder(builder_map, Tag::head);
  FontHeaderTableBuilderPtr header_table_builder;
  if (raw_head_builder != NULL) {
      header_table_builder =
          down_cast<FontHeaderTable::Builder*>(raw_head_builder);
  }

  Table::Builder* raw_hhea_builder = GetBuilder(builder_map, Tag::hhea);
  HorizontalHeaderTableBuilderPtr horizontal_header_builder;
  if (raw_head_builder != NULL) {
      horizontal_header_builder =
          down_cast<HorizontalHeaderTable::Builder*>(raw_hhea_builder);
  }

  Table::Builder* raw_maxp_builder = GetBuilder(builder_map, Tag::maxp);
  MaximumProfileTableBuilderPtr max_profile_builder;
  if (raw_maxp_builder != NULL) {
      max_profile_builder =
          down_cast<MaximumProfileTable::Builder*>(raw_maxp_builder);
  }

  Table::Builder* raw_loca_builder = GetBuilder(builder_map, Tag::loca);
  LocaTableBuilderPtr loca_table_builder;
  if (raw_loca_builder != NULL) {
      loca_table_builder = down_cast<LocaTable::Builder*>(raw_loca_builder);
  }

  Table::Builder* raw_hmtx_builder = GetBuilder(builder_map, Tag::hmtx);
  HorizontalMetricsTableBuilderPtr horizontal_metrics_builder;
  if (raw_hmtx_builder != NULL) {
      horizontal_metrics_builder =
          down_cast<HorizontalMetricsTable::Builder*>(raw_hmtx_builder);
  }

#if defined (SFNTLY_EXPERIMENTAL)
  Table::Builder* raw_hdmx_builder = GetBuilder(builder_map, Tag::hdmx);
  HorizontalDeviceMetricsTableBuilderPtr hdmx_table_builder;
  if (raw_hdmx_builder != NULL) {
      hdmx_table_builder =
          down_cast<HorizontalDeviceMetricsTable::Builder*>(raw_hdmx_builder);
  }
#endif

  // set the inter table data required to build certain tables
  if (horizontal_metrics_builder != NULL) {
    if (max_profile_builder != NULL) {
      horizontal_metrics_builder->SetNumGlyphs(
          max_profile_builder->NumGlyphs());
    }
    if (horizontal_header_builder != NULL) {
      horizontal_metrics_builder->SetNumberOfHMetrics(
          horizontal_header_builder->NumberOfHMetrics());
    }
  }

  if (loca_table_builder != NULL) {
    if (max_profile_builder != NULL) {
      loca_table_builder->SetNumGlyphs(max_profile_builder->NumGlyphs());
    }
    if (header_table_builder != NULL) {
      loca_table_builder->set_format_version(
          header_table_builder->IndexToLocFormat());
    }
  }

#if defined (SFNTLY_EXPERIMENTAL)
  // Note: In C++, hdmx_table_builder can be NULL in a subsetter.
  if (max_profile_builder != NULL && hdmx_table_builder != NULL) {
    hdmx_table_builder->SetNumGlyphs(max_profile_builder->NumGlyphs());
  }
#endif
}

void Font::Builder::ReadHeader(FontInputStream* is,
                               HeaderOffsetSortedSet* records) {
  assert(records);
  sfnt_version_ = is->ReadFixed();
  num_tables_ = is->ReadUShort();
  search_range_ = is->ReadUShort();
  entry_selector_ = is->ReadUShort();
  range_shift_ = is->ReadUShort();

  for (int32_t table_number = 0; table_number < num_tables_; ++table_number) {
    // Need to use temporary vars here.  C++ evaluates function parameters from
    // right to left and thus breaks the order of input stream.
    int32_t tag = is->ReadULongAsInt();
    int64_t checksum = is->ReadULong();
    int32_t offset = is->ReadULongAsInt();
    int32_t length = is->ReadULongAsInt();
    HeaderPtr table = new Header(tag, checksum, offset, length);
    records->insert(table);
  }
}

void Font::Builder::ReadHeader(ReadableFontData* fd,
                               int32_t offset,
                               HeaderOffsetSortedSet* records) {
  assert(records);
  sfnt_version_ = fd->ReadFixed(offset + Offset::kSfntVersion);
  num_tables_ = fd->ReadUShort(offset + Offset::kNumTables);
  search_range_ = fd->ReadUShort(offset + Offset::kSearchRange);
  entry_selector_ = fd->ReadUShort(offset + Offset::kEntrySelector);
  range_shift_ = fd->ReadUShort(offset + Offset::kRangeShift);

  int32_t table_offset = offset + Offset::kTableRecordBegin;
  for (int32_t table_number = 0;
       table_number < num_tables_;
       table_number++, table_offset += Offset::kTableRecordSize) {
    int32_t tag = fd->ReadULongAsInt(table_offset + Offset::kTableTag);
    int64_t checksum = fd->ReadULong(table_offset + Offset::kTableCheckSum);
    int32_t offset = fd->ReadULongAsInt(table_offset + Offset::kTableOffset);
    int32_t length = fd->ReadULongAsInt(table_offset + Offset::kTableLength);
    HeaderPtr table = new Header(tag, checksum, offset, length);
    records->insert(table);
  }
}

void Font::Builder::LoadTableData(HeaderOffsetSortedSet* headers,
                                  FontInputStream* is,
                                  DataBlockMap* table_data) {
  assert(table_data);
  for (HeaderOffsetSortedSet::iterator table_header = headers->begin(),
                                       table_end = headers->end();
                                       table_header != table_end;
                                       ++table_header) {
    is->Skip((*table_header)->offset() - is->position());
    FontInputStream table_is(is, (*table_header)->length());
    WritableFontDataPtr data;
    data.Attach(
        WritableFontData::CreateWritableFontData((*table_header)->length()));
    data->CopyFrom(&table_is, (*table_header)->length());
    table_data->insert(DataBlockEntry(*table_header, data));
  }
}

void Font::Builder::LoadTableData(HeaderOffsetSortedSet* headers,
                                  WritableFontData* fd,
                                  DataBlockMap* table_data) {
  for (HeaderOffsetSortedSet::iterator table_header = headers->begin(),
                                       table_end = headers->end();
                                       table_header != table_end;
                                       ++table_header) {
    FontDataPtr sliced_data;
    sliced_data.Attach(
        fd->Slice((*table_header)->offset(), (*table_header)->length()));
    WritableFontDataPtr data = down_cast<WritableFontData*>(sliced_data.p_);
    table_data->insert(DataBlockEntry(*table_header, data));
  }
}

}  // namespace sfntly
