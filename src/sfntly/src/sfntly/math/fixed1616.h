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

#ifndef SFNTLY_CPP_SRC_SFNTLY_MATH_FIXED1616_H_
#define SFNTLY_CPP_SRC_SFNTLY_MATH_FIXED1616_H_

#include "sfntly/port/type.h"

namespace sfntly {

class Fixed1616 {
 public:
  static inline int32_t Integral(int32_t fixed) {
    return (fixed >> 16);
  }

  static inline int32_t Fractional(int32_t fixed) {
    return (fixed & 0xffff);
  }

  static inline int32_t Fixed(int32_t integral, int32_t fractional) {
    return ((integral & 0xffff) << 16) | (fractional & 0xffff);
  }
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_MATH_FIXED1616_H_
