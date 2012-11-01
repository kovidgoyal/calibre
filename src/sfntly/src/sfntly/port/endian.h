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

#ifndef SFNTLY_CPP_SRC_SFNTLY_PORT_ENDIAN_H_
#define SFNTLY_CPP_SRC_SFNTLY_PORT_ENDIAN_H_

#include "sfntly/port/config.h"
#include "sfntly/port/type.h"

namespace sfntly {

static inline uint16_t EndianSwap16(uint16_t value) {
  return (uint16_t)((value >> 8) | (value << 8));
}

static inline int32_t EndianSwap32(int32_t value) {
  return (((value & 0x000000ff) << 24) |
          ((value & 0x0000ff00) <<  8) |
          ((value & 0x00ff0000) >>  8) |
          ((value & 0xff000000) >> 24));
}

static inline uint64_t EndianSwap64(uint64_t value) {
  return (((value & 0x00000000000000ffLL) << 56) |
          ((value & 0x000000000000ff00LL) << 40) |
          ((value & 0x0000000000ff0000LL) << 24) |
          ((value & 0x00000000ff000000LL) << 8)  |
          ((value & 0x000000ff00000000LL) >> 8)  |
          ((value & 0x0000ff0000000000LL) >> 24) |
          ((value & 0x00ff000000000000LL) >> 40) |
          ((value & 0xff00000000000000LL) >> 56));
}

#ifdef SFNTLY_LITTLE_ENDIAN
  #define ToBE16(n) EndianSwap16(n)
  #define ToBE32(n) EndianSwap32(n)
  #define ToBE64(n) EndianSwap64(n)
  #define ToLE16(n) (n)
  #define ToLE32(n) (n)
  #define ToLE64(n) (n)
  #define FromBE16(n) EndianSwap16(n)
  #define FromBE32(n) EndianSwap32(n)
  #define FromBE64(n) EndianSwap64(n)
  #define FromLE16(n) (n)
  #define FromLE32(n) (n)
  #define FromLE64(n) (n)
#else  // SFNTLY_BIG_ENDIAN
  #define ToBE16(n) (n)
  #define ToBE32(n) (n)
  #define ToBE64(n) (n)
  #define ToLE16(n) EndianSwap16(n)
  #define ToLE32(n) EndianSwap32(n)
  #define ToLE64(n) EndianSwap64(n)
  #define FromBE16(n) (n)
  #define FromBE32(n) (n)
  #define FromBE64(n) (n)
  #define FromLE16(n) EndianSwap16(n)
  #define FromLE32(n) EndianSwap32(n)
  #define FromLE64(n) EndianSwap64(n)
#endif

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_PORT_ENDIAN_H_
