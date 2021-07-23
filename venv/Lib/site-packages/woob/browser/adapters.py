# -*- coding: utf-8 -*-

# Copyright(C) 2019 Romain Bignon
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


import requests


__all__ = ['HTTPAdapter']


class HTTPAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self._proxy_headers = kwargs.pop('proxy_headers', {})
        super(HTTPAdapter, self).__init__(*args, **kwargs)

    def add_proxy_header(self, key, value):
        self._proxy_headers[key] = value

    def update_proxy_headers(self, headers):
        self._proxy_headers.update(headers)

    def proxy_headers(self, proxy):
        headers = super(HTTPAdapter, self).proxy_headers(proxy)
        headers.update(self._proxy_headers)
        return headers
