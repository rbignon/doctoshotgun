# -*- coding: utf-8 -*-

# Copyright(C) 2010-2020  woob project
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

from woob.tools.capabilities.bank import AccountDiff


__all__ = ['diff_accounts']


def group_by(iterable, func):
    grouped = {}
    for obj in iterable:
        key = func(obj)
        grouped.setdefault(key, []).append(obj)
    return grouped


def match_unique(new_accounts, old_accounts, func):
    # even though it should be unique and maybe required, don't error if it's missing or not unique
    # just ignore bad groups
    new_groups = {key: accs for key, accs in group_by(new_accounts, func).items() if key and len(accs) == 1}
    old_groups = {key: accs for key, accs in group_by(old_accounts, func).items() if key and len(accs) == 1}

    for matching_key in (new_groups.keys() & old_groups.keys()):
        new = new_groups[matching_key][0]
        old = old_groups[matching_key][0]

        new_accounts.remove(new)
        old_accounts.remove(old)
        yield new, old


class IdSet:
    """A set for unhashable objects, expecting to pass the same objects"""
    def __init__(self, elements=()):
        self.container = {}
        for el in elements:
            self.add(el)

    def __iter__(self):
        return self.container.values()

    def __contains__(self, el):
        return id(el) in self.container

    def __len__(self):
        return len(self.container)

    def add(self, el):
        self.container[id(el)] = el

    def remove(self, el):
        del self.container[id(el)]

    def discard(self, el):
        try:
            self.remove(el)
        except KeyError:
            pass


def diff_accounts(backend, new_accounts, old_accounts):
    """Compare accounts between a sync and previous sync

    Tries to match accounts just fetched with accounts fetched from a previous
    run of `iter_accounts()`.

    :param backend: backend from which the objects come
    :type backend: :class:`woob.tools.backend.Module`
    :type new_accounts: iter[:class:`woob.capabilities.bank.Account`]
    :type old_accounts: iter[:class:`woob.capabilities.bank.Account`]
    :rtype: :class:`woob.capabilities.bank.AccountDiff`
    """

    new_accounts = IdSet(new_accounts)
    old_accounts = IdSet(old_accounts)

    diff = AccountDiff()
    diff.matching.extend(match_unique(new_accounts, old_accounts, lambda acc: acc.id))
    diff.matching.extend(match_unique(new_accounts, old_accounts, lambda acc: acc.iban))

    if hasattr(backend, 'diff_accounts'):
        try:
            module_diff = backend.diff_accounts(new_accounts, old_accounts)
        except NotImplementedError:
            pass
        else:
            for new, old in module_diff.matching:
                new_accounts.discard(new)
                old_accounts.discard(old)
                diff.matching.append((new, old))

            diff.obsolete = module_diff.obsolete
            diff.new = module_diff.new
            diff.unknown = module_diff.unknown

    if not new_accounts:
        diff.obsolete = list(old_accounts)
    elif old_accounts:
        diff.unknown = list(new_accounts)
    else:
        diff.new = list(new_accounts)

    return diff
