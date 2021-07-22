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


from binascii import crc32
import re

from woob.capabilities.base import (
    BaseObject, Field, StringField, DecimalField, IntField,
    UserError, Currency, NotAvailable, EnumField, Enum,
    empty, find_object
)
from woob.capabilities.date import DateField
from woob.capabilities.collection import CapCollection
from woob.tools.compat import unicode


__all__ = [
    'CapBank', 'BaseAccount', 'Account', 'Loan', 'Transaction', 'AccountNotFound',
    'AccountType', 'AccountOwnership',
]


class ObjectNotFound(UserError):
    pass


class AccountNotFound(ObjectNotFound):
    """
    Raised when an account is not found.
    """

    def __init__(self, msg='Account not found'):
        super(AccountNotFound, self).__init__(msg)


class BaseAccount(BaseObject, Currency):
    """
    Generic class aiming to be parent of :class:`Recipient` and
    :class:`Account`.
    """
    label =          StringField('Pretty label')
    currency =       StringField('Currency', default=None)
    bank_name =      StringField('Bank Name', mandatory=False)

    def __init__(self, id='0', url=None):
        super(BaseAccount, self).__init__(id, url)

    @property
    def currency_text(self):
        return Currency.currency2txt(self.currency)

    @property
    def ban(self):
        """ Bank Account Number part of IBAN"""
        if not self.iban:
            return NotAvailable
        return self.iban[4:]


class AccountType(Enum):
    UNKNOWN          = 0
    CHECKING         = 1
    "Transaction, everyday transactions"
    SAVINGS          = 2
    "Savings/Deposit, can be used for every banking"
    DEPOSIT          = 3
    "Term of Fixed Deposit, has time/amount constraints"
    LOAN             = 4
    "Loan account"
    MARKET           = 5
    "Stock market or other variable investments"
    JOINT            = 6
    "Joint account"
    CARD             = 7
    "Card account"
    LIFE_INSURANCE   = 8
    "Life insurances"
    PEE              = 9
    "Employee savings PEE"
    PERCO            = 10
    "Employee savings PERCO"
    ARTICLE_83       = 11
    "Article 83"
    RSP              = 12
    "Employee savings RSP"
    PEA              = 13
    "Share savings"
    CAPITALISATION   = 14
    "Life Insurance capitalisation"
    PERP             = 15
    "Retirement savings"
    MADELIN          = 16
    "Complementary retirement savings"
    MORTGAGE         = 17
    "Mortgage"
    CONSUMER_CREDIT  = 18
    "Consumer credit"
    REVOLVING_CREDIT = 19
    "Revolving credit"
    PER = 20
    "Pension plan PER"
    REAL_ESTATE = 21
    "Real estate investment such as SCPI, OPCI, SCI"


class AccountOwnerType(object):
    """
    Specifies the usage of the account
    """
    PRIVATE = u'PRIV'
    """private personal account"""
    ORGANIZATION = u'ORGA'
    """professional account"""
    ASSOCIATION = u'ASSO'
    """association account"""


class AccountOwnership(object):
    """
    Relationship between the credentials owner (PSU) and the account
    """
    OWNER = u'owner'
    """The PSU is the account owner"""
    CO_OWNER = u'co-owner'
    """The PSU is the account co-owner"""
    ATTORNEY = u'attorney'
    """The PSU is the account attorney"""


