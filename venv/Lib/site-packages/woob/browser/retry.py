# -*- coding: utf-8 -*-

# Copyright(C) 2017  Vincent A
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

from contextlib import contextmanager
from functools import wraps

from .browsers import LoginBrowser
from .exceptions import LoggedOut
from ..exceptions import BrowserUnavailable


__all__ = ['login_method', 'retry_on_logout', 'RetryLoginBrowser']


def login_method(func):
    """Decorate a method to indicate the browser is logging in.

    When the decorated method is called, pages like
    `woob.browser.pages.LoginPage` will not raise `LoggedOut`, since it is
    expected for the browser not to be logged yet.
    """

    func.login_decorated = True

    @wraps(func)
    def wrapper(browser, *args, **kwargs):
        browser.logging_in += 1
        try:
            return func(browser, *args, **kwargs)
        finally:
            browser.logging_in -= 1
    return wrapper


def retry_on_logout(exc_check=LoggedOut, tries=4):
    """Decorate a function to retry several times in case of exception.

    The decorated function is called at max 4 times. It is retried only when it
    raises an exception of the type `woob.browser.exceptions.LoggedOut`.
    If the function call succeeds and returns an iterator, a wrapper to the
    iterator is returned. If iterating on the result raises a `LoggedOut`,
    the iterator is recreated by re-calling the function, but the values
    already yielded will not be re-yielded.
    For consistency, the function MUST always return values in the same order.

    Adding this decorator to a method which can be called from another
    decorated method should be avoided, since nested calls will greatly
    increase the number of retries.
    """

    if not isinstance(exc_check, type) or not issubclass(exc_check, Exception):
        raise TypeError('retry_on_logout() must be called in order to decorate %r' % tries)

    def decorator(func):
        @wraps(func)
        def wrapper(browser, *args, **kwargs):
            cb = lambda: func(browser, *args, **kwargs)

            for i in range(tries, 0, -1):
                try:
                    ret = cb()
                except exc_check as exc:
                    browser.logger.info('%r raised, retrying', exc)
                    continue

                if not (hasattr(ret, '__next__') or hasattr(ret, 'next')):
                    return ret  # simple value, no need to retry on items
                return iter_retry(cb, value=ret, remaining=i, exc_check=exc_check, logger=browser.logger)

            raise BrowserUnavailable('Site did not reply successfully after multiple tries')

        return wrapper
    return decorator


@contextmanager
def retry_on_logout_context(tries=4, logger=None):
    for i in range(tries, 0, -1):
        try:
            yield
        except LoggedOut as exc:
            if logger:
                logger.debug('%r raised, retrying', exc)
        else:
            return
    raise BrowserUnavailable('Site did not reply successfully after multiple tries')


class RetryLoginBrowser(LoginBrowser):
    """Browser that can retry methods if the site logs out the session.

    Some sites can terminate a session anytime, redirecting to a login page.
    To avoid having to handle it in the middle of every method, one can simply
    let logouts raise a `woob.browser.exceptions.LoggedOut` exception that
    is handled with a retry, thanks to the `@retry_on_logout` decorator.

    The `woob.browser.pages.LoginPage` will raise `LoggedOut` if the browser
    is not currently logging in. To detect this situation, the `do_login`
    method MUST be decorated with `@login_method`.
    """
    def __init__(self, *args, **kwargs):
        super(RetryLoginBrowser, self).__init__(*args, **kwargs)
        self.logging_in = 0

        if not hasattr(self.do_login, 'login_decorated'):
            raise Exception('do_login method was not decorated with @login_method')


class iter_retry(object):
    # when the callback is retried, it will create a new iterator, but we may already yielded
    # some values, so we need to keep track of them and seek in the middle of the iterator

    def __init__(self, cb, remaining=4, value=None, exc_check=LoggedOut, logger=None):
        self.cb = cb
        self.it = iter(value) if value is not None else None
        self.items = []
        self.remaining = remaining
        self.logger = logger
        self.exc_check = exc_check

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining <= 0:
            raise BrowserUnavailable('Site did not reply successfully after multiple tries')

        if self.it is None:
            self.it = iter(self.cb())

            # recreated iterator, consume previous items
            try:
                nb = -1
                for nb, sent in enumerate(self.items):
                    new = next(self.it)
                    if hasattr(new, 'iter_fields'):
                        equal = dict(sent.iter_fields()) == dict(new.iter_fields())
                    else:
                        equal = sent == new
                    if not equal:
                        # safety is not guaranteed
                        raise BrowserUnavailable('Site replied inconsistently between retries, %r vs %r', sent, new)
            except StopIteration:
                raise BrowserUnavailable('Site replied fewer elements (%d) than last iteration (%d)', nb + 1, len(self.items))
            except self.exc_check as exc:
                if self.logger:
                    self.logger.info('%r raised, retrying', exc)
                self.it = None
                self.remaining -= 1
                return next(self)

        # return one item
        try:
            obj = next(self.it)
        except self.exc_check as exc:
            if self.logger:
                self.logger.info('%r raised, retrying', exc)
            self.it = None
            self.remaining -= 1
            return next(self)
        else:
            self.items.append(obj)
            return obj

    next = __next__
