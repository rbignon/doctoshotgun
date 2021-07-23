# -*- coding: utf-8 -*-

# Copyright(C) 2012 Romain Bignon
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

from woob.capabilities.pricecomparison import CapPriceComparison
from woob.tools.html import html2text
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import IFormatter, PrettyFormatter
from woob.tools.application.base import MoreResultsAvailable
from woob.tools.application.console import ConsoleApplication

__all__ = ['AppPriceCompare']


class PriceFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'cost', 'currency', 'shop', 'product')

    def format_obj(self, obj, alias):
        if hasattr(obj, 'message') and obj.message:
            message = obj.message
        else:
            message = u'%s (%s)' % (obj.shop.name, obj.shop.location)

        result = u'%s%s%s\n' % (self.BOLD, message, self.NC)
        result += u'ID: %s\n' % obj.fullid
        result += u'Product: %s\n' % obj.product.name
        result += u'Cost: %s%s\n' % (obj.cost, obj.currency)
        if hasattr(obj, 'date') and obj.date:
            result += u'Date: %s\n' % obj.date.strftime('%Y-%m-%d')

        result += u'\n%sShop:%s\n' % (self.BOLD, self.NC)
        result += u'\tName: %s\n' % obj.shop.name
        if obj.shop.location:
            result += u'\tLocation: %s\n' % obj.shop.location
        if obj.shop.info:
            result += u'\n\t' + html2text(obj.shop.info).replace('\n', '\n\t').strip()

        return result


class PricesFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'cost', 'currency')

    def get_title(self, obj):
        if hasattr(obj, 'message') and obj.message:
            message = obj.message
        elif hasattr(obj, 'shop') and obj.shop:
            message = '%s (%s)' % (obj.shop.name, obj.shop.location)
        else:
            return u'%s%s' % (obj.cost, obj.currency)

        return u'%s%s - %s' % (obj.cost, obj.currency, message)

    def get_description(self, obj):
        if obj.date:
            return obj.date.strftime('%Y-%m-%d')


class AppPriceCompare(ReplApplication):
    APPNAME = 'pricecompare'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2012-YEAR Romain Bignon'
    DESCRIPTION = "Console application to compare products."
    SHORT_DESCRIPTION = "compare products"
    DEFAULT_FORMATTER = 'table'
    EXTRA_FORMATTERS = {'prices':       PricesFormatter,
                        'price':        PriceFormatter,
                       }
    COMMANDS_FORMATTERS = {'prices':    'prices',
                           'info':      'price',
                          }
    CAPS = CapPriceComparison

    @defaultcount(10)
    def do_prices(self, pattern):
        """
        prices [PATTERN]

        Display prices for a product. If a pattern is supplied, do not prompt
        what product to compare.
        """
        products = {}
        for product in self.do('search_products', pattern):
            double = False
            for prod in products.keys():
                if product.name == prod:
                    double = True
                    products[product.name].append(product)
                    break
            if not double:
                products[product.name] = [product]

        products_type = None
        products_names = list(products.keys())
        if len(products_names) == 0:
            print('Error: no product found with this pattern', file=self.stderr)
            return 1
        elif len(products_names) == 1:
            products_type = products_names[0]
        else:
            print('What product do you want to compare?')
            for i, p in enumerate(products_names):
                print('  %s%2d)%s %s' % (self.BOLD, i+1, self.NC, p))
            r = int(self.ask('  Select a product', regexp='\d+'))
            while products_type is None:
                if r <= 0 or r > len(products):
                    print('Error: Please enter a valid ID')
                    continue
                products_type = products_names[r-1]

        self.change_path([u'prices'])
        _products = self.get_object_list('iter_prices', products.get(products_type))
        self._sort_display_products(_products)

    def _sort_display_products(self, products):
        if products:
            self.start_format()
            for price in sorted(products, key=self._get_price):
                self.cached_format(price)

    def bcall_errors_handler(self, errors, debugmsg='Use --debug option to print backtraces', ignore=()):
        for backend, error, backtrace in errors.errors:
            if isinstance(error, MoreResultsAvailable):
                products = self.get_object_list()
                self._sort_display_products(products)

        ConsoleApplication.bcall_errors_handler(self, errors, debugmsg, ignore)

    def _get_price(self, price):
        return price.cost

    def complete_info(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_info(self, _id):
        """
        info ID

        Get information about a product.
        """
        if not _id:
            print('This command takes an argument: %s' % self.get_command_help('info', short=True), file=self.stderr)
            return 2

        price = self.get_object(_id, 'get_price')
        if not price:
            print('Price not found: %s' % _id, file=self.stderr)
            return 3

        self.start_format()
        self.format(price)
