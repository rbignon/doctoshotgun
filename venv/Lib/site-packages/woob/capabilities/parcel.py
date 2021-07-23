# -*- coding: utf-8 -*-

# Copyright(C) 2013 Romain Bignon
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


from .base import Capability, BaseObject, Field, StringField, UserError, Enum
from .date import DateField


class Event(BaseObject):
    date = DateField('Date')
    activity = StringField('Activity')
    location = StringField('Location')

    def __repr__(self):
        return '<Event date=%r activity=%r location=%r>' % (self.date, self.activity, self.location)


class ParcelState(Enum):
    UNKNOWN = 0
    PLANNED = 1
    IN_TRANSIT = 2
    ARRIVED = 3


class Parcel(BaseObject):
    STATUS_UNKNOWN = ParcelState.UNKNOWN
    STATUS_PLANNED = ParcelState.PLANNED
    STATUS_IN_TRANSIT = ParcelState.IN_TRANSIT
    STATUS_ARRIVED = ParcelState.ARRIVED

    arrival = DateField('Scheduled arrival date')
    status = Field('Status of parcel', int, default=STATUS_UNKNOWN)
    info = StringField('Information about parcel status')
    history = Field('History', list)


class CapParcel(Capability):
    def get_parcel_tracking(self, id):
        """
        Get information abouut a parcel.

        :param id: ID of the parcel
        :type id: :class:`str`
        :rtype: :class:`Parcel`
        :raises: :class:`ParcelNotFound`
        """

        raise NotImplementedError()


class ParcelNotFound(UserError):
    """
    Raised when a parcell is not found.
    It can be an user error, or an expired parcel
    """

    def __init__(self, msg='Parcel not found'):
        super(ParcelNotFound, self).__init__(msg)
