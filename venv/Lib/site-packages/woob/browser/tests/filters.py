# -*- coding: utf-8 -*-
# Copyright(C) 2016 Matthieu Weber
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

import datetime
from decimal import Decimal
from unittest import TestCase

from dateutil.tz import gettz
from lxml.html import fromstring

from woob.browser.filters.html import FormValue, Link
from woob.browser.filters.standard import RawText, DateTime


class RawTextTest(TestCase):
    # Original RawText behaviour:
    # - the content of <p> is empty, we return the default value
    def test_first_node_is_element(self):
        e = fromstring('<html><body><p></p></body></html>')
        self.assertEqual("foo", RawText('//p', default="foo")(e))

    # - the content of <p> starts with text, we retrieve only that text
    def test_first_node_is_text(self):
        e = fromstring('<html><body><p>blah: <span>229,90</span> EUR</p></body></html>')
        self.assertEqual("blah: ", RawText('//p', default="foo")(e))

    # - the content of <p> starts with a sub-element, we retrieve the default value
    def test_first_node_has_no_recursion(self):
        e = fromstring('<html><body><p><span>229,90</span> EUR</p></body></html>')
        self.assertEqual("foo", RawText('//p', default="foo")(e))

    # Recursive RawText behaviour
    # - the content of <p> starts with text, we retrieve all text, also the text from sub-elements
    def test_first_node_is_text_recursive(self):
        e = fromstring('<html><body><p>blah: <span>229,90</span> EUR</p></body></html>')
        self.assertEqual("blah: 229,90 EUR", RawText('//p', default="foo", children=True)(e))

    # - the content of <p> starts with a sub-element, we retrieve all text, also the text from sub-elements
    def test_first_node_is_element_recursive(self):
        e = fromstring('<html><body><p><span>229,90</span> EUR</p></body></html>')
        self.assertEqual("229,90 EUR", RawText('//p', default="foo", children=True)(e))


class FormValueTest(TestCase):
    def setUp(self):
        self.e = fromstring('''
        <form>
            <input value="bonjour" name="test_text">
            <input type="number" value="5" name="test_number1">
            <input type="number" step="0.01" value="0.05" name="test_number2">
            <input type="checkbox" checked="on" name="test_checkbox1">
            <input type="checkbox" name="test_checkbox2">
            <input type="range" value="20" name="test_range">
            <input type="color" value="#fff666" name="test_color">
            <input type="date" value="2010-11-12" name="test_date">
            <input type="time" value="12:13" name="test_time">
            <input type="datetime-local" value="2010-11-12T13:14" name="test_datetime_local">
        </form>
        ''')

    def test_value(self):
        self.assertEqual('bonjour', FormValue('//form//input[@name="test_text"]')(self.e))
        self.assertEqual(5, FormValue('//form//input[@name="test_number1"]')(self.e))
        self.assertEqual(Decimal('0.05'), FormValue('//form//input[@name="test_number2"]')(self.e))
        self.assertEqual(True, FormValue('//form//input[@name="test_checkbox1"]')(self.e))
        self.assertEqual(False, FormValue('//form//input[@name="test_checkbox2"]')(self.e))
        self.assertEqual(20, FormValue('//form//input[@name="test_range"]')(self.e))
        self.assertEqual('#fff666', FormValue('//form//input[@name="test_color"]')(self.e))
        self.assertEqual(datetime.date(2010, 11, 12), FormValue('//form//input[@name="test_date"]')(self.e))
        self.assertEqual(datetime.time(12, 13), FormValue('//form//input[@name="test_time"]')(self.e))
        self.assertEqual(datetime.datetime(2010, 11, 12, 13, 14), FormValue('//form//input[@name="test_datetime_local"]')(self.e))


class LinkTest(TestCase):
    def test_link(self):
        e = fromstring('<a href="https://www.google.com/">Google</a>')

        self.assertEqual('https://www.google.com/', Link('//a')(e))



class DateTimeTest(TestCase):
    def test_tz(self):
        self.assertEqual(
            DateTime().filter('2020-01-02 13:45:00'),
            datetime.datetime(2020, 1, 2, 13, 45)
        )
        self.assertEqual(
            DateTime(tzinfo='Europe/Paris').filter('2020-01-02 13:45:00'),
            datetime.datetime(2020, 1, 2, 13, 45, tzinfo=gettz('Europe/Paris'))
        )
