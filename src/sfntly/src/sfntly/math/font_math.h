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

#ifndef SFNTLY_CPP_SRC_SFNTLY_MATH_FONT_MATH_H_
#define SFNTLY_CPP_SRC_SFNTLY_MATH_FONT_MATH_H_

#include "sfntly/port/type.h"

namespace sfntly {

class FontMath {
 public:
  static int32_t Log2(int32_t a) {
    int r = 0;  // r will be lg(a)
    while (a != 0) {
      a >>= 1;
      r++;
    }
    return r - 1;
  }

  // Calculates the amount of padding needed. The values provided need to be in
  // the same units. So, if the size is given as the number of bytes then the
  // alignment size must also be specified as byte size to align to.
  // @param size the size of the data that may need padding
  // @param alignmentSize the number of units to align to
  // @return the number of units needing to be added for alignment
  static int32_t PaddingRequired(int32_t size, int32_t alignment_size) {
    int32_t padding = alignment_size - (size % alignment_size);
    return padding == alignment_size ? 0 : padding;
  }
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_MATH_FONT_MATH_H_
