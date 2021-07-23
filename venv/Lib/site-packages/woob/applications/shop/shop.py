# -*- coding: utf-8 -*-

# Copyright(C) 2015 Christophe Lampin
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

from __future__ import print_function

from decimal import Decimal

from woob.capabilities.base import empty
from woob.capabilities.shop import CapShop, Order, Item
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import IFormatter

__all__ = ['AppShop']


class OrdersFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'date', 'total')

    def start_format(self, **kwargs):
        self.output('               Id                Date         Total   ')
        self.output('-----------------------------+------------+-----------')

    def format_obj(self, obj, alias):
        date = obj.date.strftime('%Y-%m-%d') if not empty(obj.date) else ''
        total = obj.total or Decimal('0')
        result = u'%s  %s  %s' % (self.colored('%-28s' % obj.fullid, 'yellow'),
                                  self.colored('%-10s' % date, 'blue'),
                                  self.colored('%9.2f' % total, 'green'))

        return result

    def flush(self):
        self.output(u'----------------------------+------------+-----------')


class ItemsFormatter(IFormatter):
    MANDATORY_FIELDS = ('label', 'url', 'price')

    def start_format(self, **kwargs):
        self.output('                                    Label                                                           Url                       Price   ')
        self.output('---------------------------------------------------------------------------+---------------------------------------------+----------')

    def format_obj(self, obj, alias):
        price = obj.price or Decimal('0')
        result = u'%s  %s  %s' % (self.colored('%-75s' % obj.label[:75], 'yellow'),
                                  self.colored('%-43s' % obj.url, 'magenta'),
                                  self.colored('%9.2f' % price, 'green'))

        return result

    def flush(self):
        self.output(u'---------------------------------------------------------------------------+---------------------------------------------+----------')


class PaymentsFormatter(IFormatter):
    MANDATORY_FIELDS = ('date', 'method', 'amount')

    def start_format(self, **kwargs):
        self.output('   Date          Method        Amount  ')
        self.output('-----------+-----------------+----------')

    def format_obj(self, obj, alias):
        date = obj.date.strftime('%Y-%m-%d') if not empty(obj.date) else ''
        amount = obj.amount or Decimal('0')
        result = u'%s  %s  %s' % (self.colored('%-10s' % date, 'blue'),
                                  self.colored('%-17s' % obj.method, 'yellow'),
                                  self.colored('%9.2f' % amount, 'green'))

        return result

    def flush(self):
        self.output(u'-----------+-----------------+----------')


class AppShop(ReplApplication):
    APPNAME = 'shop'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2015 Christophe Lampin'
    DESCRIPTION = 'Console application to obtain details and status of e-commerce orders.'
    SHORT_DESCRIPTION = "obtain details and status of e-commerce orders"
    CAPS = CapShop
    COLLECTION_OBJECTS = (Order, )
    EXTRA_FORMATTERS = {'orders':   OrdersFormatter,
                        'items':   ItemsFormatter,
                        'payments':   PaymentsFormatter
                        }
    DEFAULT_FORMATTER = 'table'
    COMMANDS_FORMATTERS = {'orders':    'orders',
                           'items':     'items',
                           'payments':  'payments',
                           'ls':        'orders',
                           }

    def main(self, argv):
        self.load_config()
        return ReplApplication.main(self, argv)

    @defaultcount(10)
    def do_orders(self, line):
        """
        orders [BACKEND_NAME]

        Get orders of a backend.
        If no BACKEND_NAME given, display all orders of all backends.
        """
        if len(line) > 0:
            backend_name = line
        else:
            backend_name = None

        self.do_count(str(self.options.count))  # Avoid raise of MoreResultsAvailable
        l = []
        for order in self.do('iter_orders', backends=backend_name):
            l.append(order)

        self.start_format()
        for order in sorted(l, self.comp_object):
            self.format(order)

    # Order by date DESC
    def comp_object(self, obj1, obj2):
        if obj1.date == obj2.date:
            return 0
        elif obj1.date < obj2.date:
            return 1
        else:
            return -1

    def do_items(self, id):
        """
        items [ID]

        Get items of orders.
        """
        l = []
        id, backend_name = self.parse_id(id, unique_backend=True)

        if not id:
            print('Error: please give a order ID (hint: use orders command)', file=self.stderr)
            return 2
        else:
            l.append((id, backend_name))

        for id, backend in l:
            names = (backend,) if backend is not None else None
            # TODO: Use specific formatter
            mysum = Item()
            mysum.label = u"Sum"
            mysum.url = u"Generated by shop"
            mysum.price = Decimal("0.")

            self.start_format()
            for item in self.do('iter_items', id, backends=names):
                self.format(item)
                mysum.price = item.price + mysum.price

            self.format(mysum)

    def do_payments(self, id):
        """
        payments [ID]

        Get payments of orders.
        If no ID given, display payment of all backends.
        """

        id, backend_name = self.parse_id(id, unique_backend=True)

        if not id:
            print('Error: please give a order ID (hint: use orders command)', file=self.stderr)
            return 2

        self.start_format()
        for payment in self.do('iter_payments', id, backends=backend_name):
            self.format(payment)
