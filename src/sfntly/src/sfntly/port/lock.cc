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

#include "sfntly/port/lock.h"

namespace sfntly {

#if defined (WIN32)

Lock::Lock() {
  // The second parameter is the spin count, for short-held locks it avoid the
  // contending thread from going to sleep which helps performance greatly.
  ::InitializeCriticalSectionAndSpinCount(&os_lock_, 2000);
}

Lock::~Lock() {
  ::DeleteCriticalSection(&os_lock_);
}

bool Lock::Try() {
  if (::TryEnterCriticalSection(&os_lock_) != FALSE) {
    return true;
  }
  return false;
}

void Lock::Acquire() {
  ::EnterCriticalSection(&os_lock_);
}

void Lock::Unlock() {
  ::LeaveCriticalSection(&os_lock_);
}

#else  // We assume it's pthread

Lock::Lock() {
  pthread_mutex_init(&os_lock_, NULL);
}

Lock::~Lock() {
  pthread_mutex_destroy(&os_lock_);
}

bool Lock::Try() {
  return (pthread_mutex_trylock(&os_lock_) == 0);
}

void Lock::Acquire() {
  pthread_mutex_lock(&os_lock_);
}

void Lock::Unlock() {
  pthread_mutex_unlock(&os_lock_);
}

#endif

}  // namespace sfntly
