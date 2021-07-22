# -*- coding: utf-8 -*-

# Copyright(C) 2009-2012  Romain Bignon
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
from decimal import Decimal, InvalidOperation
import datetime
import re

from woob.capabilities.bank import Transaction, Account
from woob.capabilities import NotAvailable, NotLoaded
from woob.tools.misc import to_unicode
from woob.tools.log import getLogger
from woob.tools.date import new_datetime

from woob.exceptions import ParseError
from woob.browser.elements import TableElement, ItemElement
from woob.browser.filters.standard import Filter, CleanText, CleanDecimal
from woob.browser.filters.html import TableCell


__all__ = [
    'FrenchTransaction', 'AmericanTransaction',
    'sorted_transactions', 'merge_iterators', 'keep_only_card_transactions',
    'omit_deferred_transactions',
]


class classproperty(object):
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


def parse_with_patterns(raw, obj, patterns):
    obj.category = NotAvailable

    if '  ' in raw:
        # FIXME is this still relevant?
        obj.category, _, obj.label = [part.strip() for part in raw.partition('  ')]
    else:
        obj.label = raw

    for pattern, _type in patterns:
        m = pattern.match(raw)
        if m:
            args = m.groupdict()

            def inargs(key):
                """
                inner function to check if a key is in args,
                and is not None.
                """
                return args.get(key, None) is not None

            obj.type = _type
            labels = [args[name].strip() for name in ('text', 'text2') if inargs(name)]
            if labels:
                obj.label = ' '.join(labels)

            if inargs('category'):
                obj.category = args['category'].strip()

            # Set date from information in raw label.
            if inargs('dd') and inargs('mm'):
                dd = int(args['dd']) if args['dd'] != '00' else 1
                mm = int(args['mm'])

                if inargs('yy'):
                    yy = int(args['yy'])
                else:
                    d = obj.date
                    try:
                        d = d.replace(month=mm, day=dd)
                    except ValueError:
                        d = d.replace(year=d.year-1, month=mm, day=dd)

                    yy = d.year
                    if d > obj.date:
                        yy -= 1

                if yy < 100:
                    yy += 2000

                try:
                    if inargs('HH') and inargs('MM'):
                        obj.rdate = datetime.datetime(yy, mm, dd, int(args['HH']), int(args['MM']))
                    else:
                        obj.rdate = datetime.date(yy, mm, dd)
                except ValueError as e:
                    raise ParseError('Unable to parse date in label %r: %s' % (raw, e))

            break


class FrenchTransaction(Transaction):
    """
    Transaction with some helpers for french bank websites.
    """
    PATTERNS = []

    def __init__(self, id='', *args, **kwargs):
        super(FrenchTransaction, self).__init__(id, *args, **kwargs)
        self._logger = getLogger('FrenchTransaction')

    @classmethod
    def clean_amount(klass, text):
        """
        Clean a string containing an amount.
        """
        text = text.replace('.','').replace(',','.')
        return re.sub(u'[^\d\-\.]', '', text)

    def set_amount(self, credit='', debit=''):
        """
        Set an amount value from a string.

        Can take two strings if there are both credit and debit
        columns.
        """
        credit = self.clean_amount(credit)
        debit = self.clean_amount(debit)

        if len(debit) > 0:
            self.amount = - abs(Decimal(debit))
        elif len(credit) > 0:
            self.amount = Decimal(credit)
        else:
            self.amount = Decimal('0')

    def parse_date(self, date):
        if date is None:
            return NotAvailable

        if not isinstance(date, (datetime.date, datetime.datetime)):
            if date.isdigit() and len(date) == 8:
                date = datetime.date(int(date[4:8]), int(date[2:4]), int(date[0:2]))
            elif '/' in date:
                date = datetime.date(*reversed([int(x) for x in date.split('/')]))
        if not isinstance(date, (datetime.date, datetime.datetime)):
            self._logger.warning('Unable to parse date %r' % date)
            date = NotAvailable
        elif date.year < 100:
            date = date.replace(year=2000 + date.year)

        return date

    def parse(self, date, raw, vdate=None):
        """
        Parse date and raw strings to create datetime.date objects,
        determine the type of transaction, and create a simplified label

        When calling this method, you should have defined patterns (in the
        PATTERN class attribute) with a list containing tuples of regexp
        and the associated type, for example::

            PATTERNS = [(re.compile(r'^VIR(EMENT)? (?P<text>.*)'), FrenchTransaction.TYPE_TRANSFER),
                        (re.compile(r'^PRLV (?P<text>.*)'),        FrenchTransaction.TYPE_ORDER),
                        (re.compile(r'^(?P<text>.*) CARTE \d+ PAIEMENT CB (?P<dd>\d{2})(?P<mm>\d{2}) ?(.*)$'),
                                                                   FrenchTransaction.TYPE_CARD)
                       ]


        In regexps, you can define this patterns:

            * text: part of label to store in simplified label
            * category: part of label representing the category
            * yy, mm, dd, HH, MM: date and time parts
        """
        self.date = self.parse_date(date)
        self.vdate = self.parse_date(vdate)
        self.rdate = self.date
        self.raw = to_unicode(raw.replace(u'\n', u' ').strip())

        try:
            parse_with_patterns(self.raw, self, self.PATTERNS)
        except ParseError as e:
            self._logger.warning('Unable to date in label %r: %s' % (self.raw, e))

    @classproperty
    def TransactionElement(k):
        class _TransactionElement(ItemElement):
            klass = k

            obj_date = klass.Date(TableCell('date'))
            obj_vdate = klass.Date(TableCell('vdate', 'date'))
            obj_raw = klass.Raw(TableCell('raw'))
            obj_amount = klass.Amount(TableCell('credit'), TableCell('debit', default=''))

        return _TransactionElement

    @classproperty
    def TransactionsElement(klass):
        class _TransactionsElement(TableElement):
            col_date =       [u'Date']
            col_vdate =      [u'Valeur']
            col_raw =        [u'Opération', u'Libellé', u'Intitulé opération']
            col_credit =     [u'Crédit', u'Montant']
            col_debit =      [u'Débit']

            item = klass.TransactionElement
        return _TransactionsElement

    class Date(CleanText):
        def __call__(self, item):
            date = super(FrenchTransaction.Date, self).__call__(item)
            return date

        def filter(self, date):
            date = super(FrenchTransaction.Date, self).filter(date)
            if date is None:
                return NotAvailable

            if not isinstance(date, (datetime.date, datetime.datetime)):
                if date.isdigit() and len(date) == 8:
                    date = datetime.date(int(date[4:8]), int(date[2:4]), int(date[0:2]))
                elif '/' in date:
                    date = datetime.date(*reversed([int(x) for x in date.split('/')]))
            if not isinstance(date, (datetime.date, datetime.datetime)):
                date = NotAvailable
            elif date.year < 100:
                date = date.replace(year=2000 + date.year)

            return date

    @classmethod
    def Raw(klass, *args, **kwargs):
        patterns = klass.PATTERNS

        class Filter(CleanText):
            def __call__(self, item):
                raw = super(Filter, self).__call__(item)
                if item.obj.rdate is NotLoaded:
                    item.obj.rdate = item.obj.date

                parse_with_patterns(raw, item.obj, patterns)
                return raw

            def filter(self, text):
                text = super(Filter, self).filter(text)
                return to_unicode(text.replace(u'\n', u' ').strip())
        return Filter(*args, **kwargs)

    class Currency(CleanText):
        def filter(self, text):
            text = super(FrenchTransaction.Currency, self).filter(text)
            return Account.get_currency(text)

    class Amount(Filter):
        def __init__(self, credit, debit=None, replace_dots=True):
            self.credit_selector = credit
            self.debit_selector = debit
            self.replace_dots = replace_dots

        def __call__(self, item):
            if self.debit_selector:
                try:
                    return - abs(CleanDecimal(self.debit_selector, replace_dots=self.replace_dots)(item))
                except InvalidOperation:
                    pass

            if self.credit_selector:
                try:
                    return CleanDecimal(self.credit_selector, replace_dots=self.replace_dots)(item)
                except InvalidOperation:
                    pass

            return Decimal('0')


