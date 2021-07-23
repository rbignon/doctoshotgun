# -*- coding: utf-8 -*-

# Copyright(C) 2014 Romain Bignon
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

from functools import wraps
import re
import requests

from woob.tools.compat import basestring, unquote
from woob.tools.regex_helper import normalize
from woob.tools.misc import to_unicode


class UrlNotResolvable(Exception):
    """
    Raised when trying to locate on an URL instance which url pattern is not resolvable as a real url.
    """


class URL(object):
    """
    A description of an URL on the PagesBrowser website.

    It takes one or several regexps to match urls, and an optional Page
    class which is instancied by PagesBrowser.open if the page matches a regex.
    """
    _creation_counter = 0

    def __init__(self, *args):
        self.urls = []
        self.klass = None
        self.browser = None
        for arg in args:
            if isinstance(arg, basestring):
                self.urls.append(arg)
            if isinstance(arg, type):
                self.klass = arg

        self._creation_counter = URL._creation_counter
        URL._creation_counter += 1

    def is_here(self, **kwargs):
        """
        Returns True if the current page of browser matches this URL.
        If arguments are provided, and only then, they are checked against the arguments
        that were used to build the current page URL.
        """
        assert self.klass is not None, "You can use this method only if there is a Page class handler."

        if len(kwargs):
            params = self.match(self.build(**kwargs)).groupdict()
        else:
            params = None

        # XXX use unquote on current params values because if there are spaces
        # or special characters in them, it is encoded only in but not in kwargs.
        return self.browser.page and isinstance(self.browser.page, self.klass) \
            and (params is None or params == dict([(k,unquote(v)) for k,v in self.browser.page.params.items()]))

    def stay_or_go(self, headers=None, **kwargs):
        """
        Request to go on this url only if we aren't already here.

        Arguments are optional parameters for url.

        >>> url = URL('http://exawple.org/(?P<pagename>).html')
        >>> url.stay_or_go(pagename='index')
        """
        if self.is_here(**kwargs):
            return self.browser.page

        return self.go(headers=headers, **kwargs)

    def go(self, params=None, data=None, json=None, method=None, headers=None, **kwargs):
        """
        Request to go on this url.

        Arguments are optional parameters for url.

        >>> url = URL('http://exawple.org/(?P<pagename>).html')
        >>> url.stay_or_go(pagename='index')
        """
        r = self.browser.location(self.build(**kwargs), params=params, data=data, json=json, method=method, headers=headers or {})
        return r.page or r

    def open(self, params=None, data=None, json=None, method=None, headers=None, is_async=False, callback=lambda response: response, **kwargs):
        """
        Request to open on this url.

        Arguments are optional parameters for url.

        :param data: POST data
        :type url: str or dict or None

        >>> url = URL('http://exawple.org/(?P<pagename>).html')
        >>> url.open(pagename='index')
        """
        r = self.browser.open(self.build(**kwargs), params=params, data=data, json=json, method=method, headers=headers or {}, is_async=is_async, callback=callback)

        if hasattr(r, 'page') and r.page:
            return r.page
        return r

    def build(self, **kwargs):
        """
        Build an url with the given arguments from URL's regexps.

        :param param: Query string parameters

        :rtype: :class:`str`
        :raises: :class:`UrlNotResolvable` if unable to resolve a correct url with the given arguments.
        """
        browser = kwargs.pop('browser', self.browser)
        params = kwargs.pop('params', None)
        patterns = []
        for url in self.urls:
            patterns += normalize(url)

        for pattern, _ in patterns:
            url = pattern
            # only use full-name substitutions, to allow % in URLs
            args = kwargs.copy()
            for key in list(args.keys()):  # need to use keys() because of pop()
                search = '%%(%s)s' % key
                if search in pattern:
                    url = url.replace(search, to_unicode(args.pop(key)))
            # if there are named substitutions left, ignore pattern
            if re.search('%\([A-z_]+\)s', url):
                continue
            # if not all args were used
            if len(args):
                continue

            url = browser.absurl(url, base=True)
            if params:
                p = requests.models.PreparedRequest()
                p.prepare_url(url, params)
                url = p.url
            return url

        raise UrlNotResolvable('Unable to resolve URL with %r. Available are %s' % (kwargs, ', '.join([pattern for pattern, _ in patterns])))

    def match(self, url, base=None):
        """
        Check if the given url match this object.
        """
        if base is None:
            assert self.browser is not None
            base = self.browser.BASEURL

        for regex in self.urls:
            if not re.match(r'^[\w\?]+://.*', regex):
                regex = re.escape(base).rstrip('/') + '/' + regex.lstrip('/')
            m = re.match(regex, url)
            if m:
                return m

    def handle(self, response):
        """
        Handle a HTTP response to get an instance of the klass if it matches.
        """
        if self.klass is None:
            return
        if response.request.method == 'HEAD':
            return

        m = self.match(response.url)
        if m:
            page = self.klass(self.browser, response, m.groupdict())
            if hasattr(page, 'is_here'):
                if callable(page.is_here):
                    if page.is_here():
                        return page
                else:
                    assert isinstance(page.is_here, basestring)
                    if page.doc.xpath(page.is_here):
                        return page
            else:
                return page

    def id2url(self, func):
        r"""
        Helper decorator to get an URL if the given first parameter is an ID.
        """

        @wraps(func)
        def inner(browser, id_or_url, *args, **kwargs):
            if re.match('^https?://.*', id_or_url):
                if not self.match(id_or_url, browser.BASEURL):
                    return
            else:
                id_or_url = self.build(id=id_or_url, browser=browser)

            return func(browser, id_or_url, *args, **kwargs)
        return inner


