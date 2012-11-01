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

#ifndef SFNTLY_CPP_SRC_SFNTLY_PORT_TYPE_H_
#define SFNTLY_CPP_SRC_SFNTLY_PORT_TYPE_H_

#include <assert.h>

#if defined (_MSC_VER) && (_MSC_VER < 1600)
  typedef unsigned char     uint8_t;
  typedef signed char       int8_t;
  typedef unsigned __int16  uint16_t;
  typedef signed __int16    int16_t;
  typedef unsigned __int32  uint32_t;
  typedef signed __int32    int32_t;
  typedef unsigned __int64  uint64_t;
  typedef signed __int64    int64_t;
  // Definitions to avoid ICU redefinition issue
  #define U_HAVE_INT8_T 1
  #define U_HAVE_UINT8_T 1
  #define U_HAVE_INT16_T 1
  #define U_HAVE_UINT16_T 1
  #define U_HAVE_INT32_T 1
  #define U_HAVE_UINT32_T 1
  #define U_HAVE_INT64_T 1
  #define U_HAVE_UINT64_T 1
#else
  #include <stdint.h>
#endif

#include <cstddef>
#include <vector>
#include <set>

namespace sfntly {

typedef uint8_t   byte_t;
typedef uint16_t  word_t;
typedef uint32_t  dword_t;
typedef uint64_t  qword_t;

typedef std::vector<byte_t> ByteVector;
typedef std::vector<int32_t> IntegerList;
typedef std::set<int32_t> IntegerSet;

// A macro to disallow the copy constructor and operator= functions.
// This should be used in the private: declarations for a class.
#define NO_COPY_AND_ASSIGN(TypeName) \
  TypeName(const TypeName&);               \
  void operator=(const TypeName&)

}  // namespace sfntly

// Make google3 happy since it prohibits RTTI.
template<typename To, typename From>
inline To implicit_cast(From const &f) {
  return f;
}

template<typename To, typename From>     // use like this: down_cast<T*>(foo);
inline To down_cast(From* f) {                   // so we only accept pointers
  // Ensures that To is a sub-type of From *.  This test is here only
  // for compile-time type checking, and has no overhead in an
  // optimized build at run-time, as it will be optimized away
  // completely.
#if defined (_MSC_VER)
  #pragma warning(push)
  #pragma warning(disable:4127)  // disable "conditional expression is constant"
#endif
  if (false) {
    implicit_cast<From*, To>(0);
  }
#if defined (_MSC_VER)
  #pragma warning(pop)
#endif

// The following code is the only place for RTTI.  It is done so to allow
// additional type checking when SFNTLY_TYPE_VERIFICATION is defined.
#if defined (SFNTLY_TYPE_VERIFICATION)
  assert(f == NULL || dynamic_cast<To>(f) != NULL);
#endif
  return static_cast<To>(f);
}

#if !defined(WIN32)
  #define UNREFERENCED_PARAMETER(p) do { (void)p; } while (0)
#endif

#endif  // SFNTLY_CPP_SRC_SFNTLY_PORT_TYPE_H_
