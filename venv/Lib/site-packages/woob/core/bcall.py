# -*- coding: utf-8 -*-

# Copyright(C) 2010-2014 Romain Bignon, Christophe Benz
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.


from copy import copy
from threading import Thread, Event
try:
    import Queue
except ImportError:
    import queue as Queue

from woob.capabilities.base import BaseObject
from woob.tools.compat import basestring
from woob.tools.misc import get_backtrace
from woob.tools.log import getLogger


__all__ = ['BackendsCall', 'CallErrors']


class CallErrors(Exception):
    def __init__(self, errors):
        msg = 'Errors during backend calls:\n' + \
                '\n'.join(['Module(%r): %r\n%r\n' % (backend, error, backtrace)
                           for backend, error, backtrace in errors])

        super(CallErrors, self).__init__(msg)
        self.errors = copy(errors)

    def __iter__(self):
        return self.errors.__iter__()


class BackendsCall(object):
    def __init__(self, backends, function, *args, **kwargs):
        """
        :param backends: List of backends to call
        :type backends: list[:class:`Module`]
        :param function: backends' method name, or callable object.
        :type function: :class:`str` or :class:`callable`
        """
        self.logger = getLogger('bcall')

        self.responses = Queue.Queue()
        self.errors = []
        self.tasks = Queue.Queue()
        self.stop_event = Event()
        self.threads = []

        for backend in backends:
            t = Thread(target=self.backend_process, args=(function, args, kwargs))
            t.start()
            self.threads.append(t)
            self.tasks.put(backend)

    def store_result(self, backend, result):
        """Store the result when a backend task finished."""
        if result is None:
            return

        if isinstance(result, BaseObject):
            result.backend = backend.name
        self.responses.put(result)

    def backend_process(self, function, args, kwargs):
        """
        Internal method to run a method of a backend.

        As this method may be blocking, it should be run on its own thread.
        """
        backend = self.tasks.get()
        with backend:
            try:
                # Call method on backend
                try:
                    self.logger.debug('%s: Calling function %s', backend, function)
                    if callable(function):
                        result = function(backend, *args, **kwargs)
                    else:
                        result = getattr(backend, function)(*args, **kwargs)
                except Exception as error:
                    self.logger.debug('%s: Called function %s raised an error: %r', backend, function, error)
                    self.errors.append((backend, error, get_backtrace(error)))
                else:
                    self.logger.debug('%s: Called function %s returned: %r', backend, function, result)

                    if hasattr(result, '__iter__') and not isinstance(result, (bytes, basestring)):
                        # Loop on iterator
                        try:
                            for subresult in result:
                                self.store_result(backend, subresult)
                                if self.stop_event.is_set():
                                    break
                        except Exception as error:
                            self.errors.append((backend, error, get_backtrace(error)))
                    else:
                        self.store_result(backend, result)
            finally:
                self.tasks.task_done()

    def _callback_thread_run(self, callback, errback, finishback):
        while not self.stop_event.is_set() and (self.tasks.unfinished_tasks or not self.responses.empty()):
            try:
                response = self.responses.get(timeout=0.1)
            except Queue.Empty:
                continue
            else:
                if callback:
                    callback(response)

        # Raise errors
        while errback and self.errors:
            errback(*self.errors.pop(0))

        if finishback:
            finishback()

    def callback_thread(self, callback, errback=None, finishback=None):
        """
        Call this method to create a thread which will callback a
        specified function everytimes a new result comes.

        When the process is over, the function will be called with
        both arguments set to None.

        The functions prototypes:
            def callback(result)
            def errback(backend, error, backtrace)
            def finishback()

        """
        thread = Thread(target=self._callback_thread_run, args=(callback, errback, finishback))
        thread.start()
        return thread

    def wait(self):
        """Wait until all tasks are finished."""
        for thread in self.threads:
            thread.join()

        if self.errors:
            raise CallErrors(self.errors)

    def stop(self, wait=False):
        """
        Stop all tasks.

        :param wait: If True, wait until all tasks stopped.
        :type wait: bool
        """

        self.stop_event.set()

        if wait:
            self.wait()

    def __iter__(self):
        try:
            while not self.stop_event.is_set() and (self.tasks.unfinished_tasks or not self.responses.empty()):
                try:
                    yield self.responses.get(timeout=0.1)
                except Queue.Empty:
                    continue
        except:
            self.stop()
            raise

        if self.errors:
            raise CallErrors(self.errors)
