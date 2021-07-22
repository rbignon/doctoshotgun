# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Christophe Benz
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

import logging
import time

__all__ = ['retry']


def retry(exceptions_to_check, exc_handler=None, tries=3, delay=2, backoff=2):
    """
    Retry decorator
    from http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from http://wiki.python.org/moin/PythonDecoratorLibrary#Retry
    """
    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries = kwargs.pop('_tries', tries)
            mdelay = kwargs.pop('_delay', delay)
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except exceptions_to_check as exc:
                    if exc_handler:
                        exc_handler(exc, **kwargs)
                    try:
                        logging.debug(u'%s, Retrying in %d seconds...' % (exc, mdelay))
                    except UnicodeDecodeError:
                        logging.debug(u'%s, Retrying in %d seconds...' % (repr(exc), mdelay))
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)
        return f_retry  # true decorator
    return deco_retry

