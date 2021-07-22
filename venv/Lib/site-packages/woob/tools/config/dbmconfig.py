# -*- coding: utf-8 -*-

# Copyright(C) 2016-2019 Edouard Lefebvre du Prey, Laurent Bachelier
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


import yaml

from .iconfig import ConfigError, IConfig
from .yamlconfig import WoobDumper

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

try:
    import anydbm as dbm
except ImportError:
    import dbm


__all__ = ['DBMConfig']


class DBMConfig(IConfig):
    def __init__(self, path):
        self.path = path

    def load(self, default={}):
        self.storage = dbm.open(self.path, 'c')

    def save(self):
        if hasattr(self.storage, 'sync'):
            self.storage.sync()

    def get(self, *args, **kwargs):
        key = '.'.join(args)
        try:
            value = self.storage[key]
            value = yaml.load(value, Loader=Loader)
        except KeyError:
            if 'default' in kwargs:
                value = kwargs.get('default')
            else:
                raise ConfigError()
        except TypeError:
            raise ConfigError()
        return value

    def set(self, *args):
        key = '.'.join(args[:-1])
        value = args[-1]
        try:
            self.storage[key] = yaml.dump(value, None, Dumper=WoobDumper, default_flow_style=False)
        except KeyError:
            raise ConfigError()
        except TypeError:
            raise ConfigError()

    def delete(self, *args):
        key = '.'.join(args)
        try:
            del self.storage[key]
        except KeyError:
            raise ConfigError()
        except TypeError:
            raise ConfigError()
