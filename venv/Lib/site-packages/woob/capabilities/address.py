# -*- coding: utf-8 -*-

# Copyright(C) 2010-2019 woob project
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

from .base import (
    BaseObject, StringField, DecimalField,
)


class GeoCoordinates(BaseObject):
    latitude = DecimalField('Latitude')
    longitude = DecimalField('Longitude')
    altitude = DecimalField('Altitude')

    def __repr__(self):
        return '<%s %s;%s>' % (type(self).__name__, self.latitude, self.longitude)


class PostalAddress(BaseObject):
    street = StringField('Street address')
    postal_code = StringField('Postal code')
    city = StringField('City')
    region = StringField('Region')
    country = StringField('Country')

    full_address = StringField('Full address if detailed address is not available')

    def __repr__(self):
        if self.full_address:
            return '<%s full_address=%r>' % (type(self).__name__, self.full_address)
        return '<%s street=%r postal_code=%r region=%r city=%r country=%r>' % (type(self).__name__, self.street, self.postal_code, self.region, self.city, self.country)


def compat_field(field, sub):
    @property
    def f(self):
        return getattr(self, field) and getattr(getattr(self, field), sub)

    @f.setter
    def f(self, value):
        if not getattr(self, field):
            type_ = self._fields[field].types[0]
            setattr(self, field, type_())
        setattr(getattr(self, field), sub, value)

    return f
