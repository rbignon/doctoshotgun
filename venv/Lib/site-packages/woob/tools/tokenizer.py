# -*- coding: utf-8 -*-

# Copyright(C) 2014 Oleg Plakhotniuk
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

__all__ = ['ReTokenizer']


class ReTokenizer(object):
    """
    Simple regex-based tokenizer (AKA lexer or lexical analyser).
    Useful for PDF statements parsing.

    1. There's a lexing table consisting of type-regex tuples.
    2. Lexer splits text into chunks using the separator character.
    3. Text chunk is sequentially matched against regexes and first
       successful match defines the type of the token.

    Check out test() function below for examples.
    """

    def __init__(self, text, sep, lex):
        self._lex = lex
        self._tok = [ReToken(lex, chunk) for chunk in text.split(sep)]

    def tok(self, index):
        if 0 <= index < len(self._tok):
            return self._tok[index]
        else:
            return ReToken(self._lex, eof=True)

    def simple_read(self, token_type, pos, transform=lambda v: v):
        t = self.tok(pos)
        is_type = getattr(t, 'is_%s' % token_type)()
        return (pos+1, transform(t.value())) if is_type else (pos, None)


class ReToken(object):
    def __init__(self, lex, chunk=None, eof=False):
        self._lex = lex
        self._eof = eof
        self._value = None
        self._type = None
        if chunk is not None:
            for type_, regex in self._lex:
                m = re.match(regex, chunk, flags=re.UNICODE)
                if m:
                    self._type = type_
                    if len(m.groups()) == 1:
                        self._value = m.groups()[0]
                    elif m.groups():
                        self._value = m.groups()
                    else:
                        self._value = m.group(0)
                    break

    def is_eof(self):
        return self._eof

    def value(self):
        return self._value

    def __getattr__(self, name):
        if name.startswith('is_'):
            return lambda: self._type == name[3:]
        raise AttributeError()


def test():
    t = ReTokenizer('foo bar baz', ' ', [('f', r'^f'), ('b', r'^b')])

    assert t.tok(0).is_f()
    assert t.tok(1).is_b()
    assert t.tok(2).is_b()

    assert t.tok(-1).is_eof()
    assert t.tok(3).is_eof()

    assert not t.tok(-1).is_f()
    assert not t.tok(0).is_b()
    assert not t.tok(0).is_eof()

    t = ReTokenizer('nogroup onegroup multigroup', ' ', [
        ('ng', r'^n.*$'),
        ('og', r'^one(g.*)$'),
        ('mg', r'^(m.*)(g.*)$')])

    assert t.tok(-1).value() is None
    assert t.tok(0).value() == 'nogroup'
    assert t.tok(1).value() == 'group'
    assert t.tok(2).value() == ('multi', 'group')
