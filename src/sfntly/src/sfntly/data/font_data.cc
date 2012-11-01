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

#include <limits.h>
#include <algorithm>
#include <functional>

#include "sfntly/data/font_data.h"

namespace sfntly {

int32_t FontData::Size() const {
  return std::min<int32_t>(array_->Size() - bound_offset_, bound_length_);
}

bool FontData::Bound(int32_t offset, int32_t length) {
  if (offset + length > Size() || offset < 0 || length < 0)
    return false;

  bound_offset_ += offset;
  bound_length_ = length;
  return true;
}

bool FontData::Bound(int32_t offset) {
if (offset > Size() || offset < 0)
    return false;

  bound_offset_ += offset;
  return true;
}

int32_t FontData::Length() const {
  return std::min<int32_t>(array_->Length() - bound_offset_, bound_length_);
}

FontData::FontData(ByteArray* ba) {
  Init(ba);
}

FontData::FontData(FontData* data, int32_t offset, int32_t length) {
  Init(data->array_);
  Bound(data->bound_offset_ + offset, length);
}

FontData::FontData(FontData* data, int32_t offset) {
  Init(data->array_);
  Bound(data->bound_offset_ + offset,
        (data->bound_length_ == GROWABLE_SIZE)
            ? GROWABLE_SIZE : data->bound_length_ - offset);
}

FontData::~FontData() {}

void FontData::Init(ByteArray* ba) {
  array_ = ba;
  bound_offset_ = 0;
  bound_length_ = GROWABLE_SIZE;
}

int32_t FontData::BoundOffset(int32_t offset) {
  return offset + bound_offset_;
}

int32_t FontData::BoundLength(int32_t offset, int32_t length) {
  return std::min<int32_t>(length, bound_length_ - offset);
}

}  // namespace sfntly
