"""Easy to use object-oriented thread pool framework.

A thread pool is an object that maintains a pool of worker threads to perform
time consuming operations in parallel. It assigns jobs to the threads
by putting them in a work request queue, where they are picked up by the
next available thread. This then performs the requested operation in the
background and puts the results in a another queue.

The thread pool object can then collect the results from all threads from
this queue as soon as they become available or after all threads have
finished their work. It's also possible, to define callbacks to handle
each result as it comes in.

The basic concept and some code was taken from the book "Python in a Nutshell"
by Alex Martelli, copyright 2003, ISBN 0-596-00188-6, from section 14.5
"Threaded Program Architecture". I wrapped the main program logic in the
ThreadPool class, added the WorkRequest class and the callback system and
tweaked the code here and there. Kudos also to Florent Aide for the exception
handling mechanism.

Basic usage:

>>> pool = TreadPool(poolsize)
>>> requests = makeRequests(some_callable, list_of_args, callback)
>>> [pool.putRequest(req) for req in requests]
>>> pool.wait()

See the end of the module code for a brief, annotated usage example.

Website : http://chrisarndt.de/en/software/python/threadpool/
"""

__all__ = [
  'makeRequests',
  'NoResultsPending',
  'NoWorkersAvailable',
  'ThreadPool',
  'WorkRequest',
  'WorkerThread'
]

__author__ = "Christopher Arndt"
__version__ = "1.2.3"
__revision__ = "$Revision: 1.5 $"
__date__ = "$Date: 2006/06/23 12:32:25 $"
__license__ = 'Python license'

# standard library modules
import threading
from polyglot import queue

# exceptions


class NoResultsPending(Exception):
    """All work requests have been processed."""
    pass


class NoWorkersAvailable(Exception):
    """No worker threads available to process remaining requests."""
    pass

# classes


class WorkerThread(threading.Thread):
    """Background thread connected to the requests/results queues.

    A worker thread sits in the background and picks up work requests from
    one queue and puts the results in another until it is dismissed.
    """

    def __init__(self, requestsQueue, resultsQueue, **kwds):
        """Set up thread in daemonic mode and start it immediatedly.

        requestsQueue and resultQueue are instances of queue.Queue passed
        by the ThreadPool class when it creates a new worker thread.
        """
        kwds['daemon'] = True
        threading.Thread.__init__(self, **kwds)
        self.workRequestQueue = requestsQueue
        self.resultQueue = resultsQueue
        self._dismissed = threading.Event()
        self.start()

    def run(self):
        """Repeatedly process the job queue until told to exit."""

        while not self._dismissed.isSet():
            # thread blocks here, if queue empty
            request = self.workRequestQueue.get()
            if self._dismissed.isSet():
                # if told to exit, return the work request we just picked up
                self.workRequestQueue.put(request)
                break  # and exit
            try:
                self.resultQueue.put(
                    (request, request.callable(*request.args, **request.kwds))
                )
            except:
                request.exception = True
                import traceback
                self.resultQueue.put((request, traceback.format_exc()))

    def dismiss(self):
        """Sets a flag to tell the thread to exit when done with current job.
        """

        self._dismissed.set()


class WorkRequest:
    """A request to execute a callable for putting in the request queue later.

    See the module function makeRequests() for the common case
    where you want to build several WorkRequests for the same callable
    but with different arguments for each call.
    """

    def __init__(self, callable, args=None, kwds=None, requestID=None,
      callback=None, exc_callback=None):
        """Create a work request for a callable and attach callbacks.

        A work request consists of the callable to be executed by a
        worker thread, a list of positional arguments, a dictionary
        of keyword arguments.

        A callback function can be specified, that is called when the results
        of the request are picked up from the result queue. It must accept
        two arguments, the request object and the results of the callable,
        in that order. If you want to pass additional information to the
        callback, just stick it on the request object.

        You can also give a callback for when an exception occurs. It should
        also accept two arguments, the work request and a tuple with the
        exception details as returned by sys.exc_info().

        requestID, if given, must be hashable since it is used by the
        ThreadPool object to store the results of that work request in a
        dictionary. It defaults to the return value of id(self).
        """

        if requestID is None:
            self.requestID = id(self)
        else:
            try:
                hash(requestID)
            except TypeError:
                raise TypeError("requestID must be hashable.")
            self.requestID = requestID
        self.exception = False
        self.callback = callback
        self.exc_callback = exc_callback
        self.callable = callable
        self.args = args or []
        self.kwds = kwds or {}


