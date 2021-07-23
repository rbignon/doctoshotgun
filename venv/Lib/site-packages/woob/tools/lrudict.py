# -*- coding: utf-8 -*-

# Copyright(C) 2012-2016 woob project
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

__all__ = ['LimitedLRUDict', 'LRUDict']


class LRUDict(OrderedDict):
    """dict to store items in the order the keys were last added/fetched."""

    def __setitem__(self, key, value):
        if key in self:
            del self[key]
        super(LRUDict, self).__setitem__(key, value)

    def __getitem__(self, key):
        value = super(LRUDict, self).__getitem__(key)
        self[key] = value
        return value


class LimitedLRUDict(LRUDict):
    """dict to store only the N most recent items."""

    max_entries = 100

    def __setitem__(self, key, value):
        super(LimitedLRUDict, self).__setitem__(key, value)
        if len(self) > self.max_entries:
            self.popitem(last=False)
