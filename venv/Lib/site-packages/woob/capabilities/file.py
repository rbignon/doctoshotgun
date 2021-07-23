# -*- coding: utf-8 -*-

# Copyright(C) 2013 Pierre Mazière
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

from woob.tools.compat import long

from .base import Capability, BaseObject, NotAvailable, Field, StringField, IntField, Enum
from .date import DateField


__all__ = ['BaseFile', 'CapFile']


class LICENSES(Enum):
    OTHER = u'Other license'
    PD = u'Public Domain'
    COPYRIGHT = u'All rights reserved'
    CCBY = u'Creative Commons BY'
    CCBYSA = u'Creative Commons BY-SA'
    CCBYNC = u'Creative Commons BY-NC'
    CCBYND = u'Creative Commons BY-ND'
    CCBYNCSA = u'Creative Commons BY-NC-SA'
    CCBYNCND = u'Creative Commons BY-NC-ND'
    GFDL = u'GNU Free Documentation License'


class BaseFile(BaseObject):
    """
    Represent a file.
    """
    title =         StringField('File title')
    ext =           StringField('File extension')
    author =        StringField('File author')
    description =   StringField('File description')
    date =          DateField('File publication date')
    size =          IntField('File size in bytes', default=NotAvailable)
    rating =        Field('Rating', int, long, float, default=NotAvailable)
    rating_max =    Field('Maximum rating', int, long, float, default=NotAvailable)
    license =       StringField('License name')

    def __unicode__(self):
        return self.url or u''

    def __repr__(self):
        return '<%s title=%r url=%r>' % (type(self).__name__, self.title, self.url)

    @classmethod
    def id2url(cls, _id):
        """
        Overloaded in child classes provided by backends.
        """
        raise NotImplementedError()

    @property
    def page_url(self):
        """
        Get file page URL
        """
        return self.id2url(self.id)


class SearchSort(Enum):
    RELEVANCE = 0
    RATING = 1
    VIEWS = 2
    DATE = 3


class CapFile(Capability):
    """
    Provide file download
    """
    SEARCH_RELEVANCE = SearchSort.RELEVANCE
    SEARCH_RATING = SearchSort.RATING
    SEARCH_VIEWS = SearchSort.VIEWS
    SEARCH_DATE = SearchSort.DATE

    def search_file(self, pattern, sortby=SEARCH_RELEVANCE):
        """
        :param pattern: pattern to search on
        :type pattern: str
        :param sortby: sort by ... (user SEARCH_* constants)
        :rtype: iter[:class:`BaseFile`]
        """
        raise NotImplementedError()

    def get_file(self, _id):
        """
        Get a file from an ID

        :param _id: the file id. I can be a numeric ID, or a page url
        :type _id: str
        :rtype: :class:`BaseFile` or None if not found.
        """
        raise NotImplementedError()
