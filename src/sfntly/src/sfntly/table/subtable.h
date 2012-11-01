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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_SUBTABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_SUBTABLE_H_

#include "sfntly/table/font_data_table.h"

namespace sfntly {

// An abstract base class for subtables. Subtables are smaller tables nested
// within other tables and don't have an entry in the main font index. Examples
// of these are the CMap subtables within CMap table (cmap) or a glyph within
// the glyph table (glyf).
class SubTable : public FontDataTable {
 public:
  class Builder : public FontDataTable::Builder {
   public:
    virtual ~Builder();

   protected:
    // @param data the data for the subtable being built
    // @param master_data the data for the full table
    Builder(int32_t data_size);
    Builder(WritableFontData* data, ReadableFontData* master_data);
    Builder(ReadableFontData* data, ReadableFontData* master_data);
    explicit Builder(WritableFontData* data);
    explicit Builder(ReadableFontData* data);

    ReadableFontData* master_read_data() { return master_data_; }

   private:
    ReadableFontDataPtr master_data_;
  };

  virtual ~SubTable();
  virtual int32_t Padding() { return padding_; }

  // Sets the amount of padding that is part of the data being used by this
  // subtable.
  void set_padding(int32_t padding) { padding_ = padding; }

 protected:
  SubTable(ReadableFontData* data, ReadableFontData* master_data);

  // Note: constructor refactored in C++ to avoid heavy lifting.
  //       caller need to do data->Slice(offset, length) beforehand.
  explicit SubTable(ReadableFontData* data);

  ReadableFontData* master_read_data() { return master_data_; }

 private:
  // The data for the whole table in which this subtable is contained.
  ReadableFontDataPtr master_data_;
  int32_t padding_;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_SUBTABLE_H_
