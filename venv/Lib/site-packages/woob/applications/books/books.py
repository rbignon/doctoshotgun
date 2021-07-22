# -*- coding: utf-8 -*-

# Copyright(C) 2009-2012  Jeremy Monnet
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

from __future__ import print_function

from woob.capabilities.library import CapBook, Book
from woob.tools.application.repl import ReplApplication
from woob.tools.application.formatters.iformatter import PrettyFormatter

__all__ = ['AppBooks']


class RentedListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'date', 'author', 'name', 'late')

    RED = '[1;31m'

    def get_title(self, obj):
        s = u'%s — %s (%s)' % (obj.author, obj.name, obj.date)
        if obj.late:
            s += u' %sLATE!%s' % (self.RED, self.NC)
        return s


class AppBooks(ReplApplication):
    APPNAME = 'books'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2012-YEAR Jeremy Monnet'
    CAPS = CapBook
    DESCRIPTION = "Console application allowing to list your books rented or booked at the library, " \
                  "book and search new ones, get your booking history (if available)."
    SHORT_DESCRIPTION = "manage rented books"
    EXTRA_FORMATTERS = {'rented_list':   RentedListFormatter,
                        }
    DEFAULT_FORMATTER = 'table'
    COMMANDS_FORMATTERS = {'ls':          'rented_list',
                           'list':        'rented_list',
                           'rented':      'rented_list',
                          }

    COLLECTION_OBJECTS = (Book, )

    def do_renew(self, id):
        """
        renew ID

        Renew a book
        """

        id, backend_name = self.parse_id(id)
        if not id:
            print('Error: please give a book ID (hint: use ls command)', file=self.stderr)
            return 2
        names = (backend_name,) if backend_name is not None else None

        for renew in self.do('renew_book', id, backends=names):
            self.format(renew)

    def do_rented(self, args):
        """
        rented

        List rented books
        """

        for book in self.do('iter_rented', backends=None):
            self.format(book)

    def do_search(self, pattern):
        """
        search PATTERN

        Search books
        """
        for book in self.do('search_books', pattern):
            self.format(book)
