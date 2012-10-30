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

#include "sfntly/table/generic_table_builder.h"

namespace sfntly {

GenericTableBuilder::~GenericTableBuilder() {}

CALLER_ATTACH
FontDataTable* GenericTableBuilder::SubBuildTable(ReadableFontData* data) {
  // Note: In C++ port, we use GenericTable, the ref-counted version of Table
  UNREFERENCED_PARAMETER(data);
  Ptr<GenericTable> table = new GenericTable(header(), InternalReadData());
  return table.Detach();
}

// static
CALLER_ATTACH GenericTableBuilder*
    GenericTableBuilder::CreateBuilder(Header* header, WritableFontData* data) {
  Ptr<GenericTableBuilder> builder =
      new GenericTableBuilder(header, data);
  return builder.Detach();
}

GenericTableBuilder::GenericTableBuilder(Header* header,
                                         WritableFontData* data)
    : TableBasedTableBuilder(header, data) {
}

GenericTableBuilder::GenericTableBuilder(Header* header,
                                         ReadableFontData* data)
    : TableBasedTableBuilder(header, data) {
}

}  // namespace sfntly
