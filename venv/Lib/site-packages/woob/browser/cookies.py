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

import requests.cookies
try:
    import cookielib
except ImportError:
    import http.cookiejar as cookielib


__all__ = ['WoobCookieJar', 'BlockAllCookies']


class WoobCookieJar(requests.cookies.RequestsCookieJar):
    @classmethod
    def from_cookiejar(klass, cj):
        """
        Create a WoobCookieJar from another CookieJar instance.
        """
        return requests.cookies.merge_cookies(klass(), cj)

    def export(self, filename):
        """
        Export all cookies to a file, regardless of expiration, etc.
        """
        cj = requests.cookies.merge_cookies(cookielib.LWPCookieJar(), self)
        cj.save(filename, ignore_discard=True, ignore_expires=True)

    def copy(self):
        """Return an object copy of the cookie jar."""
        new_cj = type(self)()
        if hasattr(self, 'get_policy'):
            new_cj.set_policy(self.get_policy())
        else:
            new_cj.set_policy(self._policy)
        new_cj.update(self)
        return new_cj


WeboobCookieJar = WoobCookieJar


class BlockAllCookies(cookielib.CookiePolicy):
    return_ok = set_ok = domain_return_ok = path_return_ok = lambda self, *args, **kwargs: False
    netscape = True
    rfc2965 = hide_cookie2 = False
