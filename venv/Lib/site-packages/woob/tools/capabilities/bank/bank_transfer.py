# -*- coding: utf-8 -*-

# Copyright(C) 2009-2020  Romain Bignon
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


__all__ = [
    'sorted_transfers',
]


def sorted_transfers(iterable):
    """Sort an iterable of transfers in reverse chronological order"""
    return sorted(iterable, reverse=True, key=lambda tr: (tr.creation_date, tr.exec_date))