class ThreadPool:
    """A thread pool, distributing work requests and collecting results.

    See the module doctring for more information.
    """

    def __init__(self, num_workers, q_size=0):
        """Set up the thread pool and start num_workers worker threads.

        num_workers is the number of worker threads to start initially.
        If q_size > 0 the size of the work request queue is limited and
        the thread pool blocks when the queue is full and it tries to put
        more work requests in it (see putRequest method).
        """

        self.requestsQueue = queue.Queue(q_size)
        self.resultsQueue = queue.Queue()
        self.workers = []
        self.workRequests = {}
        self.createWorkers(num_workers)

    def createWorkers(self, num_workers):
        """Add num_workers worker threads to the pool."""

        for i in range(num_workers):
            self.workers.append(WorkerThread(self.requestsQueue,
              self.resultsQueue))

    def dismissWorkers(self, num_workers):
        """Tell num_workers worker threads to quit after their current task.
        """

        for i in range(min(num_workers, len(self.workers))):
            worker = self.workers.pop()
            worker.dismiss()

    def putRequest(self, request, block=True, timeout=0):
        """Put work request into work queue and save its id for later."""

        assert isinstance(request, WorkRequest)
        self.requestsQueue.put(request, block, timeout)
        self.workRequests[request.requestID] = request

    def poll(self, block=False):
        """Process any new results in the queue."""

        while True:
            # still results pending?
            if not self.workRequests:
                raise NoResultsPending
            # are there still workers to process remaining requests?
            elif block and not self.workers:
                raise NoWorkersAvailable
            try:
                # get back next results
                request, result = self.resultsQueue.get(block=block)
                # has an exception occurred?
                if request.exception and request.exc_callback:
                    request.exc_callback(request, result)
                # hand results to callback, if any
                if request.callback and not \
                  (request.exception and request.exc_callback):
                    request.callback(request, result)
                del self.workRequests[request.requestID]
            except queue.Empty:
                break

    def wait(self, sleep=0):
        """Wait for results, blocking until all have arrived."""

        while 1:
            try:
                self.poll(True)
                time.sleep(sleep)
            except NoResultsPending:
                break

# helper functions


def makeRequests(callable, args_list, callback=None, exc_callback=None):
    """Create several work requests for same callable with different arguments.

    Convenience function for creating several work requests for the same
    callable where each invocation of the callable receives different values
    for its arguments.

    args_list contains the parameters for each invocation of callable.
    Each item in 'args_list' should be either a 2-item tuple of the list of
    positional arguments and a dictionary of keyword arguments or a single,
    non-tuple argument.

    See docstring for WorkRequest for info on callback and exc_callback.
    """

    requests = []
    for item in args_list:
        if isinstance(item, tuple):
            requests.append(
              WorkRequest(callable, item[0], item[1], callback=callback,
                exc_callback=exc_callback)
            )
        else:
            requests.append(
              WorkRequest(callable, [item], None, callback=callback,
                exc_callback=exc_callback)
            )
    return requests

################
# USAGE EXAMPLE
################


if __name__ == '__main__':
    import random
    import time

    # the work the threads will have to do (rather trivial in our example)
    def do_something(data):
        time.sleep(random.randint(1,5))
        result = round(random.random() * data, 5)
        # just to show off, we throw an exception once in a while
        if result > 3:
            raise RuntimeError("Something extraordinary happened!")
        return result

    # this will be called each time a result is available
    def print_result(request, result):
        print(f"**Result: {result} from request #{request.requestID}")

    # this will be called when an exception occurs within a thread
    def handle_exception(request, exc_info):
        print("Exception occurred in request #%s: %s" %
          (request.requestID, exc_info[1]))

    # assemble the arguments for each job to a list...
    data = [random.randint(1,10) for i in range(20)]
    # ... and build a WorkRequest object for each item in data
    requests = makeRequests(do_something, data, print_result, handle_exception)

    # or the other form of args_lists accepted by makeRequests: ((,), {})
    data = [((random.randint(1,10),), {}) for i in range(20)]
    requests.extend(
      makeRequests(do_something, data, print_result, handle_exception)
    )

    # we create a pool of 3 worker threads
    main = ThreadPool(3)

    # then we put the work requests in the queue...
    for req in requests:
        main.putRequest(req)
        print("Work request #%s added." % req.requestID)
    # or shorter:
    # [main.putRequest(req) for req in requests]

    # ...and wait for the results to arrive in the result queue
    # by using ThreadPool.wait(). This would block until results for
    # all work requests have arrived:
    # main.wait()

    # instead we can poll for results while doing something else:
    i = 0
    while 1:
        try:
            main.poll()
            print("Main thread working...")
            time.sleep(0.5)
            if i == 10:
                print("Adding 3 more worker threads...")
                main.createWorkers(3)
            i += 1
        except KeyboardInterrupt:
            print("Interrupted!")
            break
        except NoResultsPending:
            print("All results collected.")
            break
