# -*- coding: utf-8 -*-

# Copyright(C) 2012 Romain Bignon
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


from .base import Capability, BaseObject, Field, IntField, DecimalField, \
                  StringField, BytesField, Enum, EnumField, UserError
from .date import DateField
from .address import compat_field, PostalAddress
from .image import BaseImage

__all__ = [
    'CapHousing', 'Housing', 'Query', 'City', 'UTILITIES', 'ENERGY_CLASS',
    'POSTS_TYPES', 'ADVERT_TYPES', 'HOUSE_TYPES', 'TypeNotSupported',
    'HousingPhoto',
]


class TypeNotSupported(UserError):
    """
    Raised when query type is not supported
    """

    def __init__(self,
                 msg='This type of house is not supported by this module'):
        super(TypeNotSupported, self).__init__(msg)


class HousingPhoto(BaseImage):
    """
    Photo of a housing.
    """
    data =      BytesField('Data of photo')

    def __init__(self, url):
        super(HousingPhoto, self).__init__(url.split('/')[-1], url)

    def __unicode__(self):
        return self.url

    def __repr__(self):
        return '<HousingPhoto %r data=%do url=%r>' % (self.id, len(self.data) if self.data else 0, self.url)


class UTILITIES(Enum):
    INCLUDED = u'C.C.'
    EXCLUDED = u'H.C.'
    UNKNOWN = u''


class ENERGY_CLASS(Enum):
    A = u'A'
    B = u'B'
    C = u'C'
    D = u'D'
    E = u'E'
    F = u'F'
    G = u'G'


class POSTS_TYPES(Enum):
    RENT = u'RENT'
    SALE = u'SALE'
    SHARING = u'SHARING'
    FURNISHED_RENT = u'FURNISHED_RENT'
    VIAGER = u'VIAGER'


class ADVERT_TYPES(Enum):
    PROFESSIONAL = u'Professional'
    PERSONAL = u'Personal'


class HOUSE_TYPES(Enum):
    APART = u'Apartment'
    HOUSE = u'House'
    PARKING = u'Parking'
    LAND = u'Land'
    OTHER = u'Other'
    UNKNOWN = u'Unknown'


class Housing(BaseObject):
    """
    Content of a housing.
    """
    type = EnumField('Type of housing (rent, sale, sharing)',
                     POSTS_TYPES)
    advert_type = EnumField('Type of advert (professional or personal)',
                            ADVERT_TYPES)
    house_type = EnumField(u'Type of house (apartment, house, parking, …)',
                           HOUSE_TYPES)
    title = StringField('Title of housing')
    area = DecimalField('Area of housing, in m2')
    cost = DecimalField('Cost of housing')
    price_per_meter = DecimalField('Price per meter ratio')
    currency = StringField('Currency of cost')
    utilities = EnumField('Utilities included or not', UTILITIES)
    date = DateField('Date when the housing has been published')
    address = Field('Location of housing', PostalAddress)
    station = StringField('What metro/bus station next to housing')
    text = StringField('Text of the housing')
    phone = StringField('Phone number to contact')
    photos = Field('List of photos', list)
    rooms = DecimalField('Number of rooms')
    bedrooms = DecimalField('Number of bedrooms')
    details = Field('Key/values of details', dict)
    DPE = EnumField('DPE (Energy Performance Certificate)', ENERGY_CLASS)
    GES = EnumField('GES (Greenhouse Gas Emissions)', ENERGY_CLASS)

    location = compat_field('address', 'full_address')


class Query(BaseObject):
    """
    Query to find housings.
    """
    type = EnumField('Type of housing to find (POSTS_TYPES constants)',
                     POSTS_TYPES)
    cities = Field('List of cities to search in', list, tuple)
    area_min = IntField('Minimal area (in m2)')
    area_max = IntField('Maximal area (in m2)')
    cost_min = IntField('Minimal cost')
    cost_max = IntField('Maximal cost')
    nb_rooms = IntField('Number of rooms')
    house_types = Field('List of house types', list, tuple, default=list(HOUSE_TYPES))
    advert_types = Field('List of advert types to filter on', list, tuple,
                         default=list(ADVERT_TYPES))


class City(BaseObject):
    """
    City.
    """
    name = StringField('Name of city')


class CapHousing(Capability):
    """
    Capability of websites to search housings.
    """

    def search_housings(self, query):
        """
        Search housings.

        :param query: search query
        :type query: :class:`Query`
        :rtype: iter[:class:`Housing`]
        """
        raise NotImplementedError()

    def get_housing(self, housing):
        """
        Get an housing from an ID.

        :param housing: ID of the housing
        :type housing: str
        :rtype: :class:`Housing` or None if not found.
        """
        raise NotImplementedError()

    def search_city(self, pattern):
        """
        Search a city from a pattern.

        :param pattern: pattern to search
        :type pattern: str
        :rtype: iter[:class:`City`]
        """
        raise NotImplementedError()