class AmericanTransaction(Transaction):
    """
    Transaction with some helpers for american bank websites.
    """
    @classmethod
    def clean_amount(klass, text):
        """
        Clean a string containing an amount.
        """
        # Convert "American" UUU.CC format to "French" UUU,CC format
        if re.search(r'\d\.\d\d(?: [A-Z]+)?$', text):
            text = text.replace(',', ' ').replace('.', ',')
        return FrenchTransaction.clean_amount(text)

    @classmethod
    def decimal_amount(klass, text):
        """
        Convert a string containing an amount to Decimal.
        """
        amnt = AmericanTransaction.clean_amount(text)
        return Decimal(amnt) if amnt else Decimal('0')


def sorted_transactions(iterable):
    """Sort an iterable of transactions in reverse chronological order"""
    return sorted(iterable, reverse=True, key=lambda tr: (tr.date, new_datetime(tr.rdate) if tr.rdate else datetime.datetime.min))


def merge_iterators(*iterables):
    """Merge transactions iterators keeping sort order.

    Each iterator must already be sorted in reverse chronological order.
    """

    def keyfunc(kv):
        return (kv[1].date, kv[1].rdate)

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


def keep_only_card_transactions(it, match_func=None):
    """Filter iterator to keep transactions with card types.

    This helper should typically be used when a banking site returns card and non-card
    transactions mixed on the same checking account.

    Types kept are `TYPE_DEFERRED_CARD` and `TYPE_CARD_SUMMARY`.
    Additionally, the amount is inversed for transactions with type `TYPE_CARD_SUMMARY`.
    This is because on the deferred debit card account, summaries should be positive
    as the amount is debitted from checking account to credit the card account.

    The `match_func` can be provided in case of multiple cards, to only return
    transactions of one card.

    :param match_func: optional function to filter transactions further
    :type match_func: callable or None
    """

    for tr in it:
        if tr.type == tr.TYPE_DEFERRED_CARD:
            if match_func is None or match_func(tr):
                yield tr
        elif tr.type == tr.TYPE_CARD_SUMMARY:
            if match_func is None or match_func(tr):
                tr.amount = -tr.amount
                yield tr


def omit_deferred_transactions(it):
    """Filter iterator to omit transactions with type `TYPE_DEFERRED_CARD`.

    This helper should typically be used when a banking site returns card and non-card
    transactions mixed on the same checking account.
    """
    for tr in it:
        if tr.type != tr.TYPE_DEFERRED_CARD:
            yield tr


def test():
    clean_amount = AmericanTransaction.clean_amount
    assert clean_amount('42') == '42'
    assert clean_amount('42,12') == '42.12'
    assert clean_amount('42.12') == '42.12'
    assert clean_amount('$42.12 USD') == '42.12'
    assert clean_amount('$12.442,12 USD') == '12442.12'
    assert clean_amount('$12,442.12 USD') == '12442.12'

    decimal_amount = AmericanTransaction.decimal_amount
    assert decimal_amount('$12,442.12 USD') == Decimal('12442.12')
    assert decimal_amount('') == Decimal('0')