class BrowserParamURL(URL):
    """A URL that automatically fills some params from browser attributes.

    URL patterns having groups named "browser_*" will pick the relevant
    attribute from the browser. For example:

        foo = BrowserParamURL(r'/foo\?bar=(?P<browser_token>\w+)')

    The browser is expected to have a `.token` attribute and it will be passed
    automatically when just calling `foo.go()`, it's equivalent to
    `foo.go(browser_token=browser.token)`.

    Warning: all `browser_*` params will be passed, having multiple patterns
    with different groups in a `BrowserParamURL` is risky.
    """

    def build(self, **kwargs):
        prefix = 'browser_'

        for arg in kwargs:
            if arg.startswith(prefix):
                raise ValueError('parameter %r is reserved by URL pattern')

        for url in self.urls:
            for groupname in re.compile(url).groupindex:
                if groupname.startswith(prefix):
                    attrname = groupname[len(prefix):]
                    kwargs[groupname] = getattr(self.browser, attrname)

        return super(BrowserParamURL, self).build(**kwargs)


def normalize_url(url):
    """Normalize URL by lower-casing the domain and other fixes.

    Lower-cases the domain, removes the default port and a trailing dot.

    >>> normalize_url('http://EXAMPLE:80')
    'http://example'
    """

    def norm_domain(m):
        # don't use urlparse/urlunparse because it might do too much normalization

        auth, authsep, hostport = m.group(2).rpartition('@')
        host, portsep, port = hostport.partition(':')

        if (
            (port == '443' and m.group(1) == 'https://')
            or (port == '80' and m.group(1) == 'http://')
        ):
            portsep = port = ''

        host = host.lower().rstrip('.')

        return ''.join((m.group(1), auth, authsep, host, portsep, port))

    return re.sub(r'^(https?://)([^/#?]+)', norm_domain, url)


def test_normalize_url():
    tests = [
        ('https://foo/bar/baz', 'https://foo/bar/baz'),

        ('https://FOO/bar', 'https://foo/bar'),

        ('https://foo:1234/bar', 'https://foo:1234/bar'),
        ('https://foo:443/bar', 'https://foo/bar'),
        ('http://foo:1234', 'http://foo:1234'),
        ('http://foo:80', 'http://foo'),
        ('http://User:Password@foo:80', 'http://User:Password@foo'),
        ('http://User:Password@foo:80/bar', 'http://User:Password@foo/bar'),

        ('http://foo#BAR', 'http://foo#BAR'),
        ('https://foo#BAR', 'https://foo#BAR'),
        ('https://foo:443#BAR', 'https://foo#BAR'),
    ]
    for todo, expected in tests:
        assert normalize_url(todo) == expected

