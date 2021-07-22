# -*- coding: utf-8 -*-

# Copyright(C) 2010-2014  Romain Bignon
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


from woob.capabilities.base import empty
from woob.capabilities.weather import CapWeather
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import IFormatter, PrettyFormatter


__all__ = ['AppWeather']


class ForecastsFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'date', 'low', 'high')

    temperature_display = staticmethod(lambda t: u'%s' % t.value)

    def format_obj(self, obj, alias):
        result = (
            u'%s* %-15s%s (%s - %s)' % (
                self.BOLD,
                '%s:' % obj.date,
                self.NC,
                self.temperature_display(obj.low) if not empty(obj.low) else '?',
                self.temperature_display(obj.high) if not empty(obj.high) else '?'
            )
        )
        if hasattr(obj, 'text') and obj.text:
            result += ' %s' % obj.text
        return result


class CurrentFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'date', 'temp')

    temperature_display = staticmethod(lambda t: u'%s' % t.value)

    def format_obj(self, obj, alias):
        result = u'%s%s%s: %s' % (self.BOLD, obj.date, self.NC, self.temperature_display(obj.temp))
        if hasattr(obj, 'text') and obj.text:
            result += u' - %s' % obj.text
        return result


class CitiesFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'name')

    def get_title(self, obj):
        return obj.name


class AppWeather(ReplApplication):
    APPNAME = 'weather'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2010-YEAR Romain Bignon'
    DESCRIPTION = "Console application allowing to display weather and forecasts in your city."
    SHORT_DESCRIPTION = "display weather and forecasts"
    CAPS = CapWeather
    DEFAULT_FORMATTER = 'table'
    EXTRA_FORMATTERS = {'cities':    CitiesFormatter,
                        'current':   CurrentFormatter,
                        'forecasts': ForecastsFormatter,
                       }
    COMMANDS_FORMATTERS = {'cities':    'cities',
                           'current':   'current',
                           'forecasts': 'forecasts',
                          }

    def main(self, argv):
        self.load_config()
        return ReplApplication.main(self, argv)

    @defaultcount(10)
    def do_cities(self, pattern):
        """
        cities PATTERN

        Search cities.
        """
        self.change_path(['cities'])
        self.start_format()
        for city in self.do('iter_city_search', pattern, caps=CapWeather):
            self.cached_format(city)

    def complete_current(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_current(self, line):
        """
        current CITY_ID

        Get current weather for specified city. Use the 'cities' command to find them.
        """
        city, = self.parse_command_args(line, 1, 1)
        _id, backend_name = self.parse_id(city)

        tr = self.config.get('settings', 'temperature_display', default='C')
        if tr == 'C':
            self.formatter.temperature_display = lambda t: t.ascelsius()
        elif tr == 'F':
            self.formatter.temperature_display = lambda t: t.asfahrenheit()

        self.start_format()
        for current in self.do('get_current', _id, backends=backend_name, caps=CapWeather):
            if current:
                self.format(current)

    def complete_forecasts(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_forecasts(self, line):
        """
        forecasts CITY_ID

        Get forecasts for specified city. Use the 'cities' command to find them.
        """
        city, = self.parse_command_args(line, 1, 1)
        _id, backend_name = self.parse_id(city)

        tr = self.config.get('settings', 'temperature_display', default='C')
        if tr == 'C':
            self.formatter.temperature_display = lambda t: t.ascelsius()
        elif tr == 'F':
            self.formatter.temperature_display = lambda t: t.asfahrenheit()
        self.start_format()

        for forecast in self.do('iter_forecast', _id, backends=backend_name, caps=CapWeather):
            self.format(forecast)
