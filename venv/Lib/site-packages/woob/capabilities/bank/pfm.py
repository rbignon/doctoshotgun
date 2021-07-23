# -*- coding: utf-8 -*-

# Copyright(C) 2010-2016 Romain Bignon
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

from .base import CapBank

__all__ = [
    'CapBankMatching', 'AccountDiff',
]


class AccountDiff:
    """Difference between 2 accounts lists
    """

    def __init__(self):
        self.matching = []
        """List of new-old account pairs matching together"""

        self.obsolete = []
        """Accounts from the previous state that are not present in the latest state"""

        self.new = []
        """Accounts from the latest state that are not present in the previous state"""

        self.unknown = []


class CapBankMatching(CapBank):
    """
    Capability for matching data between synchronisations.

    This is mostly useful for PFM which have to compare states across time.
    For example, a PFM has to compare accounts freshly returned to accounts
    returned in a previous sync.
    """

    def diff_accounts(self, new_accounts, old_accounts):
        """Compute difference between 2 states of accounts lists.

        This function will remove elements from `new_accounts` and
        `old_accounts` as they are matched and put in the resulting
        `AccountDiff` object.

        Limitations may apply to the fields of `old_accounts` objects, see
        documentation of.

        :param new_accounts: list of freshly fetched, not-matched-yet accounts
        :type new_accounts: iter[:class:`Account`]
        :param old_accounts: list of old, not-matched-yet accounts
        :type old_accounts: iter[:class:`Account`]
        :rtype: iter[:class:`AccountDiff`]
        """

        diff = AccountDiff()
        for new_account in new_accounts:
            old_account = self.match_account(new_account, old_accounts)
            if old_account:
                old_accounts.remove(old_account)
                new_accounts.remove(new_account)
                diff.matching.append((new_account, old_account))
        return diff

    def match_account(self, account, old_accounts):
        """Search an account in `old_accounts` corresponding to `account`.

        `old_accounts` is a list of accounts found in a previous
        synchronisation.
        However, they may not be the exact same objects but only reconstructed
        objects with the same data, although even it could be partial.
        For example, they may have been marshalled, sometimes loosely, thus some
        attributes may be missing (like `_private` attributes) or unset (some
        PFM may choose not to even save all attributes).
        Also, `old_accounts` may not contain all accounts from previous state,
        but only accounts which have not been matched yet.

        :param account: fresh account to search for
        :type account: :class:`Account`
        :param old_accounts: candidates accounts from previous sync
        :type old_accounts: iter[:class:`Account`]
        :return: the corresponding account from `old_accounts`, or `None` if none matches
        :rtype: :class:`Account`
        """

        raise NotImplementedError()
