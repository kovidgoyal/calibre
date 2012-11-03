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

#ifndef SFNTLY_CPP_SRC_SFNTLY_PORT_LOCK_H_
#define SFNTLY_CPP_SRC_SFNTLY_PORT_LOCK_H_

#if defined (WIN32)
#include <windows.h>
#else  // Assume pthread.
#include <pthread.h>
#include <errno.h>
#endif

#include "sfntly/port/type.h"

namespace sfntly {

#if defined (WIN32)
  typedef CRITICAL_SECTION OSLockType;
#else  // Assume pthread.
  typedef pthread_mutex_t OSLockType;
#endif

class Lock {
 public:
  Lock();
  ~Lock();

  // If the lock is not held, take it and return true.  If the lock is already
  // held by something else, immediately return false.
  bool Try();

  // Take the lock, blocking until it is available if necessary.
  void Acquire();

  // Release the lock.  This must only be called by the lock's holder: after
  // a successful call to Try, or a call to Lock.
  void Unlock();

 private:
  OSLockType os_lock_;
  NO_COPY_AND_ASSIGN(Lock);
};

// A helper class that acquires the given Lock while the AutoLock is in scope.
class AutoLock {
 public:
  explicit AutoLock(Lock& lock) : lock_(lock) {
    lock_.Acquire();
  }

  ~AutoLock() {
    lock_.Unlock();
  }

 private:
  Lock& lock_;
  NO_COPY_AND_ASSIGN(AutoLock);
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_PORT_LOCK_H_
