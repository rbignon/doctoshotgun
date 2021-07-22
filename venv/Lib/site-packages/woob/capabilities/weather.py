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


from datetime import datetime, date

from woob.tools.compat import basestring, unicode

from .base import Capability, BaseObject, Field, FloatField, \
                  StringField, IntField, UserError, NotLoaded, EnumField, Enum
from .date import DateField

__all__ = [
    'Forecast', 'Current', 'City', 'CityNotFound', 'Temperature', 'CapWeather',
    'BaseWeather', 'Direction', 'Precipitation',
]


class Direction(Enum):
    S = 'South'
    N = 'North'
    E = 'East'
    W = 'West'
    SE = 'Southeast'
    SW = 'Southwest'
    NW = 'Northwest'
    NE = 'Northeast'
    SSE = 'South-Southeast'
    SSW = 'South-Southwest'
    NNW = 'North-Northwest'
    NNE = 'North-Northeast'
    ESE = 'East-Southeast'
    ENE = 'East-Northeast'
    WSW = 'West-Southwest'
    WNW = 'West-Northwest'


# METAR keys
class Precipitation(Enum):
    RA = 'Rain'
    SN = 'Snow'
    GR = 'Hail'
    PL = 'Ice pellets'
    GS = 'Small hail'
    DZ = 'Drizzle'
    IC = 'Ice cristals'
    SG = 'Small grains'
    UP = 'Unknown precipiation'


class Temperature(BaseObject):
    value =      FloatField('Temperature value')
    unit =       StringField('Input unit')

    def __init__(self, value=NotLoaded, unit = u'', url=None):
        super(Temperature, self).__init__(unicode(value), url)
        self.value = value
        if unit not in [u'C', u'F']:
            unit = u''
        self.unit = unit

    def asfahrenheit(self):
        if not self.unit:
            return u'%s' % int(round(self.value))
        elif self.unit == 'F':
            return u'%s °F' % int(round(self.value))
        else:
            return u'%s °F' % int(round((self.value * 9.0 / 5.0) + 32))

    def ascelsius(self):
        if not self.unit:
            return u'%s' % int(round(self.value))
        elif self.unit == 'C':
            return u'%s °C' % int(round(self.value))
        else:
            return u'%s °C' % int(round((self.value - 32.0) * 5.0 / 9.0))

    def __repr__(self):
        if self.value is not None and self.unit:
            return '%r %r' % (self.value, self.unit)
        return ''


class BaseWeather(BaseObject):
    precipitation = EnumField('Precipitation type', Precipitation)
    precipitation_probability = FloatField('Probability of precipitation (ratio)')

    wind_direction = EnumField('Wind direction', Direction)
    wind_speed = FloatField('Wind speed (in km/h)')

    humidity = FloatField('Relative humidity (ratio)')
    pressure = FloatField('Atmospheric pressure (in hPa)')

    visibility = FloatField('Horizontal visibility distance (in km)')
    cloud = IntField('Cloud coverage (in okta (0-8))')


class Forecast(BaseWeather):
    """
    Weather forecast.
    """
    date =      Field('Date for the forecast', datetime, date, basestring)
    low =       Field('Low temperature', Temperature)
    high =      Field('High temperature', Temperature)
    text =      StringField('Comment on forecast')

    def __init__(self, date=NotLoaded, low=None, high=None, text=None, unit=None, url=None):
        super(Forecast, self).__init__(unicode(date), url)
        self.date = date
        self.low = Temperature(low, unit)
        self.high = Temperature(high, unit)
        self.text = text


class Current(BaseWeather):
    """
    Current weather.
    """
    date =      DateField('Date of measure')
    text =      StringField('Comment about current weather')
    temp =      Field('Current temperature', Temperature)

    def __init__(self, date=NotLoaded, temp=None, text=None, unit=None, url=None):
        super(Current, self).__init__(unicode(date), url)
        self.date = date
        self.text = text
        self.temp = Temperature(temp, unit)


class City(BaseObject):
    """
    City where to find weather.
    """
    name =      StringField('Name of city')

    def __init__(self, id='', name=None, url=None):
        super(City, self).__init__(id, url)
        self.name = name


class CityNotFound(UserError):
    """
    Raised when a city is not found.
    """


class CapWeather(Capability):
    """
    Capability for weather websites.
    """

    def iter_city_search(self, pattern):
        """
        Look for a city.

        :param pattern: pattern to search
        :type pattern: str
        :rtype: iter[:class:`City`]
        """
        raise NotImplementedError()

    def get_current(self, city_id):
        """
        Get current weather.

        :param city_id: ID of the city
        :rtype: :class:`Current`
        """
        raise NotImplementedError()

    def iter_forecast(self, city_id):
        """
        Iter forecasts of a city.

        :param city_id: ID of the city
        :rtype: iter[:class:`Forecast`]
        """
        raise NotImplementedError()
