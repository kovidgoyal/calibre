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

#include "sfntly/table/header.h"

namespace sfntly {

/******************************************************************************
 * Header class
 ******************************************************************************/
Header::Header(int32_t tag)
    : tag_(tag),
      offset_(0),
      offset_valid_(false),
      length_(0),
      length_valid_(false),
      checksum_(0),
      checksum_valid_(false) {
}

Header::Header(int32_t tag, int32_t length)
    : tag_(tag),
      offset_(0),
      offset_valid_(false),
      length_(length),
      length_valid_(true),
      checksum_(0),
      checksum_valid_(false) {
}

Header::Header(int32_t tag, int64_t checksum, int32_t offset, int32_t length)
    : tag_(tag),
      offset_(offset),
      offset_valid_(true),
      length_(length),
      length_valid_(true),
      checksum_(checksum),
      checksum_valid_(true) {
}

Header::~Header() {}

bool HeaderComparatorByOffset::operator() (const HeaderPtr lhs,
                                           const HeaderPtr rhs) {
  return lhs->offset_ > rhs->offset_;
}

bool HeaderComparatorByTag::operator() (const HeaderPtr lhs,
                                        const HeaderPtr rhs) {
  return lhs->tag_ > rhs->tag_;
}

}  // namespace sfntly
