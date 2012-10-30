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

// Exceptions used in sfntly

#ifndef SFNTLY_CPP_SRC_SFNTLY_PORT_EXCEPTION_TYPE_H_
#define SFNTLY_CPP_SRC_SFNTLY_PORT_EXCEPTION_TYPE_H_

#if !defined (SFNTLY_NO_EXCEPTION)

#include <exception>
#include <string>
#include <sstream>

namespace sfntly {

class Exception : public std::exception {
 public:
  Exception() : what_("Unknown exception") {}
  explicit Exception(const char* message) throw() { SetMessage(message); }
  virtual ~Exception() throw() {}
  virtual const char* what() const throw() { return what_.c_str(); }

 protected:
  void SetMessage(const char* message) throw() {
    try {
      what_ = message;
    } catch (...) {}
  }

 private:
  std::string what_;
};

class IndexOutOfBoundException : public Exception {
 public:
  IndexOutOfBoundException() throw() : Exception("Index out of bound") {}
  explicit IndexOutOfBoundException(const char* message) throw()
      : Exception(message) {}
  IndexOutOfBoundException(const char* message, int32_t index) throw() {
    try {
      std::ostringstream msg;
      msg << message;
      msg << ":";
      msg << index;
      SetMessage(msg.str().c_str());
    } catch (...) {}
  }
  virtual ~IndexOutOfBoundException() throw() {}
};

class IOException : public Exception {
 public:
  IOException() throw() : Exception("I/O exception") {}
  explicit IOException(const char* message) throw() : Exception(message) {}
  virtual ~IOException() throw() {}
};

class ArithmeticException : public Exception {
 public:
  ArithmeticException() throw() : Exception("Arithmetic exception") {}
  explicit ArithmeticException(const char* message) throw()
      : Exception(message) {}
  virtual ~ArithmeticException() throw() {}
};

class UnsupportedOperationException : public Exception {
 public:
  UnsupportedOperationException() throw() :
      Exception("Operation not supported") {}
  explicit UnsupportedOperationException(const char* message) throw()
      : Exception(message) {}
  virtual ~UnsupportedOperationException() throw() {}
};

class RuntimeException : public Exception {
 public:
  RuntimeException() throw() : Exception("Runtime exception") {}
  explicit RuntimeException(const char* message) throw()
      : Exception(message) {}
  virtual ~RuntimeException() throw() {}
};

class NoSuchElementException : public Exception {
 public:
  NoSuchElementException() throw() : Exception("No such element") {}
  explicit NoSuchElementException(const char* message) throw()
      : Exception(message) {}
  virtual ~NoSuchElementException() throw() {}
};

class IllegalArgumentException : public Exception {
 public:
  IllegalArgumentException() throw() : Exception("Illegal argument") {}
  explicit IllegalArgumentException(const char* message) throw()
      : Exception(message) {}
  virtual ~IllegalArgumentException() throw() {}
};

class IllegalStateException : public Exception {
 public:
  IllegalStateException() throw() : Exception("Illegal state") {}
  explicit IllegalStateException(const char* message) throw()
      : Exception(message) {}
  virtual ~IllegalStateException() throw() {}
};

}  // namespace sfntly

#endif  // #if !defined (SFNTLY_NO_EXCEPTION)

#endif  // SFNTLY_CPP_SRC_SFNTLY_PORT_EXCEPTION_TYPE_H_
