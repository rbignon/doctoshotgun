# -*- coding: utf-8 -*-

# Copyright(C) 2017  Vincent Ardisson
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

from datetime import date

from woob.capabilities.base import empty, NotLoaded
from woob.capabilities.bank import CapTransfer
from woob.capabilities.wealth import CapBankWealth
from woob.exceptions import NoAccountsException
from woob.tools.capabilities.bank.iban import is_iban_valid
from woob.tools.capabilities.bank.investments import is_isin_valid
from woob.tools.date import new_date


__all__ = ('BankStandardTest',)


def sign(n):
    if n < 0:
        return -1
    elif n > 0:
        return 1
    else:
        return 0


class BankStandardTest(object):
    """Mixin for simple tests on CapBank backends.

    This checks:
    * there are accounts
    * accounts have an id, a label and a balance
    * history is implemented (optional)
    * transactions have a date, a label and an amount
    * investments are implemented (optional)
    * investments have a label and a valuation
    * recipients are implemented (optional)
    * recipients have an id and a label
    """

    allow_notimplemented_history = False
    allow_notimplemented_coming = False
    allow_notimplemented_investments = False
    allow_notimplemented_pockets = False
    allow_notimplemented_market_orders = False
    allow_notimplemented_emitters = False
    allow_notimplemented_recipients = False

    def test_basic(self):
        try:
            accounts = list(self.backend.iter_accounts())
        except NoAccountsException:
            return

        self.assertTrue(accounts)

        for account in accounts:
            self.check_account(account)

            try:
                self.check_history(account)
            except NotImplementedError:
                self.assertTrue(self.allow_notimplemented_history, 'iter_history should not raise NotImplementedError')

            try:
                self.check_coming(account)
            except NotImplementedError:
                self.assertTrue(self.allow_notimplemented_coming, 'iter_coming should not raise NotImplementedError')

            try:
                self.check_investments(account)
            except NotImplementedError:
                self.assertTrue(self.allow_notimplemented_investments, 'iter_investment should not raise NotImplementedError')

            try:
                self.check_pockets(account)
            except NotImplementedError:
                self.assertTrue(self.allow_notimplemented_pockets, 'iter_pocket should not raise NotImplementedError')

            try:
                self.check_market_orders(account)
            except NotImplementedError:
                self.assertTrue(self.allow_notimplemented_market_orders, 'iter_market_orders should not raise NotImplementedError')

            try:
                self.check_recipients(account)
            except NotImplementedError:
                self.assertTrue(self.allow_notimplemented_recipients, 'iter_transfer_recipients should not raise NotImplementedError')

        try:
            self.check_emitters()
        except NotImplementedError:
            self.assertTrue(self.allow_notimplemented_emitters, 'iter_emitters should not raise NotImplementedError')

    def check_account(self, account):
        self.assertTrue(account.id, 'account %r has no id' % account)
        self.assertTrue(account.label, 'account %r has no label' % account)
        self.assertFalse(empty(account.balance) and empty(account.coming), 'account %r should have balance or coming' % account)
        self.assertTrue(account.type, 'account %r is untyped' % account)
        self.assertTrue(account.currency, 'account %r has no currency' % account)
        self.assertIsNot(account.number, NotLoaded, 'account %r number is not loaded' % account)
        if account.iban:
            self.assertTrue(is_iban_valid(account.iban), 'account %r IBAN is invalid: %r' % (account, account.iban))

        if account.type in (account.TYPE_LOAN,):
            self.assertLessEqual(account.balance, 0, 'loan %r should not have positive balance' % account)
        elif account.type == account.TYPE_CHECKING:
            self.assertTrue(account.iban, 'account %r has no IBAN' % account)
        elif account.type == account.TYPE_CARD:
            if not account.parent:
                self.backend.logger.warning('card account %r has no parent account', account)
            else:
                self.assertEqual(account.parent.type, account.TYPE_CHECKING, 'parent account of %r should have checking type' % account)

    def check_history(self, account):
        for tr in self.backend.iter_history(account):
            self.check_transaction(account, tr, False)

    def check_coming(self, account):
        for tr in self.backend.iter_coming(account):
            self.check_transaction(account, tr, True)

    def check_transaction(self, account, tr, coming):
        today = date.today()

        self.assertFalse(empty(tr.date), 'transaction %r has no debit date' % tr)
        if tr.amount != 0:
            self.assertTrue(tr.amount, 'transaction %r has no amount' % tr)
        self.assertFalse(empty(tr.raw) and empty(tr.label), 'transaction %r has no raw or label' % tr)

        if coming:
            self.assertGreaterEqual(new_date(tr.date), today, 'coming transaction %r should be in the future' % tr)
        else:
            self.assertLessEqual(new_date(tr.date), today, 'history transaction %r should be in the past' % tr)

        if tr.rdate:
            self.assertGreaterEqual(new_date(tr.date), new_date(tr.rdate), 'transaction %r rdate should be before date' % tr)
            self.assertLess(abs(tr.date.year - tr.rdate.year), 2, 'transaction %r date (%r) and rdate (%r) are too far away' % (tr, tr.date, tr.rdate))

        if tr.original_amount or tr.original_currency:
            self.assertTrue(tr.original_amount and tr.original_currency, 'transaction %r has missing foreign info' % tr)

        for inv in (tr.investments or []):
            self.assertTrue(inv.label, 'transaction %r investment %r has no label' % (tr, inv))
            self.assertTrue(inv.valuation, 'transaction %r investment %r has no valuation' % (tr, inv))

    def check_investments(self, account):
        if not isinstance(self.backend, CapBankWealth):
            return

        total = 0
        for inv in self.backend.iter_investment(account):
            self.check_investment(account, inv)
            if not empty(inv.valuation):
                total += inv.valuation

        if total:
            self.assertEqual(total, account.balance, 'investments total (%s) is different than account balance (%s)' % (total, account.balance))

    def check_investment(self, account, inv):
        self.assertTrue(inv.label, 'investment %r has no label' % inv)
        self.assertFalse(empty(inv.valuation), 'investment %r has no valuation' % inv)
        if inv.code and inv.code != 'XX-liquidity':
            self.assertTrue(inv.code_type, 'investment %r has code but no code type' % inv)
        if inv.code_type == inv.CODE_TYPE_ISIN and inv.code and not inv.code.startswith('XX'):
            self.assertTrue(is_isin_valid(inv.code), 'investment %r has invalid ISIN: %r' % (inv, inv.code))
        if not empty(inv.portfolio_share):
            self.assertTrue(0 < inv.portfolio_share <= 1, 'investment %r has invalid portfolio_share' % inv)

    def check_pockets(self, account):
        if not isinstance(self.backend, CapBankWealth):
            return
        for pocket in self.backend.iter_pocket(account):
            self.check_pocket(account, pocket)

    def check_pocket(self, account, pocket):
        self.assertTrue(pocket.amount, 'pocket %r has no amount' % pocket)
        self.assertTrue(pocket.label, 'pocket %r has no label' % pocket)

    def check_market_orders(self, account):
        if not isinstance(self.backend, CapBankWealth):
            return
        for market_order in self.backend.iter_market_orders(account):
            self.check_market_order(account, market_order)

    def check_market_order(self, account, market_order):
        self.assertTrue(market_order.label, 'Market order %r has no label' % market_order)
        self.assertFalse(
            empty(market_order.quantity) and empty(market_order.amount),
            'Market order %r has no quantity and no amount' % market_order
        )

    def check_recipients(self, account):
        if not isinstance(self.backend, CapTransfer):
            return
        for rcpt in self.backend.iter_transfer_recipients(account):
            self.check_recipient(account, rcpt)

    def check_recipient(self, account, rcpt):
        self.assertTrue(rcpt.id, 'recipient %r has no id' % rcpt)
        self.assertTrue(rcpt.label, 'recipient %r has no label' % rcpt)
        self.assertTrue(rcpt.category, 'recipient %r has no category' % rcpt)
        self.assertTrue(rcpt.enabled_at, 'recipient %r has no enabled_at' % rcpt)

    def check_emitters(self):
        if not isinstance(self.backend, CapTransfer):
            return
        for emitter in self.backend.iter_emitters():
            self.check_emitter(emitter)

    def check_emitter(self, emitter):
        self.assertTrue(emitter.id, 'emitter %r has no id' % emitter)
        # TODO
