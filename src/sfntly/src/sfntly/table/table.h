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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_TABLE_H_

#include <set>
#include <map>
#include <vector>
#include <utility>

#include "sfntly/port/type.h"
#include "sfntly/table/font_data_table.h"
#include "sfntly/table/header.h"

namespace sfntly {
class Font;

// A concrete implementation of a root level table in the font. This is the base
// class used for all specific table implementations and is used as the generic
// table for all tables which have no specific implementations.
class Table : public FontDataTable {
 public:
  // Note: original version is Builder<T extends Table>
  //       C++ template is not designed that way so plain old inheritance is
  //       chosen.
  class Builder : public FontDataTable::Builder {
   public:
    virtual ~Builder();
    virtual Header* header() { return header_; }
    virtual void NotifyPostTableBuild(FontDataTable* table);

    // Get a builder for the table type specified by the data in the header.
    // @param header the header for the table
    // @param tableData the data to be used to build the table from
    // @return builder for the table specified
    static CALLER_ATTACH Builder* GetBuilder(Header* header,
                                             WritableFontData* table_data);

    // UNIMPLEMENTED: toString()

   protected:
    Builder(Header* header, WritableFontData* data);
    Builder(Header* header, ReadableFontData* data);
    Builder(Header* header);

   private:
    Ptr<Header> header_;
  };

  // Note: GenericTableBuilder moved to table_based_table_builder.h to avoid
  //       circular inclusion.

  virtual ~Table();

  // Get the calculated checksum for the data in the table.
  virtual int64_t CalculatedChecksum();

  // Get the header for the table.
  virtual Header* header()          { return header_; }

  // Get the tag for the table from the record header.
  virtual int32_t header_tag()      { return header_->tag(); }

  // Get the offset for the table from the record header.
  virtual int32_t header_offset()   { return header_->offset(); }

  // Get the length of the table from the record header.
  virtual int32_t header_length()   { return header_->length(); }

  // Get the checksum for the table from the record header.
  virtual int64_t header_checksum() { return header_->checksum(); }

  // UNIMPLEMENTED: toString()

  virtual void SetFont(Font* font);

 protected:
  Table(Header* header, ReadableFontData* data);

 private:
  Ptr<Header> header_;
  Ptr<Font> font_;
};

// C++ port only
class GenericTable : public Table, public RefCounted<GenericTable> {
 public:
  GenericTable(Header* header, ReadableFontData* data) : Table(header, data) {}
  virtual ~GenericTable() {}
};

typedef Ptr<Table> TablePtr;
typedef std::vector<HeaderPtr> TableHeaderList;
typedef Ptr<Table::Builder> TableBuilderPtr;
typedef std::map<int32_t, TablePtr> TableMap;
typedef std::pair<int32_t, TablePtr> TableMapEntry;

typedef std::map<HeaderPtr, WritableFontDataPtr> DataBlockMap;
typedef std::pair<HeaderPtr, WritableFontDataPtr> DataBlockEntry;
typedef std::map<int32_t, TableBuilderPtr> TableBuilderMap;
typedef std::pair<int32_t, TableBuilderPtr> TableBuilderEntry;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_TABLE_H_
