# -*- coding: utf-8 -*-

# Copyright(C) 2017  woob project
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

import lxml.html

from woob.exceptions import ParseError
from woob.tools.compat import unicode, basestring
from woob.tools.log import getLogger, DEBUG_FILTERS


__all__ = ['FilterError', 'ItemNotFound', 'Filter',]


class NoDefault(object):
    def __repr__(self):
        return 'NO_DEFAULT'

_NO_DEFAULT = NoDefault()


class FilterError(ParseError):
    pass


class ItemNotFound(FilterError):
    pass


class _Filter(object):
    _creation_counter = 0

    def __init__(self, default=_NO_DEFAULT):
        self._key = None
        self._obj = None
        self.default = default
        self._creation_counter = _Filter._creation_counter
        _Filter._creation_counter += 1

    def __or__(self, o):
        self.default = o
        return self

    def __and__(self, o):
        if isinstance(o, type) and issubclass(o, _Filter):
            o = o()
        o.selector = self
        return o

    def default_or_raise(self, exception):
        if self.default is not _NO_DEFAULT:
            return self.default
        else:
            raise exception

    def __str__(self):
        return self.__class__.__name__

    def highlight_el(self, el, item=None):
        obj = self._obj or item
        try:
            if not hasattr(obj, 'saved_attrib'):
                return
            if not obj.page.browser.highlight_el:
                return
        except AttributeError:
            return

        if el not in obj.saved_attrib:
            obj.saved_attrib[el] = dict(el.attrib)

        el.attrib['style'] = 'color: white !important; background: red !important;'
        if self._key:
            el.attrib['title'] = 'woob field: %s' % self._key


def debug(*args):
    """
    A decorator function to provide some debug information
    in Filters.
    It prints by default the name of the Filter and the input value.
    """
    def wraper(function):
        @wraps(function)
        def print_debug(self, value):
            logger = getLogger('b2filters')
            result = ''
            outputvalue = value
            if isinstance(value, list):
                from lxml import etree
                outputvalue = ''
                first = True
                for element in value:
                    if first:
                        first = False
                    else:
                        outputvalue += ', '
                    if isinstance(element, etree.ElementBase):
                        outputvalue += "%s" % etree.tostring(element, encoding=unicode)
                    else:
                        outputvalue += "%r" % element
            if self._obj is not None:
                result += "%s" % self._obj._random_id
            if self._key is not None:
                result += ".%s" % self._key
            name = str(self)
            result += " %s(%r" % (name, outputvalue)
            for arg in self.__dict__:
                if arg.startswith('_') or arg == u"selector":
                    continue
                if arg == u'default' and getattr(self, arg) == _NO_DEFAULT:
                    continue
                result += ", %s=%r" % (arg, getattr(self, arg))
            result += u')'
            logger.log(DEBUG_FILTERS, result)
            res = function(self, value)
            return res
        return print_debug
    return wraper


class Filter(_Filter):
    """
    Class used to filter on a HTML element given as call parameter to return
    matching elements.

    Filters can be chained, so the parameter supplied to constructor can be
    either a xpath selector string, or an other filter called before.

    >>> from lxml.html import etree
    >>> f = CleanDecimal(CleanText('//p'), replace_dots=True)
    >>> f(etree.fromstring('<html><body><p>blah: <span>229,90</span></p></body></html>'))
    Decimal('229.90')
    """

    def __init__(self, selector=None, default=_NO_DEFAULT):
        """
        :param default: default value in case the filter fails to find or parse
                        the requested value
        """

        super(Filter, self).__init__(default=default)
        self.selector = selector

    def select(self, selector, item):
        if isinstance(selector, basestring):
            ret = item.xpath(selector)
        elif isinstance(selector, _Filter):
            selector._key = self._key
            selector._obj = self._obj
            ret = selector(item)
        elif callable(selector):
            ret = selector(item)
        else:
            ret = selector

        if isinstance(ret, lxml.html.HtmlElement):
            self.highlight_el(ret, item)
        elif isinstance(ret, list):
            for el in ret:
                if isinstance(el, lxml.html.HtmlElement):
                    self.highlight_el(el, item)

        return ret

    def __call__(self, item):
        return self.filter(self.select(self.selector, item))

    @debug()
    def filter(self, value):
        """
        This method has to be overridden by children classes.
        """
        raise NotImplementedError()


class _Selector(Filter):
    def filter(self, elements):
        if elements is not None:
            return elements
        else:
            return self.default_or_raise(FilterError('Element %r not found' % self.selector))
