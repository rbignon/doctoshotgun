# -*- coding: utf-8 -*-

# Copyright(C) 2014 Laurent Bachelier
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

import datetime

from dateutil.relativedelta import relativedelta
from requests.exceptions import HTTPError
from woob.exceptions import (
    BrowserHTTPError, BrowserHTTPNotFound, BrowserUnavailable,
)


class HTTPNotFound(HTTPError, BrowserHTTPNotFound):
    pass


class ClientError(HTTPError, BrowserHTTPError):
    pass


class ServerError(HTTPError, BrowserHTTPError):
    pass


class LoggedOut(Exception):
    pass


class BrowserTooManyRequests(BrowserUnavailable):
    """
    Client tries to perform too many requests within a certain timeframe.
    The module should set the next_try if possible, else it is set to 24h.
    """

    def __init__(self, message='', next_try=None):
        super(BrowserTooManyRequests, self).__init__(message)

        if isinstance(next_try, datetime.date) and not isinstance(next_try, datetime.datetime):
            next_try = datetime.datetime.combine(next_try, datetime.datetime.min.time())

        if next_try is None:
            next_try = datetime.datetime.now() + relativedelta(days=1)

        if not isinstance(next_try, datetime.datetime):
            raise TypeError('next_try value should be a datetime.')

        self.next_try = next_try

    def __str__(self):
        return super(BrowserTooManyRequests, self).__str__() or 'Too many requests, next_try set %s' % self.next_try
