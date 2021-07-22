# -*- coding: utf-8 -*-

# Copyright(C) 2019 Laurent Bachelier
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


import os
from datetime import datetime
from woob.tools.log import getLogger

__all__ = ['LOGGER', 'replace', 'time_buffer']


LOGGER = getLogger('woob.config')


try:
    from os import replace
except ImportError:
    def replace(src, dst, *args, **kwargs):
        if os.name != 'posix':
            try:
                os.remove(dst)
            except OSError:
                pass
        return os.rename(src, dst, *args, **kwargs)


def time_buffer(since_seconds=None, last_run=True, logger=False):
    def decorator_time_buffer(func):
        def wrapper_time_buffer(*args, **kwargs):
            since_seconds = kwargs.pop('since_seconds', None)
            if since_seconds is None:
                since_seconds = decorator_time_buffer.since_seconds
            if logger:
                logger.debug('Time buffer for %r of %s. Last run %s.'
                             % (func, since_seconds, decorator_time_buffer.last_run))
            if since_seconds and decorator_time_buffer.last_run:
                if (datetime.now() - decorator_time_buffer.last_run).seconds < since_seconds:
                    if logger:
                        logger.debug('Too soon to run %r, ignore.' % func)
                    return
            if logger:
                logger.debug('Run %r and record' % func)
            res = func(*args, **kwargs)
            decorator_time_buffer.last_run = datetime.now()
            return res

        decorator_time_buffer.since_seconds = since_seconds
        decorator_time_buffer.last_run = datetime.now() if last_run is True else last_run

        return wrapper_time_buffer
    return decorator_time_buffer
