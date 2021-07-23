# -*- coding: utf-8 -*-

# Copyright(C) 2016 Romain Bignon
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


from threading import RLock
from collections import defaultdict


__all__ = ['RequestsManager']


class RequestsManager(object):
    def __init__(self):
        self.callbacks = defaultdict(lambda: lambda *args, **kwargs: None)
        self.lock = RLock()

    def request(self, name, *args, **kwargs):
        with self.lock:
            return self.callbacks[name](*args, **kwargs)

    def register(self, name, callback):
        self.callbacks[name] = callback
