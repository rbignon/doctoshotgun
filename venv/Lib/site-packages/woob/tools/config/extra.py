# -*- coding: utf-8 -*-

# Copyright(C) 2017-2019 Laurent Bachelier
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


import multiprocessing
import os

from .util import time_buffer


__all__ = ['AutoCleanConfig', 'ForkingConfig', 'TimeBufferConfig']


"""
These classes add functionality to existing IConfig classes.
Example:

    class MyYamlConfig(TimeBufferConfig, ForkingConfig, YamlConfig):
        saved_since_seconds = 42

The recommended order is TimeBufferConfig, AutoCleanConfig, ForkingConfig, and then the
actual storage class.
"""


class AutoCleanConfig(object):
    """
    Removes config file if it has no values.
    """
    def save(self):
        if self.values:
            super(AutoCleanConfig, self).save()
        else:
            try:
                os.remove(self.path)
            except OSError:
                pass


class ForkingConfig(object):
    """
    Runs the actual save in a forked processes, making save non-blocking.
    It prevents two save() from being called at once by blocking on the previous one
    if it is not finished.
    It is also possible to call join() to wait for the save to complete.
    """
    process = None

    def __init__(self, *args, **kwargs):
        self.lock = multiprocessing.RLock()
        super(ForkingConfig, self).__init__(*args, **kwargs)

    def join(self):
        with self.lock:
            if self.process:
                self.process.join()
            self.process = None

    def save(self):
        # if a save is already in progress, wait for it to finish
        self.join()

        parent_save = super(ForkingConfig, self).save
        with self.lock:
            self.process = multiprocessing.Process(target=parent_save, name=u'save %s' % self.path)
            self.process.start()

    def __exit__(self, t, v, tb):
        self.join()
        super(ForkingConfig, self).__exit__(t, v, tb)

    def __getstate__(self):
        d = self.__dict__.copy()
        d.pop('lock', None)
        return d

    def __setstate__(self, d):
        self.__init__(path=d['path'])
        for k, v in d.items():
            setattr(self, k, v)


class TimeBufferConfig(object):
    """
    Really saves only every saved_since_seconds seconds.
    It is possible to force save (e.g. at exit) with force_save().
    """
    saved_since_seconds = None

    def __init__(self, path, saved_since_seconds=None, last_run=True, logger=None, *args, **kwargs):
        super(TimeBufferConfig, self).__init__(path, *args, **kwargs)
        if saved_since_seconds:
            self.saved_since_seconds = saved_since_seconds
        if self.saved_since_seconds:
            self.save = time_buffer(since_seconds=self.saved_since_seconds, last_run=last_run, logger=logger)(self.save)

    def save(self, *args, **kwargs):
        kwargs.pop('since_seconds', None)
        super(TimeBufferConfig, self).save(*args, **kwargs)

    def force_save(self):
        self.save(since_seconds=False)

    def __exit__(self, t, v, tb):
        self.force_save()
        super(TimeBufferConfig, self).__exit__(t, v, tb)

    def __getstate__(self):
        try:
            d = super(TimeBufferConfig, self).__getstate__()
        except AttributeError:
            d = self.__dict__.copy()
        # When decorated, it is not serializable.
        # The decorator will be added again by __setstate__.
        d.pop('save', None)
        return d

    def __setstate__(self, d):
        # Add the decorator if needed
        self.__init__(path=d['path'],
                      saved_since_seconds=d.get('saved_since_seconds'))
        for k, v in d.items():
            setattr(self, k, v)
