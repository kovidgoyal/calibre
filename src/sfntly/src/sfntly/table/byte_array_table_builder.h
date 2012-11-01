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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BYTE_ARRAY_TABLE_BUILDER_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BYTE_ARRAY_TABLE_BUILDER_H_

#include "sfntly/table/table_based_table_builder.h"

namespace sfntly {

// An abstract builder base for byte array based tables.
class ByteArrayTableBuilder : public TableBasedTableBuilder {
 public:
  virtual ~ByteArrayTableBuilder();

  // Get the byte value at the specified index. The index is relative to the
  // start of the table.
  // @param index index relative to the start of the table
  // @return byte value at the given index
  virtual int32_t ByteValue(int32_t index);

  // Set the byte value at the specified index. The index is relative to the
  // start of the table.
  // @param index index relative to the start of the table
  // @param b byte value to set
  virtual void SetByteValue(int32_t index, byte_t b);

  // Get the number of bytes set for this table. It may include padding bytes at
  // the end.
  virtual int32_t ByteCount();

 protected:
  ByteArrayTableBuilder(Header* header, WritableFontData* data);
  ByteArrayTableBuilder(Header* header, ReadableFontData* data);
  explicit ByteArrayTableBuilder(Header* header);
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BYTE_ARRAY_TABLE_BUILDER_H_
