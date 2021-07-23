# -*- coding: utf-8 -*-

# Copyright(C) 2014-2015 Romain Bignon, Laurent Bachelier
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

from woob.tools.compat import basestring

from .base import _Filter, _NO_DEFAULT, Filter, debug, ItemNotFound

__all__ = ['Dict']


class NotFound(object):
    def __repr__(self):
        return 'NOT_FOUND'

_NOT_FOUND = NotFound()


class Dict(Filter):
    def __init__(self, selector=None, default=_NO_DEFAULT):
        super(Dict, self).__init__(self, default=default)
        if selector is None:
            self.selector = []
        elif isinstance(selector, basestring):
            self.selector = selector.split('/')
        elif callable(selector):
            self.selector = [selector]
        else:
            self.selector = selector

    def __getitem__(self, name):
        self.selector.append(name)
        return self

    @debug()
    def filter(self, elements):
        if elements is not _NOT_FOUND:
            return elements
        else:
            return self.default_or_raise(ItemNotFound('Element %r not found' % self.selector))

    @classmethod
    def select(cls, selector, item, obj=None, key=None):
        if isinstance(item, (dict, list)):
            content = item
        else:
            content = item.el

        for el in selector:
            if isinstance(content, list):
                el = int(el)
            elif isinstance(el, _Filter):
                el._key = key
                el._obj = obj
                el = el(item)
            elif callable(el):
                el = el(item)

            try:
                content = content[el]
            except (KeyError, IndexError, TypeError):
                return _NOT_FOUND

        return content
