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


from copy import deepcopy

from .config.yamlconfig import YamlConfig


class IStorage(object):
    def load(self, what, name, default={}):
        """
        Load data from storage.
        """
        raise NotImplementedError()

    def save(self, what, name):
        """
        Write changes in storage on the disk.
        """
        raise NotImplementedError()

    def set(self, what, name, *args):
        """
        Set data in a path.
        """
        raise NotImplementedError()

    def delete(self, what, name, *args):
        """
        Delete a value or a path.
        """
        raise NotImplementedError()

    def get(self, what, name, *args, **kwargs):
        """
        Get a value or a path.
        """
        raise NotImplementedError()


class StandardStorage(IStorage):
    def __init__(self, path):
        self.config = YamlConfig(path)
        self.config.load()

    def load(self, what, name, default={}):
        d = {}
        if what not in self.config.values:
            self.config.values[what] = {}
        else:
            d = self.config.values[what].get(name, {})

        self.config.values[what][name] = deepcopy(default)
        self.config.values[what][name].update(d)

    def save(self, what, name):
        self.config.save()

    def set(self, what, name, *args):
        self.config.set(what, name, *args)

    def delete(self, what, name, *args):
        self.config.delete(what, name, *args)

    def get(self, what, name, *args, **kwargs):
        return self.config.get(what, name, *args, **kwargs)
