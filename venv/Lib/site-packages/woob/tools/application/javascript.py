# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Christophe Benz
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


__all__ = ['get_javascript']


def get_javascript(name, load_order=('local', 'web'), minified=True):
    if name == 'jquery':
        for src in load_order:
            if src == 'local':
                # try Debian paths
                if minified:
                    filepath = '/usr/share/javascript/jquery/jquery.min.js'
                else:
                    filepath = '/usr/share/javascript/jquery/jquery.js'
                if os.path.exists(filepath):
                    return filepath
            elif src == 'web':
                # return Google-hosted URLs
                if minified:
                    return 'http://ajax.googleapis.com/ajax/libs/jquery/1.4.2/jquery.min.js'
                else:
                    return 'http://ajax.googleapis.com/ajax/libs/jquery/1.4.2/jquery.js'
    elif name == 'tablesorter':
        if 'web' in load_order:
            if minified:
                return 'http://tablesorter.com/jquery.tablesorter.min.js'
            else:
                return 'http://tablesorter.com/jquery.tablesorter.js'
    return None
