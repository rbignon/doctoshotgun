# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Romain Bignon, Christophe Benz, Noé Rubinstein
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


from woob.capabilities.image import BaseImage as CIBaseImage, Thumbnail
from woob.tools.compat import unicode
from .base import Capability, BaseObject, NotLoaded, Field, StringField, \
                  IntField, FloatField, Enum
from .date import DateField


__all__ = ['BaseGallery', 'BaseImage', 'CapGallery']


class BaseGallery(BaseObject):
    """
    Represents a gallery.

    This object has to be inherited to specify how to calculate the URL of the gallery from its ID.
    """
    title =         StringField('Title of gallery')
    description =   StringField('Description of gallery')
    cardinality =   IntField('Cardinality of gallery')
    date =          DateField('Date of gallery')
    rating =        FloatField('Rating of this gallery')
    rating_max =    FloatField('Max rating available')
    thumbnail =     Field('Thumbnail', Thumbnail)

    def __init__(self, _id, title=NotLoaded, url=NotLoaded, cardinality=NotLoaded, date=NotLoaded,
                 rating=NotLoaded, rating_max=NotLoaded, thumbnail=NotLoaded, thumbnail_url=None, nsfw=False):
        super(BaseGallery, self).__init__(unicode(_id), url)

        self.title = title
        self.date = date
        self.rating = rating
        self.rating_max = rating_max
        self.thumbnail = thumbnail

    @classmethod
    def id2url(cls, _id):
        """Overloaded in child classes provided by backends."""
        raise NotImplementedError()

    @property
    def page_url(self):
        """
        Get URL to page of this gallery.
        """
        return self.id2url(self.id)

    def iter_image(self):
        """
        Iter images.
        """
        raise NotImplementedError()


class BaseImage(CIBaseImage):
    """
    Base class for images.
    """
    index =     IntField('Usually page number')
    gallery =   Field('Reference to the Gallery object', BaseGallery)

    def __init__(self, _id=u'', index=None, thumbnail=NotLoaded, url=NotLoaded,
            ext=NotLoaded, gallery=None):

        super(BaseImage, self).__init__(unicode(_id), url)

        self.index = index
        self.thumbnail = thumbnail
        self.ext = ext
        self.gallery = gallery

    def __unicode__(self):
        return self.url

    def __repr__(self):
        return '<Image url="%s">' % self.url

    def __iscomplete__(self):
        return self.data is not NotLoaded


class SearchSort(Enum):
    RELEVANCE = 0
    RATING = 1
    VIEWS = 2
    DATE = 3


class CapGallery(Capability):
    """
    This capability represents the ability for a website backend to provide videos.
    """
    SEARCH_RELEVANCE = SearchSort.RELEVANCE
    SEARCH_RATING = SearchSort.RATING
    SEARCH_VIEWS = SearchSort.VIEWS
    SEARCH_DATE = SearchSort.DATE

    def search_galleries(self, pattern, sortby=SEARCH_RELEVANCE):
        """
        Iter results of a search on a pattern.

        :param pattern: pattern to search on
        :type pattern: str
        :param sortby: sort by...
        :type sortby: SEARCH_*
        :rtype: :class:`BaseGallery`
        """
        raise NotImplementedError()

    def get_gallery(self, _id):
        """
        Get gallery from an ID.

        :param _id: the gallery id. It can be a numeric ID, or a page url, or so.
        :type _id: str
        :rtype: :class:`Gallery`
        """
        raise NotImplementedError()

    def iter_gallery_images(self, gallery):
        """
        Iterate images from a Gallery.

        :type gallery: BaseGallery
        :rtype: iter(BaseImage)
        """
        raise NotImplementedError()
