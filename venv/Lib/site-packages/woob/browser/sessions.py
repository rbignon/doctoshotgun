# -*- coding: utf-8 -*-
#
# Copyright(C) 2014 Simon Murail
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

# Inspired by: https://github.com/ross/requests-futures/blob/master/requests_futures/sessions.py
# XXX Licence issues?

try:
    from concurrent.futures import ThreadPoolExecutor
except ImportError:
    ThreadPoolExecutor = None

from requests import Session
from requests.adapters import DEFAULT_POOLSIZE
from requests.compat import OrderedDict, cookielib
from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.models import PreparedRequest
from requests.sessions import merge_setting
from requests.structures import CaseInsensitiveDict
from requests.utils import get_netrc_auth

from .adapters import HTTPAdapter


def merge_hooks(request_hooks, session_hooks, dict_class=OrderedDict):
    """
    Properly merges both requests and session hooks.

    This is necessary because when request_hooks == {'response': []}, the
    merge breaks Session hooks entirely.

    Backport from request so we can use it in wheezy
    """
    if session_hooks is None or session_hooks.get('response') == []:
        return request_hooks

    if request_hooks is None or request_hooks.get('response') == []:
        return session_hooks

    ret = {}
    for (k, v) in request_hooks.items():
        if v is not None:
            ret[k] = set(v).union(session_hooks.get(k, []))

    return ret


class WoobSession(Session):
    def prepare_request(self, request):
        """Constructs a :class:`PreparedRequest <PreparedRequest>` for
        transmission and returns it. The :class:`PreparedRequest` has settings
        merged from the :class:`Request <Request>` instance and those of the
        :class:`Session`.

        :param request: :class:`Request` instance to prepare with this
                        session's settings.
        """
        cookies = request.cookies or {}

        # Bootstrap CookieJar.
        if not isinstance(cookies, cookielib.CookieJar):
            cookies = cookiejar_from_dict(cookies)

        # Merge with session cookies
        merged_cookies = RequestsCookieJar()
        merged_cookies.update(self.cookies)
        merged_cookies.update(cookies)

        # Set environment's basic authentication if not explicitly set.
        auth = request.auth
        if self.trust_env and not auth and not self.auth:
            auth = get_netrc_auth(request.url)

        p = PreparedRequest()
        p.prepare(
            method=request.method.upper(),
            url=request.url,
            files=request.files,
            data=request.data,
            json=request.json,
            headers=merge_setting(request.headers, self.headers, dict_class=CaseInsensitiveDict),
            params=merge_setting(request.params, self.params),
            auth=merge_setting(auth, self.auth),
            cookies=merged_cookies,
            hooks=merge_hooks(request.hooks, self.hooks),
        )
        return p


WeboobSession = WoobSession


class FuturesSession(WoobSession):
    def __init__(self, executor=None, max_workers=2, max_retries=2, *args, **kwargs):
        """Creates a FuturesSession

        Notes
        ~~~~~

        * ProcessPoolExecutor is not supported b/c Response objects are
          not picklable.

        * If you provide both `executor` and `max_workers`, the latter is
          ignored and provided executor is used as is.
        """
        super(FuturesSession, self).__init__(*args, **kwargs)
        if executor is None and ThreadPoolExecutor is not None:
            executor = ThreadPoolExecutor(max_workers=max_workers)
            # set connection pool size equal to max_workers if needed
            if max_workers > DEFAULT_POOLSIZE:
                adapter_kwargs = dict(pool_connections=max_workers,
                                      pool_maxsize=max_workers,
                                      max_retries=max_retries)
                self.mount('https://', HTTPAdapter(**adapter_kwargs))
                self.mount('http://', HTTPAdapter(**adapter_kwargs))

        self.executor = executor

    def send(self, *args, **kwargs):
        """Maintains the existing api for :meth:`Session.send`

        Used by :meth:`request` and thus all of the higher level methods

        If the `is_async` param is True, the request is processed in a
        thread. Otherwise, the request is processed as usual, in a blocking way.

        In all cases, it will call the `callback` parameter and return its
        result when the request has been processed.
        """
        if 'async' in kwargs:
            import warnings
            warnings.warn('Please use is_async instead of async.', DeprecationWarning)
            kwargs['is_async'] = kwargs['async']
            del kwargs['async']

        sup = super(FuturesSession, self).send

        callback = kwargs.pop('callback', lambda future, response: response)
        is_async = kwargs.pop('is_async', False)

        def func(*args, **kwargs):
            resp = sup(*args, **kwargs)
            return callback(self, resp)

        if is_async:
            if not self.executor:
                raise ImportError('Please install python3-concurrent.futures')
            return self.executor.submit(func, *args, **kwargs)

        return func(*args, **kwargs)

    def close(self):
        super(FuturesSession, self).close()
        if self.executor:
            self.executor.shutdown()
