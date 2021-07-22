# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Romain Bignon, Christophe Benz, Noé Rubinstein
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

from collections import OrderedDict

from .base import NotLoaded, Field, BoolField, BytesField
from .file import CapFile, BaseFile

__all__ = ['BaseImage', 'Thumbnail', 'CapImage']


class _BaseImage(BaseFile):
    """
    Fake class to allow the inclusion of a BaseImage property within
    the real BaseImage class
    """
    pass


class Thumbnail(_BaseImage):
    """
    Thumbnail of an image.
    """

    data = BytesField('Data')

    def __init__(self, url):
        super(Thumbnail, self).__init__(url)
        self.url = url.replace(u' ', u'%20')

    def __unicode__(self):
        return self.url

    def __repr__(self):
        return '<Thumbnail url=%r>' % self.url

    def __iscomplete__(self):
        return self.data is not NotLoaded


class BaseImage(_BaseImage):
    """
    Represents an image file.
    """
    nsfw =      BoolField('Is this Not Safe For Work', default=False)
    thumbnail = Field('Thumbnail of the image', Thumbnail)
    data =      BytesField('Data of image')

    def __iscomplete__(self):
        return self.data is not NotLoaded

    def to_dict(self):
        def iter_decorate(d):
            for key, value in d:
                if key == 'data':
                    continue

                if key == 'id' and self.backend is not None:
                    value = self.fullid

                yield key, value

        fields_iterator = self.iter_fields()
        return OrderedDict(iter_decorate(fields_iterator))


class CapImage(CapFile):
    """
    Image file provider
    """

    def search_image(self, pattern, sortby=CapFile.SEARCH_RELEVANCE, nsfw=False):
        """
        search for an image file

        :param pattern: pattern to search on
        :type pattern: str
        :param sortby: sort by ...(use SEARCH_* constants)
        :param nsfw: include non-suitable for work images if True
        :type nsfw: bool
        :rtype: iter[:class:`BaseImage`]
        """
        return self.search_file(pattern, sortby)

    def get_image(self, _id):
        """
        Get an image file from an ID.

        :param id: image file ID
        :type id: str
        :rtype: :class:`BaseImage`]
        """
        return self.get_file(_id)
