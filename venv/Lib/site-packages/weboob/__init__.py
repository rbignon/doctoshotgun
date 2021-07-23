# -*- coding: utf-8 -*-

# Copyright(C) 2010-2021 Romain Bignon
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

import sys
from importlib.abc import MetaPathFinder, Loader
import importlib

import woob


__title__ = woob.__title__
__version__ = woob.__version__
__author__ = woob.__author__
__copyright__ = woob.__copyright__


# Use case: the core does "import woob.x" but some app does "import weboob.x".
# If we merely set __path__, python will generate different modules
# though they have the same path. So the references will be different,
# isinstance(woob.X(), weboob.X) will fail, etc.
# Instead, we must return the same module to prevent Python from generating
# another one.
# Trick found at https://stackoverflow.com/a/56872393

class AliasLoader(Loader):
    def module_repr(self, module):
        return repr(module)

    def load_module(self, fullname):
        new_name = fullname.replace("weboob", "woob")
        module = importlib.import_module(new_name)
        sys.modules[fullname] = module
        return module


class AliasImporter(MetaPathFinder):
    def find_module(self, fullname, path=None):
        root_name, _, __ = fullname.partition(".")
        if root_name == "weboob":
            return AliasLoader()


sys.meta_path.insert(0, AliasImporter())
