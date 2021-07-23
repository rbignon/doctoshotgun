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


class ConfigError(Exception):
    pass


class IConfig(object):
    """
    Interface for config storage.

    Config stores keys and values. Each key is a path of components, allowing
    to group multiple options.
    """

    def load(self, default={}):
        """
        Load config.

        :param default: default values for the config
        :type default: dict[:class:`str`]
        """
        raise NotImplementedError()

    def save(self):
        """Save config."""
        raise NotImplementedError()

    def set(self, *args):
        """
        Set a config value.

        :param args: all args except the last arg are the path of the option key.
        :type args: str or object
        """
        raise NotImplementedError()

    def delete(self, *args):
        """
        Delete an option from config.

        :param args: path to the option key.
        :type args: str
        """
        raise NotImplementedError()

    def get(self, *args, **kwargs):
        """
        Get the value of an option.

        :param args: path of the option key.
        :param default: if specified, default value when path is not found
        """
        raise NotImplementedError()

    def __enter__(self):
        self.load()

    def __exit__(self, t, v, tb):
        self.save()
