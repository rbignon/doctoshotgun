# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012 Jeremy Monnet
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

from .collection import CapCollection
from .base import BaseObject, BoolField, StringField
from .date import DateField


__all__ = ['Book', 'Renew', 'CapBook']


class Book(BaseObject):
    """
    Describes a book.
    """
    name =      StringField('Name of the book')
    author =    StringField('Author of the book')
    location =  StringField('Location')
    date =      DateField('The due date')
    late =      BoolField('Are you late?')


class Renew(BaseObject):
    """
    A renew message.
    """
    message = StringField('Message')


class CapBook(CapCollection):
    """
    Library websites.
    """

    def iter_resources(self, objs, split_path):
        """
        Iter resources. It retuns :func:`iter_books`.
        """
        if Book in objs:
            self._restrict_level(split_path)
            return self.iter_books()

    def iter_books(self):
        """
        Iter books.

        :rtype: iter[:class:`Book`]
        """
        raise NotImplementedError()

    def get_book(self, _id):
        """
        Get a book from an ID.

        :param _id: ID of the book
        :type _id: str
        :rtype: :class:`Book`
        """
        raise NotImplementedError()

    def iter_booked(self):
        raise NotImplementedError()

    def renew_book(self, _id):
        raise NotImplementedError()

    def iter_rented(self):
        raise NotImplementedError()

    def search_books(self, _string):
        raise NotImplementedError()
