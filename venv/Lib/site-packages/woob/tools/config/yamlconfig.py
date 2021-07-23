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


import os
import tempfile
import sys

import woob.tools.date
import yaml

from .iconfig import ConfigError, IConfig
from .util import LOGGER, replace

try:
    from yaml import CLoader as Loader
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Loader
    from yaml import Dumper


__all__ = ['YamlConfig']


class WoobDumper(Dumper):
    pass


WeboobDumper = WoobDumper


class WoobNoAliasDumper(WoobDumper):
    def ignore_aliases(self, data):
        return True


WeboobNoAliasDumper = WoobNoAliasDumper


WoobDumper.add_representer(woob.tools.date.date,
                           WoobDumper.represent_date)

WoobDumper.add_representer(woob.tools.date.datetime,
                           WoobDumper.represent_datetime)


class YamlConfig(IConfig):
    DUMPER = WoobDumper
    LOADER = Loader

    def __init__(self, path):
        self.path = path
        self.values = {}

    def load(self, default={}):
        self.values = default.copy()

        LOGGER.debug(u'Loading configuration file: %s.' % self.path)
        try:
            with open(self.path, 'r') as f:
                self.values = yaml.load(f, Loader=self.LOADER)
            LOGGER.debug(u'Configuration file loaded: %s.' % self.path)
        except IOError:
            self.save()
            LOGGER.debug(u'Configuration file created with default values: %s.' % self.path)

        if self.values is None:
            self.values = {}

    def save(self):
        # write in a temporary file to avoid corruption problems
        if sys.version_info.major == 2:
            f = tempfile.NamedTemporaryFile(dir=os.path.dirname(self.path), delete=False)
        else:
            f = tempfile.NamedTemporaryFile(mode='w', dir=os.path.dirname(self.path), delete=False, encoding='utf-8')
        with f:
            yaml.dump(self.values, f, Dumper=self.DUMPER, default_flow_style=False)
        replace(f.name, self.path)
        LOGGER.debug(u'Configuration file saved: %s.' % self.path)

    def get(self, *args, **kwargs):
        v = self.values
        for a in args[:-1]:
            try:
                v = v[a]
            except KeyError:
                if 'default' in kwargs:
                    return kwargs['default']
                else:
                    raise ConfigError()
            except TypeError:
                raise ConfigError()

        try:
            v = v[args[-1]]
        except KeyError:
            v = kwargs.get('default')

        return v

    def set(self, *args):
        v = self.values
        for a in args[:-2]:
            try:
                v = v[a]
            except KeyError:
                v[a] = {}
                v = v[a]
            except TypeError:
                raise ConfigError()

        v[args[-2]] = args[-1]

    def delete(self, *args):
        v = self.values
        for a in args[:-1]:
            try:
                v = v[a]
            except KeyError:
                return
            except TypeError:
                raise ConfigError()

        v.pop(args[-1], None)
