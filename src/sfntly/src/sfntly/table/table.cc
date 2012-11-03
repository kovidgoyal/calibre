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
#include "sfntly/table/table.h"

#include "sfntly/font.h"
#include "sfntly/tag.h"
#include "sfntly/table/bitmap/ebdt_table.h"
#include "sfntly/table/bitmap/eblc_table.h"
#include "sfntly/table/bitmap/ebsc_table.h"
#include "sfntly/table/core/cmap_table.h"
#include "sfntly/table/core/font_header_table.h"
#include "sfntly/table/core/horizontal_device_metrics_table.h"
#include "sfntly/table/core/horizontal_header_table.h"
#include "sfntly/table/core/horizontal_metrics_table.h"
#include "sfntly/table/core/maximum_profile_table.h"
#include "sfntly/table/core/name_table.h"
#include "sfntly/table/core/os2_table.h"
#include "sfntly/table/generic_table_builder.h"
#include "sfntly/table/table_based_table_builder.h"
#include "sfntly/table/truetype/glyph_table.h"
#include "sfntly/table/truetype/loca_table.h"

namespace sfntly {

/******************************************************************************
 * Table class
 ******************************************************************************/
Table::~Table() {}

int64_t Table::CalculatedChecksum() {
  return data_->Checksum();
}

void Table::SetFont(Font* font) {
  font_ = font;
}

Table::Table(Header* header, ReadableFontData* data)
    : FontDataTable(data) {
  header_ = header;
}

/******************************************************************************
 * Table::Builder class
 ******************************************************************************/
Table::Builder::~Builder() {
  header_.Release();
}

void Table::Builder::NotifyPostTableBuild(FontDataTable* table) {
  if (model_changed() || data_changed()) {
    Table* derived_table = down_cast<Table*>(table);
    derived_table->header_ = new Header(header()->tag(),
                                        derived_table->DataLength());
  }
}

CALLER_ATTACH
Table::Builder* Table::Builder::GetBuilder(Header* header,
                                           WritableFontData* table_data) {
  int32_t tag = header->tag();
  Table::Builder* builder_raw = NULL;

  // Note: Tables are commented out when they are not used/ported.
  // TODO(arthurhsu): IMPLEMENT: finish tables that are not ported.
  if (tag == Tag::head) {
    builder_raw = static_cast<Table::Builder*>(
        FontHeaderTable::Builder::CreateBuilder(header, table_data));
#if defined (SFNTLY_EXPERIMENTAL)
  } else if (tag == Tag::cmap) {
    builder_raw = static_cast<Table::Builder*>(
        CMapTable::Builder::CreateBuilder(header, table_data));
#endif  // SFNTLY_EXPERIMENTAL
  } else if (tag == Tag::hhea) {
    builder_raw = static_cast<Table::Builder*>(
        HorizontalHeaderTable::Builder::CreateBuilder(header, table_data));
  } else if (tag == Tag::hmtx) {
    builder_raw = static_cast<Table::Builder*>(
        HorizontalMetricsTable::Builder::CreateBuilder(header, table_data));
  } else if (tag == Tag::maxp) {
    builder_raw = static_cast<Table::Builder*>(
        MaximumProfileTable::Builder::CreateBuilder(header, table_data));
  } else if (tag == Tag::name) {
    builder_raw = static_cast<Table::Builder*>(
        NameTable::Builder::CreateBuilder(header, table_data));
  } else if (tag == Tag::OS_2) {
    builder_raw = static_cast<Table::Builder*>(
        OS2Table::Builder::CreateBuilder(header, table_data));
  }/* else if (tag == Tag::PostScript) {
    builder_raw = static_cast<Table::Builder*>(
        PostScriptTable::Builder::CreateBuilder(header, table_data));
  } else if (tag == Tag::cvt) {
    builder_raw = static_cast<Table::Builder*>(
        ControlValueTable::Builder::CreateBuilder(header, table_data));
  }*/ else if (tag == Tag::glyf) {
    builder_raw = static_cast<Table::Builder*>(
        GlyphTable::Builder::CreateBuilder(header, table_data));
  } else if (tag == Tag::loca) {
    builder_raw = static_cast<Table::Builder*>(
        LocaTable::Builder::CreateBuilder(header, table_data));
  } else if (tag == Tag::EBDT || tag == Tag::bdat) {
    builder_raw = static_cast<Table::Builder*>(
        EbdtTable::Builder::CreateBuilder(header, table_data));
  } else if (tag == Tag::EBLC || tag == Tag::bloc) {
    builder_raw = static_cast<Table::Builder*>(
        EblcTable::Builder::CreateBuilder(header, table_data));
  } else if (tag == Tag::EBSC) {
    builder_raw = static_cast<Table::Builder*>(
        EbscTable::Builder::CreateBuilder(header, table_data));
  } /* else if (tag == Tag::prep) {
    builder_raw = static_cast<Table::Builder*>(
        ControlProgramTable::Builder::CreateBuilder(header, table_data));
  }*/ else if (tag == Tag::bhed) {
    builder_raw = static_cast<Table::Builder*>(
        FontHeaderTable::Builder::CreateBuilder(header, table_data));
#if defined (SFNTLY_EXPERIMENTAL)
  } else if (tag == Tag::hdmx) {
    builder_raw = static_cast<Table::Builder*>(
        HorizontalDeviceMetricsTable::Builder::CreateBuilder(header,
                                                             table_data));
#endif  // SFNTLY_EXPERIMENTAL
  } else {
    builder_raw = static_cast<Table::Builder*>(
        GenericTableBuilder::CreateBuilder(header, table_data));
  }

  return builder_raw;
}

Table::Builder::Builder(Header* header, WritableFontData* data)
    : FontDataTable::Builder(data) {
  header_ = header;
}

Table::Builder::Builder(Header* header, ReadableFontData* data)
    : FontDataTable::Builder(data) {
  header_ = header;
}

Table::Builder::Builder(Header* header) {
  header_ = header;
}

}  // namespace sfntly
