# -*- coding: utf-8 -*-

# Copyright(C) 2018      Vincent Ardisson
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

from __future__ import unicode_literals, absolute_import

import codecs
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from glob import glob
import os
import hashlib
from tempfile import NamedTemporaryFile
import time
import logging

try:
    from selenium import webdriver
except ImportError:
    raise ImportError('Please install python3-selenium')

from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, NoSuchFrameException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.remote.command import Command
from woob.tools.log import getLogger
from woob.tools.compat import (
    urljoin, urlparse, urlencode, parse_qsl,
    urlunparse,
)

from .pages import HTMLPage as BaseHTMLPage
from .url import URL


__all__ = (
    'SeleniumBrowser', 'SeleniumPage', 'HTMLPage',
    'CustomCondition', 'AnyCondition', 'AllCondition', 'NotCondition',
    'IsHereCondition', 'VisibleXPath', 'ClickableXPath', 'ClickableLinkText',
    'HasTextCondition', 'WrapException',
    'xpath_locator', 'link_locator', 'ElementWrapper',
)


class CustomCondition(object):
    """Abstract condition class

    In Selenium, waiting is done on callable objects named "conditions".
    Basically, a condition is a function predicate returning True if some condition is met.

    The builtin selenium conditions are in :any:`selenium.webdriver.support.expected_conditions`.

    This class exists to differentiate normal methods from condition objects when calling :any:`SeleniumPage.is_here`.

    See https://seleniumhq.github.io/selenium/docs/api/py/webdriver_support/selenium.webdriver.support.expected_conditions.html
    When using `selenium.webdriver.support.expected_conditions`, it's better to
    wrap them using :any:`WrapException`.
    """

    def __call__(self, driver):
        raise NotImplementedError()


class WrapException(CustomCondition):
    """Wrap Selenium's builtin `expected_conditions` to catch exceptions.

    Selenium's builtin `expected_conditions` return True when a condition is met
    but might throw exceptions when it's not met, which might not be desirable.

    `WrapException` wraps such `expected_conditions` to catch those exception
    and simply return False when such exception is thrown.
    """
    def __init__(self, condition):
        self.condition = condition

    def __call__(self, driver):
        try:
            return self.condition(driver)
        except NoSuchElementException:
            return False


class AnyCondition(CustomCondition):
    """Condition that is true if any of several conditions is true.
    """

    def __init__(self, *conditions):
        self.conditions = tuple(WrapException(cb) for cb in conditions)

    def __call__(self, driver):
        return any(cb(driver) for cb in self.conditions)


class AllCondition(CustomCondition):
    """Condition that is true if all of several conditions are true.
    """

    def __init__(self, *conditions):
        self.conditions = tuple(WrapException(cb) for cb in conditions)

    def __call__(self, driver):
        return all(cb(driver) for cb in self.conditions)


class NotCondition(CustomCondition):
    """Condition that tests the inverse of another condition."""

    def __init__(self, condition):
        self.condition = WrapException(condition)

    def __call__(self, driver):
        return not self.condition(driver)


class IsHereCondition(CustomCondition):
    """Condition that is true if a page "is here".

    This condition is to be passed to `SeleniumBrowser.wait_until`.
    It mustn't be used in a `SeleniumPage.is_here` definition.
    """
    def __init__(self, urlobj):
        assert isinstance(urlobj, URL)
        self.urlobj = urlobj

    def __call__(self, driver):
        return self.urlobj.is_here()


class WithinFrame(CustomCondition):
    """Check a condition inside a frame.

    In Selenium, frames are separated from each other and from the main page.
    This class wraps a condition to execute it within a frame.
    """

    def __init__(self, selector, condition):
        self.selector = selector
        self.condition = condition

    def __call__(self, driver):
        try:
            driver.switch_to.frame(self.selector)
        except NoSuchFrameException:
            return False

        try:
            return self.condition(driver)
        finally:
            driver.switch_to.default_content()


