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


from woob.capabilities.base import NotLoaded, NotAvailable
from .iformatter import IFormatter


__all__ = ['MultilineFormatter']


class MultilineFormatter(IFormatter):
    def __init__(self, key_value_separator=u': ', after_item=u'\n'):
        super(MultilineFormatter, self).__init__()
        self.key_value_separator = key_value_separator
        self.after_item = after_item

    def flush(self):
        pass

    def format_dict(self, item):
        result = u'\n'.join(u'%s%s' % (
            (u'%s%s' % (k, self.key_value_separator) if self.display_keys else ''), v)
            for k, v in item.items() if (v is not NotLoaded and v is not NotAvailable))
        if len(item) > 1:
            result += self.after_item
        return result
