# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012  Romain Bignon, Florent Fourcot
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


from .base import Capability, BaseObject, StringField, DecimalField, Field, UserError, empty
from .date import DateField
from .address import compat_field, GeoCoordinates, PostalAddress

__all__ = ['Gauge', 'GaugeSensor', 'GaugeMeasure', 'CapGauge', 'SensorNotFound']


class SensorNotFound(UserError):
    """
    Not found a sensor
    """


class Gauge(BaseObject):
    """
    Gauge class.
    """
    name =       StringField('Name of gauge')
    city =       StringField('City of the gauge')
    object =     StringField('What is evaluate')  # For example, name of a river
    sensors =    Field('List of sensors on the gauge', list)


class GaugeMeasure(BaseObject):
    """
    Measure of a gauge sensor.
    """
    level =     DecimalField('Level of measure')
    date =      DateField('Date of measure')
    alarm =     StringField('Alarm level')

    def __repr__(self):
        if empty(self.level):
            return "<GaugeMeasure is %s>" % self.level
        else:
            return "<GaugeMeasure level=%f alarm=%s date=%s>" % (self.level, self.alarm, self.date)


class GaugeSensor(BaseObject):
    """
    GaugeSensor class.
    """
    name =      StringField('Name of the sensor')
    unit =      StringField('Unit of values')
    forecast =  StringField('Forecast')
    location = Field('Address of the sensor', PostalAddress)
    geo = Field('Geo address of the sensor', GeoCoordinates)

    address = compat_field('location', 'full_address')
    latitude = compat_field('geo', 'latitude')
    longitude = compat_field('geo', 'longitude')

    lastvalue = Field('Last value', GaugeMeasure)
    history =   Field('Value history', list)  # lastvalue not included
    gaugeid =   StringField('Id of the gauge')

    def __repr__(self):
        return "<GaugeSensor id=%s name=%s>" % (self.id, self.name)


class CapGauge(Capability):
    def iter_gauges(self, pattern=None):
        """
        Iter gauges.

        :param pattern: if specified, used to search gauges.
        :type pattern: str
        :rtype: iter[:class:`Gauge`]
        """
        raise NotImplementedError()

    def iter_sensors(self, id, pattern=None):
        """
        Iter instrument of a gauge.

        :param: ID of the gauge
        :param pattern: if specified, used to search sensors.
        :type pattern: str
        :rtype: iter[:class:`GaugeSensor`]
        """
        raise NotImplementedError()

    def iter_gauge_history(self, id):
        """
        Get history of a gauge sensor.

        :param id: ID of the gauge sensor
        :type id: str
        :rtype: iter[:class:`GaugeMeasure`]
        """
        raise NotImplementedError()

    def get_last_measure(self, id):
        """
        Get last measures of a sensor.

        :param id: ID of the sensor.
        :type id: str
        :rtype: :class:`GaugeMeasure`
        """
        raise NotImplementedError()