class StablePageCondition(CustomCondition):
    """
    Warning: this condition will not work if a site has a carousel or something
    like this that constantly changes the DOM.
    """

    purge_times = 10

    def __init__(self, waiting=3):
        self.elements = OrderedDict()
        self.waiting = waiting

    def _purge(self):
        now = time.time()

        for k in list(self.elements):
            if now - self.elements[k][0] > self.purge_times * self.waiting:
                del self.elements[k]

    def __call__(self, driver):
        self._purge()

        hashed = hashlib.md5(driver.page_source.encode('utf-8')).hexdigest()
        now = time.time()
        page_id = driver.find_element_by_xpath('/*').id

        if page_id not in self.elements or self.elements[page_id][1] != hashed:
            self.elements[page_id] = (now, hashed)
            return False
        elif now - self.elements[page_id][0] < self.waiting:
            return False
        return True


def VisibleXPath(xpath):
    """Wraps `visibility_of_element_located`"""
    return WrapException(EC.visibility_of_element_located(xpath_locator(xpath)))


def ClickableXPath(xpath):
    """Wraps `element_to_be_clickable`"""
    return WrapException(EC.element_to_be_clickable(xpath_locator(xpath)))


def ClickableLinkText(text, partial=False):
    """Wraps `element_to_be_clickable`"""
    return WrapException(EC.element_to_be_clickable(link_locator(text, partial)))


def HasTextCondition(xpath):
    """Condition to ensure some xpath is visible and contains non-empty text."""

    xpath = '(%s)[normalize-space(text())!=""]' % xpath
    return VisibleXPath(xpath)


def xpath_locator(xpath):
    """Creates an XPath locator from a string

    Most Selenium functions don't accept XPaths directly but "locators".
    Locators can be XPath, CSS selectors.
    """
    return (By.XPATH, xpath)


def link_locator(text, partial=False):
    """Creates an link text locator locator from a string

    Most Selenium functions don't accept XPaths directly but "locators".

    Warning: if searched text is not directly in <a> but in one of its children,
    some webdrivers might not find the link.
    """
    if partial:
        return (By.PARTIAL_LINK_TEXT, text)
    else:
        return (By.LINK_TEXT, text)


class ElementWrapper(object):
    """Wrapper to Selenium element to ressemble lxml.

    Some differences:
    - only a subset of lxml's Element class are available
    - cannot access XPath "text()", only Elements

    See https://seleniumhq.github.io/selenium/docs/api/py/webdriver_remote/selenium.webdriver.remote.webelement.html
    """
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def xpath(self, xpath):
        """Returns a list of elements matching `xpath`.

        Since it uses `find_elements_by_xpath`, it does not raise
        `NoSuchElementException` or `TimeoutException`.
        """
        return [ElementWrapper(sel) for sel in self.wrapped.find_elements_by_xpath(xpath)]

    def text_content(self):
        return self.wrapped.text

    @property
    def text(self):
        # Selenium can only fetch text recursively.
        # Could be implemented by injecting JS though.
        raise NotImplementedError()

    def itertext(self):
        return [self.wrapped.text]

    def __getattr__(self, attr):
        return getattr(self.wrapped, attr)

    @property
    class attrib(object):
        def __init__(self, el):
            self.el = el

        def __getitem__(self, k):
            v = self.el.get_attribute(k)
            if v is None:
                raise KeyError('Attribute %r was not found' % k)
            return v

        def get(self, k, default=None):
            v = self.el.get_attribute(k)
            if v is None:
                return default
            return v


class SeleniumPage(object):
    """Page to use in a SeleniumBrowser

    Differences with regular woob Pages:
    - cannot access raw HTML text
    """

    logged = False

    def __init__(self, browser):
        super(SeleniumPage, self).__init__()
        self.params = {}
        self.browser = browser
        self.driver = browser.driver
        self.logger = getLogger(self.__class__.__name__.lower(), browser.logger)

    @property
    def doc(self):
        return ElementWrapper(self.browser.driver.find_element_by_xpath('/*'))

    def is_here(self):
        """Method to determine if the browser is on this page and the page is ready.

        Use XPath and page content to determine if we are on this page.
        Make sure the page is "ready" for the usage we want. For example, if there's
        a splash screen in front the page, preventing click, it should return False.

        `is_here` can be a method or a :any:`CustomCondition` instance.
        """
        return True

    # TODO get_form


