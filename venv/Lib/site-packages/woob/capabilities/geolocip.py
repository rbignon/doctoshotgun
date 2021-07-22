# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Romain Bignon
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


from .base import Capability, BaseObject, StringField, Field
from .address import GeoCoordinates, PostalAddress, compat_field


__all__ = ['IpLocation', 'CapGeolocIp']


class IpLocation(BaseObject):
    """
    Represents the location of an IP address.
    """

    address = Field('Address', PostalAddress)
    geo = Field('Geolocation', GeoCoordinates)

    osmlink =   StringField('Link to OpenStreetMap location page')
    host =      StringField('Hostname')
    tld =       StringField('Top Level Domain')
    isp =       StringField('Internet Service Provider')

    lt = compat_field('geo', 'latitude')
    lg = compat_field('geo', 'longitude')

    city = compat_field('address', 'city')
    region = compat_field('address', 'region')
    zipcode = compat_field('address', 'postal_code')
    country = compat_field('address', 'country')


class CapGeolocIp(Capability):
    """
    Access information about IP addresses database.
    """

    def get_location(self, ipaddr):
        """
        Get location of an IP address.

        :param ipaddr: IP address
        :type ipaddr: str
        :rtype: :class:`IpLocation`
        """
        raise NotImplementedError()
