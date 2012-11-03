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

#ifndef SFNTLY_CPP_SRC_SFNTLY_PORT_JAVA_ITERATOR_H_
#define SFNTLY_CPP_SRC_SFNTLY_PORT_JAVA_ITERATOR_H_

#include "sfntly/port/refcount.h"

// Interface of Java iterator.
// This is a forward read-only iterator that represents java.util.Iterator<E>

namespace sfntly {

template <typename ReturnType, typename ContainerBase>
class Iterator : public virtual RefCount {
 public:
  virtual ~Iterator() {}
  virtual ContainerBase* container_base() = 0;

 protected:
  Iterator() {}
  NO_COPY_AND_ASSIGN(Iterator);
};

template <typename ReturnType, typename Container,
          typename ContainerBase = Container>
class PODIterator : public Iterator<ReturnType, ContainerBase>,
                    public RefCounted< PODIterator<ReturnType, Container> > {
 public:
  explicit PODIterator(Container* container) : container_(container) {}
  virtual ~PODIterator() {}
  virtual ContainerBase* container_base() {
    return static_cast<ContainerBase*>(container_);
  }

  virtual bool HasNext() = 0;
  virtual ReturnType Next() = 0;
  virtual void Remove() {
#if !defined (SFNTLY_NO_EXCEPTION)
    // Default to no support.
    throw UnsupportedOperationException();
#endif
  }

 protected:
  Container* container() { return container_; }

 private:
  Container* container_;  // Dumb pointer is used to avoid circular ref-counting
};

template <typename ReturnType, typename Container,
          typename ContainerBase = Container>
class RefIterator : public Iterator<ReturnType, ContainerBase>,
                    public RefCounted< RefIterator<ReturnType, Container> > {
 public:
  explicit RefIterator(Container* container) : container_(container) {}
  virtual ~RefIterator() {}
  virtual ContainerBase* container_base() {
    return static_cast<ContainerBase*>(container_);
  }

  virtual bool HasNext() = 0;
  CALLER_ATTACH virtual ReturnType* Next() = 0;
  virtual void Remove() {
#if !defined (SFNTLY_NO_EXCEPTION)
    // Default to no support.
    throw UnsupportedOperationException();
#endif
  }

 protected:
  Container* container() { return container_; }

 private:
  Container* container_;  // Dumb pointer is used to avoid circular ref-counting
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_PORT_JAVA_ITERATOR_H_
