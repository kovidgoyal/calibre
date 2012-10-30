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

#ifndef SFNTLY_CPP_SRC_SFNTLY_PORT_ATOMIC_H_
#define SFNTLY_CPP_SRC_SFNTLY_PORT_ATOMIC_H_

#if defined (WIN32)

#include <windows.h>

static inline size_t AtomicIncrement(size_t* address) {
#if defined (_WIN64)
  return InterlockedIncrement64(reinterpret_cast<LONGLONG*>(address));
#else
  return InterlockedIncrement(reinterpret_cast<LONG*>(address));
#endif
}

static inline size_t AtomicDecrement(size_t* address) {
#if defined (_WIN64)
  return InterlockedDecrement64(reinterpret_cast<LONGLONG*>(address));
#else
  return InterlockedDecrement(reinterpret_cast<LONG*>(address));
#endif
}

#elif defined (__APPLE__)

#include <libkern/OSAtomic.h>

static inline size_t AtomicIncrement(size_t* address) {
  return OSAtomicIncrement32Barrier(reinterpret_cast<int32_t*>(address));
}

static inline size_t AtomicDecrement(size_t* address) {
  return OSAtomicDecrement32Barrier(reinterpret_cast<int32_t*>(address));
}

// Originally we check __GCC_HAVE_SYNC_COMPARE_AND_SWAP_4, however, there are
// issues that clang not carring over this definition.  Therefore we boldly
// assume it's gcc or gcc-compatible here.  Compilation shall still fail since
// the intrinsics used are GCC-specific.

#else

#include <stddef.h>

static inline size_t AtomicIncrement(size_t* address) {
  return __sync_add_and_fetch(address, 1);
}

static inline size_t AtomicDecrement(size_t* address) {
  return __sync_sub_and_fetch(address, 1);
}

#endif  // WIN32

#endif  // SFNTLY_CPP_SRC_SFNTLY_PORT_ATOMIC_H_
