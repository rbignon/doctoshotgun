# -*- coding: utf-8 -*-
# Copyright(C) 2014 Julia Leven
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
from unittest import TestCase

from woob.browser import PagesBrowser, URL
from woob.browser.pages import Page
from woob.browser.url import UrlNotResolvable


class MyMockBrowserWithoutBrowser(object):
    BASEURL = "http://woob.tech/"
    url = URL("http://test.org/")


# Mock that allows to represent a Page
class MyMockPage(Page):
    pass


# Mock that allows to represent a Browser
class MyMockBrowser(PagesBrowser):
    BASEURL = "http://woob.tech/"

    # URL used by method match
    urlNotRegex = URL("http://test.org/", "http://test2.org/")
    urlRegex = URL("http://test.org/", "http://woob2.org/")
    urlRegWithoutHttp = URL("news")
    urlNotRegWithoutHttp = URL("youtube")

    # URL used by method build
    urlValue = URL("http://test.com/(?P<id>\d+)")
    urlParams = URL("http://test.com/\?id=(?P<id>\d+)&name=(?P<name>.+)")
    urlSameParams = URL("http://test.com/(?P<id>\d+)", "http://test.com\?id=(?P<id>\d+)&name=(?P<name>.+)")

    # URL used by method is_here
    urlIsHere = URL('http://woob.tech/(?P<param>)', MyMockPage)
    urlIsHereDifKlass = URL('http://free.fr/', MyMockPage)


# Class that tests different methods from the class URL
class URLTest(TestCase):

    # Initialization of the objects needed by the tests
    def setUp(self):
        self.myBrowser = MyMockBrowser()
        self.myBrowserWithoutBrowser = MyMockBrowserWithoutBrowser()

    # Check that an assert is sent if both base and browser are none
    def test_match_base_none_browser_none(self):
        self.assertRaises(AssertionError,
                          self.myBrowserWithoutBrowser.url.match,
                          "http://woob.tech/")

    # Check that no assert is raised when browser is none and a base is indeed
    # instanciated when given as a parameter
    def test_match_base_not_none_browser_none(self):
        try:
            self.myBrowserWithoutBrowser.url.match("http://woob.tech/news",
                                                   "http://woob.tech/")
        except AssertionError:
            self.fail("Method match returns an AssertionError while" +
                      " base parameter is not none!")

    # Check that none is returned when none of the defined urls is a regex for
    # the given url
    def test_match_url_pasregex_baseurl(self):
        res = self.myBrowser.urlNotRegex.match("http://woob.tech/news")
        self.assertIsNone(res)

    # Check that true is returned when one of the defined urls is a regex
    # for the given url
    def test_match_url_regex_baseurl(self):
        res = self.myBrowser.urlRegex.match("http://woob2.org/news")
        self.assertTrue(res)

    # Successful test with relatives url
    def test_match_url_without_http(self):
        res = self.myBrowser.urlRegWithoutHttp.match("http://woob.tech/news")
        self.assertTrue(res)

    # Unsuccessful test with relatives url
    def test_match_url_without_http_fail(self):
        browser = self.myBrowser
        res = browser.urlNotRegWithoutHttp.match("http://woob.tech/news")
        self.assertIsNone(res)

    # Checks that build returns the right url when it needs to add
    # the value of a parameter
    def test_build_nominal_case(self):
        res = self.myBrowser.urlValue.build(id=2)
        self.assertEquals(res, "http://test.com/2")

    # Checks that build returns the right url when it needs to add
    # identifiers and values of some parameters
    def test_build_urlParams_OK(self):
        res = self.myBrowser.urlParams.build(id=2, name="woob")
        self.assertEquals(res, "http://test.com/?id=2&name=woob")

    # Checks that build returns the right url when it needs to add
    # identifiers and values of some parameters.
    # The same parameters can be in multiple patterns.
    def test_build_urlSameParams_OK(self):
        res = self.myBrowser.urlSameParams.build(id=2, name="woob")
        self.assertEquals(res, "http://test.com?id=2&name=woob")

    # Checks that an exception is raised when a parameter is missing
    # (here, the parameter name)
    def test_build_urlParams_KO_missedparams(self):
        self.assertRaises(UrlNotResolvable, self.myBrowser.urlParams.build,
                          id=2)

    # Checks that an exception is raised when there is an extra parameter
    # added to the build function (here, the parameter title)
    def test_build_urlParams_KO_moreparams(self):
        self.assertRaises(UrlNotResolvable, self.myBrowser.urlParams.build,
                          id=2, name="woob", title="test")

    # Check that an assert is sent if both klass is none
    def test_ishere_klass_none(self):
        self.assertRaisesRegexp(AssertionError, "You can use this method" +
                                " only if there is a Page class handler.",
                                self.myBrowser.urlRegex.is_here, id=2)
