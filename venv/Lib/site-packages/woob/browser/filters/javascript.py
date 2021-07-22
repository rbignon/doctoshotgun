# -*- coding: utf-8 -*-

# Copyright(C) 2014  Simon Murail
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


import re
from ast import literal_eval
import sys

from woob.browser.filters.standard import Filter, Regexp, RegexpError, FormatError, ItemNotFound


__all__ = ['JSPayload', 'JSValue', 'JSVar']


def _quoted(q):
    return r'(?<!\\){0}(?:\\{0}|[^{0}])*{0}'.format(q)


class JSPayload(Filter):
    r"""
    Get Javascript code from tag's text, cleaned from all comments.

    It filters code in a such a way that corner cases are handled, such as
    comments in string literals and comments in comments.

    The following snippet is borrowed from <http://ostermiller.org/findcomment.html>:

    >>> JSPayload.filter('''someString = "An example comment: /* example */";
    ...
    ... // The comment around this code has been commented out.
    ... // /*
    ... some_code();
    ... // */''')
    'someString = "An example comment: /* example */";\n\nsome_code();\n'

    """
    _single_line_comment = '[ \t\v\f]*//.*\r?(?:\n|$)'
    _multi_line_comment = '/\*(?:.|[\r\n])*?\*/'
    _splitter = re.compile('(?:(%s|%s)|%s|%s)' % (_quoted('"'),
                                                  _quoted("'"),
                                                  _single_line_comment,
                                                  _multi_line_comment))

    @classmethod
    def filter(cls, value):
        return ''.join(filter(bool, cls._splitter.split(value)))


class JSValue(Regexp):
    r"""
    Get one or many JavaScript literals.

    It only understands literal values, but should parse them well. Values
    are converted in python values, quotes and slashes in strings are stripped.

    >>> JSValue().filter('boringVar = "boring string"')
    u'boring string'
    >>> JSValue().filter('somecode(); doConfuse(0xdead, cat);')
    57005
    >>> JSValue(need_type=int, nth=2).filter('fazboo("3", "5", 7, "9");')
    7
    >>> JSValue(nth='*').filter('foo([1, 2, 3], "blah", 5.0, true, null]);')
    [1, 2, 3, u'blah', 5.0, True, None]
    """
    pattern = r"""(?x)
        (?:(?P<float>(?:[-+]\s*)?                     # float ?
               (?:(?:\d+\.\d*|\d*\.\d+)(?:[eE]\d+)?
                 |\d+[eE]\d+))
          |(?P<int>(?:[-+]\s*)?(?:0[bB][01]+          # int ?
                                 |0[oO][0-7]+
                                 |0[xX][0-9a-fA-F]+
                                 |\d+))
          |(?:(?:(?:new\s+)?String\()?(?P<str>(?:%s|%s)))  # str ?
          |(?P<bool>true|false)                       # bool ?
          |(?P<None>null))                            # None ?
    """ % (_quoted('"'), _quoted("'"))

    def to_python(self, m):
        "Convert MatchObject to python value"
        values = m.groupdict()
        for t, v in values.items():
            if v is not None:
                break
        if self.need_type and t != self.need_type:
            raise ItemNotFound('Value with type %s not found' % self.need_type)
        if t in ('int', 'float'):
            return literal_eval(v)
        if t == 'str':
            if sys.version_info.major < 3:
                return literal_eval(v).decode('utf-8')
            return literal_eval(v)
        if t == 'bool':
            return v == 'true'
        if t == 'None':
            return
        if self.default:
            return self.default
        raise FormatError('Unable to parse %r value' % m.group(0))

    def __init__(self, selector=None, need_type=None, **kwargs):
        assert 'pattern' not in kwargs and 'flags' not in kwargs, \
               "It would be meaningless to define a pattern and/or flags, use Regexp"
        assert 'template' not in kwargs, "Can't use a template, use Regexp if you have to"
        self.need_type = need_type.__name__ if type(need_type) == type else need_type
        super(JSValue, self).__init__(selector, pattern=self.pattern, template=self.to_python, **kwargs)


class JSVar(JSValue):
    r"""
    Get assigned value of a variable, either as an initialisation value, either
    as an assignement. One can use Regexp's nth parameter to be more specific.

    See JSValue for more details about parsed values.

    >>> JSVar(var='test').filter("var test = .1;\nsomecode()")
    0.1
    >>> JSVar(var='test').filter("test = 666;\nsomecode()")
    666
    >>> JSVar(var='test').filter("test = 'Some \\'string\\' value, isn\\'t it ?';\nsomecode()")
    u"Some 'string' value, isn't it ?"
    >>> JSVar(var='test').filter('test = "Some \\"string\\" value";\nsomecode()')
    u'Some "string" value'
    >>> JSVar(var='test').filter("var test = false;\nsomecode()")
    False
    >>> JSVar(var='test', nth=1).filter("var test = false; test = true;\nsomecode()")
    True
    """
    pattern_template = r"""(?x)
        (?:var\s+)?                                   # optional var keyword
        \b%s                                          # var name
        \s*=\s*                                       # equal sign
    """ + JSValue.pattern

    def __init__(self, selector=None, var=None, need_type=None, **kwargs):
        assert var is not None, 'Please give a var parameter'
        self.var = var
        self.pattern = self.pattern_template % re.escape(var)
        super(JSVar, self).__init__(selector, need_type=need_type, **kwargs)

    def filter(self, txt):
        try:
            return super(JSVar, self).filter(txt)
        except RegexpError:
            raise ItemNotFound('Variable %r not found' % self.var)
