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


from woob.capabilities.base import BaseObject, StringField, NotLoaded

__all__ = ['StreamInfo']


class StreamInfo(BaseObject):
    """
    Stream related information.
    """
    who = StringField('Who is currently on air')
    what = StringField('What is currently on air')

    def __iscomplete__(self):
        return self.who is not NotLoaded or self.what is not NotLoaded

    def __unicode__(self):
        if self.who:
            return u'%s - %s' % (self.who, self.what)
        else:
            return self.what
