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

#ifndef TYPOGRAPHY_FONT_SFNTLY_SRC_SFNTLY_TABLE_SUBTABLE_CONTAINER_TABLE_H_
#define TYPOGRAPHY_FONT_SFNTLY_SRC_SFNTLY_TABLE_SUBTABLE_CONTAINER_TABLE_H_

#include "sfntly/table/table.h"

namespace sfntly {

class SubTableContainerTable : public Table {
 public:
  class Builder : public Table::Builder {
   public:
    Builder(Header* header, WritableFontData* data)
        : Table::Builder(header, data) {
    }

    Builder(Header* header, ReadableFontData* data)
        : Table::Builder(header, data) {
    }

    virtual ~Builder() {}
  };

  SubTableContainerTable(Header* header, ReadableFontData* data)
      : Table(header, data) {
  }

  virtual ~SubTableContainerTable() {}
};

}  // namespace sfntly

#endif  // TYPOGRAPHY_FONT_SFNTLY_SRC_SFNTLY_TABLE_SUBTABLE_CONTAINER_TABLE_H_
