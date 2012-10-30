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

#include "sfntly/table/byte_array_table_builder.h"

namespace sfntly {

ByteArrayTableBuilder::~ByteArrayTableBuilder() {}

int32_t ByteArrayTableBuilder::ByteValue(int32_t index) {
  ReadableFontDataPtr data = InternalReadData();
  if (data == NULL) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IOException("No font data for the table");
#endif
    return -1;
  }
  return data->ReadByte(index);
}

void ByteArrayTableBuilder::SetByteValue(int32_t index, byte_t b) {
  WritableFontDataPtr data = InternalWriteData();
  if (data == NULL) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IOException("No font data for the table");
#endif
    return;
  }
  data->WriteByte(index, b);
}

int32_t ByteArrayTableBuilder::ByteCount() {
  ReadableFontDataPtr data = InternalReadData();
  if (data == NULL) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IOException("No font data for the table");
#endif
    return 0;
  }
  return data->Length();
}

ByteArrayTableBuilder::ByteArrayTableBuilder(Header* header,
                                               WritableFontData* data)
    : TableBasedTableBuilder(header, data) {
}

ByteArrayTableBuilder::ByteArrayTableBuilder(Header* header,
                                               ReadableFontData* data)
    : TableBasedTableBuilder(header, data) {
}

ByteArrayTableBuilder::ByteArrayTableBuilder(Header* header)
    : TableBasedTableBuilder(header) {
}

}  // namespace sfntly