class Account(BaseAccount):
    """
    Bank account.
    """
    TYPE_UNKNOWN          = AccountType.UNKNOWN
    TYPE_CHECKING         = AccountType.CHECKING
    TYPE_SAVINGS          = AccountType.SAVINGS
    TYPE_DEPOSIT          = AccountType.DEPOSIT
    TYPE_LOAN             = AccountType.LOAN
    TYPE_MARKET           = AccountType.MARKET
    TYPE_JOINT            = AccountType.JOINT
    TYPE_CARD             = AccountType.CARD
    TYPE_LIFE_INSURANCE   = AccountType.LIFE_INSURANCE
    TYPE_PEE              = AccountType.PEE
    TYPE_PERCO            = AccountType.PERCO
    TYPE_ARTICLE_83       = AccountType.ARTICLE_83
    TYPE_RSP              = AccountType.RSP
    TYPE_PEA              = AccountType.PEA
    TYPE_CAPITALISATION   = AccountType.CAPITALISATION
    TYPE_PERP             = AccountType.PERP
    TYPE_MADELIN          = AccountType.MADELIN
    TYPE_MORTGAGE         = AccountType.MORTGAGE
    TYPE_CONSUMER_CREDIT  = AccountType.CONSUMER_CREDIT
    TYPE_REVOLVING_CREDIT = AccountType.REVOLVING_CREDIT
    TYPE_PER              = AccountType.PER
    TYPE_REAL_ESTATE      = AccountType.REAL_ESTATE

    type =      EnumField('Type of account', AccountType, default=TYPE_UNKNOWN)
    owner_type = StringField('Usage of account')  # cf AccountOwnerType class
    balance =   DecimalField('Balance on this bank account')
    coming =    DecimalField('Sum of coming movements')
    iban =      StringField('International Bank Account Number', mandatory=False)
    ownership = StringField('Relationship between the credentials owner (PSU) and the account')  # cf AccountOwnership class

    # card attributes
    paydate =   DateField('For credit cards. When next payment is due.')
    paymin =    DecimalField('For credit cards. Minimal payment due.')
    cardlimit = DecimalField('For credit cards. Credit limit.')

    number =    StringField('Shown by the bank to identify your account ie XXXXX7489')

    # Wealth accounts (market, life insurance...)
    valuation_diff = DecimalField('+/- values total')
    valuation_diff_ratio = DecimalField('+/- values ratio')

    # Employee savings (PERP, PERCO, Article 83...)
    company_name = StringField('Name of the company of the stock - only for employee savings')

    # parent account
    #  - A checking account parent of a card account
    #  - A checking account parent of a recurring loan account
    #  - An investment account parent of a liquidity account
    #  - ...
    parent = Field('Parent account', BaseAccount)

    opening_date = DateField('Date when the account contract was created on the bank')

    def __repr__(self):
        return "<%s id=%r label=%r>" % (type(self).__name__, self.id, self.label)

    # compatibility alias
    @property
    def valuation_diff_percent(self):
        return self.valuation_diff_ratio

    @valuation_diff_percent.setter
    def valuation_diff_percent(self, value):
        self.valuation_diff_ratio = value


class Loan(Account):
    """
    Account type dedicated to loans and credits.
    """

    name = StringField('Person name')
    account_label = StringField('Label of the debited account')
    insurance_label = StringField('Label of the insurance')

    total_amount = DecimalField('Total amount loaned')
    available_amount = DecimalField('Amount available') # only makes sense for revolving credit
    used_amount = DecimalField('Amount already used') # only makes sense for revolving credit

    subscription_date = DateField('Date of subscription of the loan')
    maturity_date = DateField('Estimated end date of the loan')
    duration = IntField('Duration of the loan given in months')
    rate = DecimalField('Monthly rate of the loan')

    nb_payments_left = IntField('Number of payments still due')
    nb_payments_done = IntField('Number of payments already done')
    nb_payments_total = IntField('Number total of payments')

    last_payment_amount = DecimalField('Amount of the last payment done')
    last_payment_date = DateField('Date of the last payment done')
    next_payment_amount = DecimalField('Amount of next payment')
    next_payment_date = DateField('Date of the next payment')


class TransactionType(Enum):
    UNKNOWN       = 0
    TRANSFER      = 1
    ORDER         = 2
    CHECK         = 3
    DEPOSIT       = 4
    PAYBACK       = 5
    WITHDRAWAL    = 6
    CARD          = 7
    LOAN_PAYMENT  = 8
    BANK          = 9
    CASH_DEPOSIT  = 10
    CARD_SUMMARY  = 11
    DEFERRED_CARD = 12