class HTMLPage(BaseHTMLPage):
    ENCODING = 'utf-8'

    def __init__(self, browser):
        fake = FakeResponse(
            url=browser.url,
            text=browser.page_source,
            content=browser.page_source.encode('utf-8'),
            encoding = 'utf-8',
        )

        super(HTMLPage, self).__init__(browser, fake, encoding='utf-8')
        self.driver = browser.driver


OPTIONS_CLASSES = {
    webdriver.Firefox: webdriver.FirefoxOptions,
    webdriver.Chrome: webdriver.ChromeOptions,
    webdriver.PhantomJS: webdriver.ChromeOptions, # unused, put dummy thing
}


CAPA_CLASSES = {
    webdriver.Firefox: DesiredCapabilities.FIREFOX,
    webdriver.Chrome: DesiredCapabilities.CHROME,
    webdriver.PhantomJS: DesiredCapabilities.PHANTOMJS,
}


class DirFirefoxProfile(FirefoxProfile):
    def __init__(self, custom_dir):
        self._woob_dir = custom_dir
        super(DirFirefoxProfile, self).__init__()

    def _create_tempfolder(self):
        if self._woob_dir:
            return self._woob_dir
        return super(DirFirefoxProfile, self)._create_tempfolder()


class FakeResponse(object):
    page = None

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class SeleniumBrowserSetupError(Exception):
    """
    Raised when the browser attributes are not valid
    and the driver can not be setup
    """


