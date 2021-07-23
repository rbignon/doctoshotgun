# -*- coding: utf-8 -*-

# Copyright(C) 2014 Romain Bignon
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

import warnings

from woob.tools.misc import to_unicode
from woob.tools.compat import StrConv


class BrowserIncorrectPassword(Exception):
    pass


class BrowserForbidden(Exception):
    pass


class BrowserUserBanned(BrowserIncorrectPassword):
    pass


class BrowserUnavailable(Exception):
    pass


class ScrapingBlocked(BrowserUnavailable):
    pass


class BrowserInteraction(Exception):
    pass


class BrowserQuestion(StrConv, BrowserInteraction):
    """
    When raised by a browser,
    """
    def __init__(self, *fields):
        self.fields = fields

    def __str__(self):
        return ", ".join("{}: {}".format(
            field.id or field.label, field.description) for field in self.fields
        )

    def __unicode__(self):
        return ", ".join(
            u"{}: {}".format(
                to_unicode(field.id) or to_unicode(field.label),
                to_unicode(field.description)
            ) for field in self.fields
        )


class DecoupledValidation(BrowserInteraction):
    def __init__(self, message='', resource=None, *values):
        super(DecoupledValidation, self).__init__(*values)
        self.message = message
        self.resource = resource

    def __str__(self):
        return self.message


class AppValidation(DecoupledValidation):
    pass


class AppValidationError(Exception):
    def __init__(self, message=''):
        super(AppValidationError, self).__init__(message)


class AppValidationCancelled(AppValidationError):
    pass


class AppValidationExpired(AppValidationError):
    pass


class BrowserRedirect(BrowserInteraction):
    def __init__(self, url, resource=None):
        self.url = url

        # Needed for transfer redirection
        self.resource = resource

    def __str__(self):
        return 'Redirecting to %s' % self.url


class CaptchaQuestion(Exception):
    """Site requires solving a CAPTCHA (base class)"""
    # could be improved to pass the name of the backendconfig key

    def __init__(self, type=None, **kwargs):
        super(CaptchaQuestion, self).__init__("The site requires solving a captcha")
        self.type = type
        for key, value in kwargs.items():
            setattr(self, key, value)


class WrongCaptchaResponse(Exception):
    """when website tell us captcha response is not good"""
    def __init__(self, message=None):
        super(WrongCaptchaResponse, self).__init__(message or "Captcha response is wrong")


class ImageCaptchaQuestion(CaptchaQuestion):
    type = 'image_captcha'

    image_data = None

    def __init__(self, image_data):
        super(ImageCaptchaQuestion, self).__init__(self.type, image_data=image_data)


class RecaptchaV2Question(CaptchaQuestion):
    type = 'g_recaptcha'

    website_key = None
    website_url = None

    def __init__(self, website_key, website_url):
        super(RecaptchaV2Question, self).__init__(self.type, website_key=website_key, website_url=website_url)


class NocaptchaQuestion(RecaptchaV2Question):
    def __init__(self, *args, **kwargs):
        warnings.warn('use RecaptchaV2Question class instead', DeprecationWarning)
        super(NocaptchaQuestion, self).__init__(*args, **kwargs)


class RecaptchaQuestion(CaptchaQuestion):
    type = 'g_recaptcha'

    website_key = None
    website_url = None

    def __init__(self, website_key, website_url):
        super(RecaptchaQuestion, self).__init__(self.type, website_key=website_key, website_url=website_url)


class RecaptchaV3Question(CaptchaQuestion):
    type = 'g_recaptcha'

    website_key = None
    website_url = None
    action = None

    def __init__(self, website_key, website_url, action=None):
        super(RecaptchaV3Question, self).__init__(self.type, website_key=website_key, website_url=website_url)
        self.action = action


class FuncaptchaQuestion(CaptchaQuestion):
    type = 'funcaptcha'

    website_key = None
    website_url = None
    sub_domain = None

    def __init__(self, website_key, website_url, sub_domain=None):
        super(FuncaptchaQuestion, self).__init__(
            self.type, website_key=website_key, website_url=website_url, sub_domain=sub_domain)


class HcaptchaQuestion(CaptchaQuestion):
    type = 'hcaptcha'

    website_key = None
    website_url = None

    def __init__(self, website_key, website_url):
        super(HcaptchaQuestion, self).__init__(self.type, website_key=website_key, website_url=website_url)


class BrowserHTTPNotFound(Exception):
    pass


class BrowserHTTPError(BrowserUnavailable):
    pass


class BrowserHTTPSDowngrade(Exception):
    pass


class BrowserSSLError(BrowserUnavailable):
    pass


class ParseError(Exception):
    pass


class FormFieldConversionWarning(UserWarning):
    """
    A value has been set to a form's field and has been implicitly converted.
    """


class NoAccountsException(Exception):
    pass


class ModuleInstallError(Exception):
    pass


class ModuleLoadError(Exception):
    def __init__(self, module_name, msg):
        super(ModuleLoadError, self).__init__(msg)
        self.module = module_name


class ActionNeeded(Exception):
    pass


class AuthMethodNotImplemented(ActionNeeded):
    pass


class BrowserPasswordExpired(ActionNeeded):
    pass


class NeedInteractive(Exception):
    pass


class NeedInteractiveForRedirect(NeedInteractive):
    """
    An authentication is required to connect and credentials are not supplied
    """
    pass


class NeedInteractiveFor2FA(NeedInteractive):
    """
    A 2FA is required to connect, credentials are supplied but not the second factor
    """
    pass