class Transaction(BaseObject):
    """
    Bank transaction.
    """
    TYPE_UNKNOWN       = TransactionType.UNKNOWN
    TYPE_TRANSFER      = TransactionType.TRANSFER
    TYPE_ORDER         = TransactionType.ORDER
    TYPE_CHECK         = TransactionType.CHECK
    TYPE_DEPOSIT       = TransactionType.DEPOSIT
    TYPE_PAYBACK       = TransactionType.PAYBACK
    TYPE_WITHDRAWAL    = TransactionType.WITHDRAWAL
    TYPE_CARD          = TransactionType.CARD
    TYPE_LOAN_PAYMENT  = TransactionType.LOAN_PAYMENT
    TYPE_BANK          = TransactionType.BANK
    TYPE_CASH_DEPOSIT  = TransactionType.CASH_DEPOSIT
    TYPE_CARD_SUMMARY  = TransactionType.CARD_SUMMARY
    TYPE_DEFERRED_CARD = TransactionType.DEFERRED_CARD

    date =      DateField('Debit date on the bank statement')
    rdate =     DateField('Real date, when the payment has been made; usually extracted from the label or from credit card info')
    vdate =     DateField('Value date, or accounting date; usually for professional accounts')
    bdate =     DateField('Bank date, when the transaction appear on website (usually extracted from column date)')
    type =      EnumField('Type of transaction, use TYPE_* constants', TransactionType, default=TYPE_UNKNOWN)
    raw =       StringField('Raw label of the transaction')
    category =  StringField('Category of the transaction')
    label =     StringField('Pretty label')
    amount = DecimalField('Net amount of the transaction, used to compute account balance')

    card =              StringField('Card number (if any)')
    commission =        DecimalField('Commission part on the transaction (in account currency)')
    gross_amount = DecimalField('Amount of the transaction without the commission')

    # International
    original_amount = DecimalField('Original net amount (in another currency)')
    original_currency = StringField('Currency of the original amount')
    country =           StringField('Country of transaction')

    original_commission =          DecimalField('Original commission (in another currency)')
    original_commission_currency = StringField('Currency of the original commission')
    original_gross_amount = DecimalField('Original gross amount (in another currency)')

    # Financial arbitrations
    investments =       Field('List of investments related to the transaction', list, default=[])

    def __repr__(self):
        return "<Transaction date=%r label=%r amount=%r>" % (self.date, self.label, self.amount)

    def unique_id(self, seen=None, account_id=None):
        """
        Get an unique ID for the transaction based on date, amount and raw.

        :param seen: if given, the method uses this dictionary as a cache to
                     prevent several transactions with the same values to have the same
                     unique ID.
        :type seen: :class:`dict`
        :param account_id: if given, add the account ID in data used to create
                           the unique ID. Can be useful if you want your ID to be unique across
                           several accounts.
        :type account_id: :class:`str`
        :returns: an unique ID encoded in 8 length hexadecimal string (for example ``'a64e1bc9'``)
        :rtype: :class:`str`
        """
        crc = crc32(unicode(self.date).encode('utf-8'))
        crc = crc32(unicode(self.amount).encode('utf-8'), crc)
        if not empty(self.raw):
            label = self.raw
        else:
            label = self.label

        crc = crc32(re.sub('[ ]+', ' ', label).encode("utf-8"), crc)

        if account_id is not None:
            crc = crc32(unicode(account_id).encode('utf-8'), crc)

        if seen is not None:
            while crc in seen:
                crc = crc32(b"*", crc)

            seen.add(crc)

        return "%08x" % (crc & 0xffffffff)


class CapBank(CapCollection):
    """
    Capability of bank websites to see accounts and transactions.
    """

    def iter_resources(self, objs, split_path):
        """
        Iter resources.

        Default implementation of this method is to return on top-level
        all accounts (by calling :func:`iter_accounts`).

        :param objs: type of objects to get
        :type objs: tuple[:class:`BaseObject`]
        :param split_path: path to discover
        :type split_path: :class:`list`
        :rtype: iter[:class:`BaseObject`]
        """
        if Account in objs:
            self._restrict_level(split_path)

            return self.iter_accounts()

    def iter_accounts(self):
        """
        Iter accounts.

        :rtype: iter[:class:`Account`]
        """
        raise NotImplementedError()

    def get_account(self, id):
        """
        Get an account from its ID.

        :param id: ID of the account
        :type id: :class:`str`
        :rtype: :class:`Account`
        :raises: :class:`AccountNotFound`
        """
        return find_object(self.iter_accounts(), id=id, error=AccountNotFound)

    def iter_history(self, account):
        """
        Iter history of transactions on a specific account.

        :param account: account to get history
        :type account: :class:`Account`
        :rtype: iter[:class:`Transaction`]
        :raises: :class:`AccountNotFound`
        """
        raise NotImplementedError()

    def iter_coming(self, account):
        """
        Iter coming transactions on a specific account.

        :param account: account to get coming transactions
        :type account: :class:`Account`
        :rtype: iter[:class:`Transaction`]
        :raises: :class:`AccountNotFound`
        """
        raise NotImplementedError()