class SeleniumBrowser(object):
    """Browser similar to PagesBrowser, but using Selenium.

    URLs instances can be used. The need_login decorator can be used too.

    Differences:
    - since JS code can be run anytime, the current `url` and `page` can change anytime
    - it's not possible to use `open()`, only `location()` can be used
    - many options are not implemented yet (like proxies) or cannot be implemented at all
    """

    DRIVER = webdriver.Firefox

    """Selenium driver class"""

    HEADLESS = True

    """Run without any display"""

    DEFAULT_WAIT = 10

    """Default wait time for `wait_*` methods"""

    WINDOW_SIZE = None

    """Rendering window size

    It can be useful for responsive websites which show or hide elements depending
    on the viewport size.
    """

    BASEURL = None

    MAX_SAVED_RESPONSES = (1 << 30)  # limit to 1GiB

    def __init__(self, logger=None, proxy=None, responses_dirname=None, weboob=None, proxy_headers=None,
                 preferences=None, remote_driver_url=None, woob=None):
        super(SeleniumBrowser, self).__init__()
        self.responses_dirname = responses_dirname
        self.responses_count = 0
        self.woob = woob or weboob
        self.logger = getLogger('browser', logger)
        self.proxy = proxy or {}
        self.remote_driver_url = remote_driver_url

        # We set the default value of selenium logger to ERROR to avoid
        # spamming logs with useless information.
        # Also, the data we send to the browser using selenium (with send_keys)
        # can be displayed clearly in the log, if the log level is
        # set to DEBUG.
        logging.getLogger('selenium').setLevel(logging.ERROR)

        self.implicit_timeout = 0
        self.last_page_hash = None

        self._setup_driver(preferences)

        self._urls = []
        cls = type(self)
        for attr in dir(cls):
            val = getattr(cls, attr)
            if isinstance(val, URL):
                val = deepcopy(val)
                val.browser = self
                setattr(self, attr, val)
                self._urls.append(val)
        self._urls.sort(key=lambda u: u._creation_counter)

    def _build_options(self, preferences):
        options = OPTIONS_CLASSES[self.DRIVER]()
        if preferences:
            if isinstance(options, webdriver.FirefoxOptions):
                for key, value in preferences.items():
                    options.set_preference(key, value)
            elif isinstance(options, webdriver.ChromeOptions):
                options.add_experimental_option('prefs', preferences)
        return options

    def _build_capabilities(self):
        caps = CAPA_CLASSES[self.DRIVER].copy()
        caps['acceptInsecureCerts'] = bool(getattr(self, 'VERIFY', False))
        return caps

    def get_proxy_url(self, url):
        if self.DRIVER is webdriver.Firefox:
            proxy_url = urlparse(url)
            return proxy_url.geturl().replace('%s://' % proxy_url.scheme, '')
        return url

    def _build_proxy(self):
        proxy = Proxy()
        if 'http' in self.proxy:
            proxy.proxy_type = ProxyType.MANUAL
            proxy.http_proxy = self.get_proxy_url(self.proxy['http'])
        if 'https' in self.proxy:
            proxy.proxy_type = ProxyType.MANUAL
            proxy.ssl_proxy = self.get_proxy_url(self.proxy['https'])

        if proxy.proxy_type != ProxyType.MANUAL:
            proxy.proxy_type = ProxyType.DIRECT

        return proxy

    def _setup_driver(self, preferences):
        proxy = self._build_proxy()
        capa = self._build_capabilities()
        proxy.add_to_capabilities(capa)

        options = self._build_options(preferences)
        # TODO some browsers don't need headless
        # TODO handle different proxy setting?
        try:
            # New Selenium versions
            options.headless = self.HEADLESS
        except AttributeError:
            # Keep compatibility with old Selenium versions
            options.set_headless(self.HEADLESS)

        driver_kwargs = {}
        if self.responses_dirname:
            if not os.path.isdir(self.responses_dirname):
                os.makedirs(self.responses_dirname)
            driver_kwargs['service_log_path'] = os.path.join(self.responses_dirname, 'selenium.log')
        else:
            driver_kwargs['service_log_path'] = NamedTemporaryFile(prefix='woob_selenium_', suffix='.log', delete=False).name

        if self.remote_driver_url:
            self._setup_remote_driver(options=options, capabilities=capa, proxy=proxy)

        elif self.DRIVER is webdriver.Firefox:
            if self.responses_dirname and not os.path.isdir(self.responses_dirname):
                os.makedirs(self.responses_dirname)

            options.profile = DirFirefoxProfile(self.responses_dirname)
            if self.responses_dirname:
                capa['profile'] = self.responses_dirname
            self.driver = self.DRIVER(options=options, capabilities=capa, **driver_kwargs)
        elif self.DRIVER is webdriver.Chrome:
            self.driver = self.DRIVER(options=options, desired_capabilities=capa, **driver_kwargs)
        elif self.DRIVER is webdriver.PhantomJS:
            self.driver = self.DRIVER(desired_capabilities=capa, **driver_kwargs)
        else:
            raise NotImplementedError()

        if self.WINDOW_SIZE:
            self.driver.set_window_size(*self.WINDOW_SIZE)

    def _setup_remote_driver(self, options, capabilities, proxy):
        if self.DRIVER is webdriver.Firefox:
            capabilities['browserName'] = 'firefox'
        elif self.DRIVER is webdriver.Chrome:
            capabilities['browserName'] = 'chrome'
            options.add_argument("start-maximized")  # must be start maximized to avoid diffs using headless
        else:
            raise SeleniumBrowserSetupError('Remote driver supports only Firefox and Chrome.')

        self.driver = webdriver.Remote(
            command_executor='%s/wd/hub' % self.remote_driver_url,
            desired_capabilities=capabilities,
            options=options,
            proxy=proxy
        )

    ### Browser
    def deinit(self):
        if self.driver:
            self.driver.quit()

    @property
    def url(self):
        return self.driver.current_url

    @property
    def page(self):
        def do_on_load(page):
            if hasattr(page, 'on_load'):
                page.on_load()

        for val in self._urls:
            if not val.match(self.url):
                continue

            page = val.klass(self)
            with self.implicit_wait(0):
                try:
                    if isinstance(page.is_here, CustomCondition):
                        if page.is_here(self.driver):
                            self.logger.debug('Handle %s with %s', self.url, type(page).__name__)
                            self.save_response_if_changed()
                            do_on_load(page)
                            return page
                    elif page.is_here():
                        self.logger.debug('Handle %s with %s', self.url, type(page).__name__)
                        self.save_response_if_changed()
                        do_on_load(page)
                        return page
                except NoSuchElementException:
                    pass

        self.logger.debug('Unable to handle %s', self.url)

    def open(self, *args, **kwargs):
        # TODO maybe implement with a new window?
        raise NotImplementedError()

    def location(self, url, data=None, headers=None, params=None, method=None, json=None):
        """Change current url of the browser.

        Warning: unlike other requests-based woob browsers, this function does not block
        until the page is loaded, it's completely asynchronous.
        To use the new page content, it's necessary to wait, either implicitly (e.g. with
        context manager :any:`implicit_wait`) or explicitly (e.g. using method
        :any:`wait_until`)
        """
        assert method is None
        assert data is None
        assert json is None
        assert not headers

        params = params or {}

        # if it's a list of 2-tuples, it will cast into a dict
        # otherwise, it will raise a TypeError
        try:
            params = dict(params)
        except TypeError:
            raise TypeError("'params' keyword argument must be a dict, a list of tuples or None.")

        params = params.items()
        url_parsed = urlparse(url)
        original_params = parse_qsl(url_parsed.query)
        original_params.extend(params)
        query = urlencode(original_params)
        url_parsed._replace(query=query)
        url = urlunparse(url_parsed)

        self.logger.debug('opening %r', url)
        self.driver.get(url)

        try:
            WebDriverWait(self.driver, 1).until(EC.url_changes(self.url))
        except TimeoutException:
            pass
        return FakeResponse(page=self.page)

    def export_session(self):
        cookies = [cookie.copy() for cookie in self.driver.get_cookies()]
        for cookie in cookies:
            cookie['expirationDate'] = cookie.pop('expiry', None)

        ret = {
            'url': self.url,
            'cookies': cookies,
        }
        return ret

    def save_response_if_changed(self):
        hash = hashlib.md5(self.driver.page_source.encode('utf-8')).hexdigest()
        if self.last_page_hash != hash:
            self.save_response()

        self.last_page_hash = hash

    def save_response(self):
        if self.responses_dirname:
            if not os.path.isdir(self.responses_dirname):
                os.makedirs(self.responses_dirname)

            total = sum(os.path.getsize(f) for f in glob('%s/*' % self.responses_dirname))
            if self.MAX_SAVED_RESPONSES is not None and total >= self.MAX_SAVED_RESPONSES:
                self.logger.info('quota reached, not saving responses')
                return

            self.responses_count += 1
            path = '%s/%02d.html' % (self.responses_dirname, self.responses_count)
            with codecs.open(path, 'w', encoding='utf-8') as fd:
                fd.write(self.driver.page_source)
            self.logger.info('Response saved to %s', path)

    def absurl(self, uri, base=None):
        # FIXME this is copy-pasta from DomainBrowser
        if not base:
            base = self.url
        if base is None or base is True:
            base = self.BASEURL
        return urljoin(base, uri)

    ### a few selenium wrappers
    def wait_xpath(self, xpath, timeout=None):
        self.wait_until(EC.presence_of_element_located(xpath_locator(xpath)), timeout)

    def wait_xpath_visible(self, xpath, timeout=None):
        self.wait_until(EC.visibility_of_element_located(xpath_locator(xpath)), timeout)

    def wait_xpath_invisible(self, xpath, timeout=None):
        self.wait_until(EC.invisibility_of_element_located(xpath_locator(xpath)), timeout)

    def wait_xpath_clickable(self, xpath, timeout=None):
        self.wait_until(EC.element_to_be_clickable(xpath_locator(xpath)), timeout)

    def wait_until_is_here(self, urlobj, timeout=None):
        self.wait_until(IsHereCondition(urlobj), timeout)

    def wait_until(self, condition, timeout=None):
        """Wait until some condition object is met

        Wraps WebDriverWait.
        See https://seleniumhq.github.io/selenium/docs/api/py/webdriver_support/selenium.webdriver.support.wait.html

        See :any:`CustomCondition`.

        :param timeout: wait time in seconds (else DEFAULT_WAIT if None)
        """
        if timeout is None:
            timeout = self.DEFAULT_WAIT

        try:
            WebDriverWait(self.driver, timeout).until(condition)
        except (NoSuchElementException, TimeoutException):
            if self.responses_dirname:
                self.driver.get_screenshot_as_file('%s/%02d.png' % (self.responses_dirname, self.responses_count))
            self.save_response()
            raise

    def implicitly_wait(self, timeout):
        """Set implicit wait time

        When querying anything in DOM in Selenium, like evaluating XPath, if not found,
        Selenium will wait in a blocking manner until it is found or until the
        implicit wait timeouts.
        By default, it is 0, so if an XPath is not found, it fails immediately.

        :param timeout: new implicit wait time in seconds
        """
        self.implicit_timeout = timeout
        self.driver.implicitly_wait(timeout)

    @contextmanager
    def implicit_wait(self, timeout):
        """Context manager to change implicit wait time and restore it

        Example::

            with browser.implicit_wait(10):
                # Within this block, the implicit wait will be set to 10 seconds
                # and be restored at the end of block.
                # If the link is not found immediately, it will be periodically
                # retried until found (for max 10 seconds).
                el = self.find_element_link_text("Show list")
                el.click()
        """

        old = self.implicit_timeout
        try:
            self.driver.implicitly_wait(timeout)
            yield
        finally:
            self.driver.implicitly_wait(old)

    @contextmanager
    def in_frame(self, selector):
        """Context manager to execute a block inside a frame and restore main page after.

        In selenium, to operate on a frame's content, one needs to switch to the frame before
        and return to main page after.

        :param selector: selector to match the frame

        Example::

            with self.in_frame(xpath_locator('//frame[@id="foo"]')):
                el = self.find_element_by_xpath('//a[@id="bar"]')
                el.click()
        """

        self.driver.switch_to.frame(selector)
        try:
            yield
        finally:
            self.driver.switch_to.default_content()

    def get_storage(self):
        """Get localStorage content for current domain.

        As for cookies, this method only manipulates data for current domain.
        It's not possible to get all localStorage content. To get localStorage
        for multiple domains, the browser must change the url to each domain
        and call get_storage each time after.
        To do so, it's wise to choose a neutral URL (like an image file or JS file)
        to avoid the target page itself changing the cookies.
        """
        response = self.driver.execute(Command.GET_LOCAL_STORAGE_KEYS)

        ret = {}
        for k in response['value']:
            response = self.driver.execute(Command.GET_LOCAL_STORAGE_ITEM, {'key': k})
            ret[k] = response['value']
        return ret

    def update_storage(self, d):
        """Update local storage content for current domain.

        It has the same restrictions as `get_storage`.
        """

        for k, v in d.items():
            self.driver.execute(Command.SET_LOCAL_STORAGE_ITEM, {'key': k, 'value': v})

    def clear_storage(self):
        """Clear local storage."""

        self.driver.execute(Command.CLEAR_LOCAL_STORAGE)


class SubSeleniumMixin(object):
    """Mixin to have a Selenium browser for performing login."""

    SELENIUM_BROWSER = None

    """Class of Selenium browser to use for the login"""

    __states__ = ('selenium_state',)

    selenium_state = None

    def create_selenium_browser(self):
        dirname = self.responses_dirname
        if dirname:
            dirname += '/selenium'

        return self.SELENIUM_BROWSER(self.config, logger=self.logger, responses_dirname=dirname, proxy=self.PROXIES)

    def do_login(self):
        sub_browser = self.create_selenium_browser()
        try:
            if self.selenium_state and hasattr(sub_browser, 'load_state'):
                sub_browser.load_state(self.selenium_state)
            sub_browser.do_login()
            self.load_selenium_session(sub_browser)
        finally:
            try:
                if hasattr(sub_browser, 'dump_state'):
                    self.selenium_state = sub_browser.dump_state()
            finally:
                sub_browser.deinit()

    def load_selenium_session(self, selenium):
        d = selenium.export_session()
        for cookie in d['cookies']:
            self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

        if hasattr(self, 'locate_browser'):
            self.locate_browser(d)
