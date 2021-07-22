# -*- coding: utf-8 -*-

# Copyright(C) 2020  Budget Insight
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


__all__ = ['sorted_documents', 'merge_iterators']


def sorted_documents(iterable):
    """Sort an iterable of documents in reverse chronological order"""
    return sorted(iterable, reverse=True, key=lambda doc: doc.date)


def merge_iterators(*iterables):
    """Merge documents iterators keeping sort order.

    Each iterator must already be sorted in reverse chronological order.
    """

    def keyfunc(kv):
        return kv[1].date

    its = OrderedDict((iter(it), None) for it in iterables)
    for k in list(its):
        try:
            its[k] = next(k)
        except StopIteration:
            del its[k]

    while its:
        k, v = max(its.items(), key=keyfunc)
        yield v

        try:
            its[k] = next(k)
        except StopIteration:
            del its[k]
