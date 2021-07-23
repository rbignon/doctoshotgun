# -*- coding: utf-8 -*-

# Copyright(C) 2012  Lucien Loiseau
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

import re

from woob.capabilities.translate import CapTranslate, TranslationFail, LanguageNotSupported
from woob.tools.application.repl import ReplApplication
from woob.tools.application.formatters.iformatter import IFormatter
from babel.core import Locale, UnknownLocaleError
from babel.localedata import locale_identifiers

__all__ = ['AppTranslate']


class TranslationFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'text')

    def format_obj(self, obj, alias):
        return u'%s* %s%s\n\t%s' % (self.BOLD, obj.backend, self.NC, obj.text.replace('\n', '\n\t'))


class XmlTranslationFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'text')

    def start_format(self, **kwargs):
        if 'source' in kwargs:
            self.output('<source>\n%s\n</source>' % kwargs['source'])

    def format_obj(self, obj, alias):
        return u'<translation %s>\n%s\n</translation>' % (obj.backend, obj.text)


class AppTranslate(ReplApplication):
    APPNAME = 'translate'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2012-YEAR Lucien Loiseau'
    DESCRIPTION = "Console application to translate text from one language to another"
    SHORT_DESCRIPTION = "translate text from one language to another"
    CAPS = CapTranslate
    EXTRA_FORMATTERS = {'translation': TranslationFormatter,
        'xmltrans':    XmlTranslationFormatter,
        }
    COMMANDS_FORMATTERS = {'translate': 'translation',
        }

    def parse_lang(self, s):
        try:
            locale = Locale.parse(s)
        except UnknownLocaleError:
            pattern = re.compile(r'\b%s\b' % re.escape(s), re.I)
            for locale_id in locale_identifiers():
                locale = Locale.parse(locale_id)
                if pattern.search(locale.english_name):
                    return locale.language
            return s
        else:
            return locale.language

    def do_translate(self, line):
        """
        translate FROM TO [TEXT]

        Translate from one language to another.
        * FROM : source language
        * TO   : destination language
        * TEXT : text to translate. If "-" is passed, spawn $EDITOR (if in a TTY) to edit text
                 or use standard input text.

        Language  Abbreviation
        ----------------------
        Arabic      ar          Esperanto   eo          Irish       ga          Russian     ru
        Afrikaans   af          Estonian    et          Italian     it          Serbian     sr
        Albanian    sq          Filipino    tl          Japanese    ja          Slovak      sk
        Armenian    hy          Finnish     fi          Kannada     kn          Slovenian   sl
        Azerbaijani az          French      fr          Korean      ko          Spanish     es
        Basque      eu          Galician    gl          Latin       la          Swahili     sw
        Belarusian  be          Georgian    ka          Latvian     lv          Swedish     sv
        Bengali     bn          German      de          Lithuanian  lt          Tamil       ta
        Bulgarian   bg          Greek       gr          Macedonian  mk          Telugu      te
        Catalan     ca          Gujarati    gu          Malay       ms          Thai        th
        Chinese     zh          Haitian     ht          Maltese     mt          Turkish     tr
        Croatian    hr          Hebrew      iw          Norwegian   no          Ukrainian   uk
        Czech       cz          Hindi       hi          Persian     fa          Urdu        ur
        Danish      da          Hungaric    hu          Polish      pl          Vietnamese  vi
        Dutch       nl          Icelandic   is          Portuguese  pt          Welsh       cy
        English     en          Indonesian  id          Romanian    ro          Yiddish     yi
        ----------------------
        """

        lan_from, lan_to, text = self.parse_command_args(line, 3, 2)

        try:
            lan_from = self.parse_lang(lan_from)
            lan_to = self.parse_lang(lan_to)

            if not text or text == '-':
                text = self.acquire_input()

            self.start_format(source=text)
            for translation in self.do('translate', lan_from, lan_to, text):
                self.format(translation)
        except (TranslationFail, LanguageNotSupported) as error:
            print(error, file=self.stderr)
            pass
