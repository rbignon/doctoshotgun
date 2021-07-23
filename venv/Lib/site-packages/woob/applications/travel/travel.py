# -*- coding: utf-8 -*-

# Copyright(C) 2010-2013 Romain Bignon, Julien Hébert
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

import datetime

from woob.capabilities.base import Currency, empty
from woob.capabilities.travel import CapTravel, RoadmapFilters
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import PrettyFormatter


__all__ = ['AppTravel']


class DeparturesFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'type', 'departure_station', 'arrival_station', 'time')

    def get_title(self, obj):
        s = obj.type
        if hasattr(obj, 'price') and not empty(obj.price):
            s += u' %s %s' % (self.colored(u'—', 'cyan'), self.colored('%6.2f %s' % (obj.price, Currency.currency2txt(obj.currency)), 'green'))
        if hasattr(obj, 'late') and not empty(obj.late) and obj.late > datetime.time():
            s += u' %s %s' % (self.colored(u'—', 'cyan'), self.colored('Late: %s' % obj.late, 'red', 'bold'))
        if hasattr(obj, 'information') and not empty(obj.information) and obj.information.strip() != '':
            s += u' %s %s' % (self.colored(u'—', 'cyan'), self.colored(obj.information, 'red'))
        return s

    def get_description(self, obj):
        if hasattr(obj, 'arrival_time') and not empty(obj.arrival_time):
            s = '(%s)  %s%s\n\t(%s)  %s' % (self.colored(obj.time.strftime('%H:%M') if obj.time else '??:??', 'cyan'),
                                            obj.departure_station,
                                            self.colored(' [Platform: %s]' % obj.platform, 'yellow') if (hasattr(obj, 'platform') and not empty(obj.platform)) else '',
                                            self.colored(obj.arrival_time.strftime('%H:%M'), 'cyan'),
                                            obj.arrival_station)
        else:
            s = '(%s)  %20s -> %s' % (self.colored(obj.time.strftime('%H:%M') if obj.time else '??:??', 'cyan'),
                                      obj.departure_station, obj.arrival_station)

        return s


class StationsFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'name')

    def get_title(self, obj):
        return obj.name


class AppTravel(ReplApplication):
    APPNAME = 'travel'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2010-YEAR Romain Bignon'
    DESCRIPTION = "Console application allowing to search for train stations and get departure times."
    SHORT_DESCRIPTION = "search for train stations and departures"
    CAPS = CapTravel
    DEFAULT_FORMATTER = 'table'
    EXTRA_FORMATTERS = {'stations': StationsFormatter,
                        'departures': DeparturesFormatter,
                       }
    COMMANDS_FORMATTERS = {'stations':     'stations',
                           'departures':   'departures',
                          }

    def add_application_options(self, group):
        group.add_option('--departure-time')
        group.add_option('--arrival-time')

    @defaultcount(10)
    def do_stations(self, pattern):
        """
        stations PATTERN

        Search stations.
        """
        for station in self.do('iter_station_search', pattern):
            self.format(station)

    @defaultcount(10)
    def do_departures(self, line):
        """
        departures STATION [ARRIVAL [DATE]]]

        List all departures for a given station.
        The format for the date is "yyyy-mm-dd HH:MM" or "HH:MM".
        """
        station, arrival, date = self.parse_command_args(line, 3, 1)

        station_id, backend_name = self.parse_id(station)
        if arrival:
            arrival_id, backend_name2 = self.parse_id(arrival)
            if backend_name and backend_name2 and backend_name != backend_name2:
                print('Departure and arrival aren\'t on the same backend', file=self.stderr)
                return 1
        else:
            arrival_id = backend_name2 = None

        if backend_name:
            backends = [backend_name]
        elif backend_name2:
            backends = [backend_name2]
        else:
            backends = None

        if date is not None:
            try:
                date = self.parse_datetime(date)
            except ValueError as e:
                print('Invalid datetime value: %s' % e, file=self.stderr)
                print('Please enter a datetime in form "yyyy-mm-dd HH:MM" or "HH:MM".', file=self.stderr)
                return 1

        for departure in self.do('iter_station_departures', station_id, arrival_id, date, backends=backends):
            self.format(departure)

    def do_roadmap(self, line):
        """
        roadmap DEPARTURE ARRIVAL

        Display the roadmap to travel from DEPARTURE to ARRIVAL.

        Command-line parameters:
           --departure-time TIME    requested departure time
           --arrival-time TIME      requested arrival time

        TIME might be in form "yyyy-mm-dd HH:MM" or "HH:MM".

        Example:
            > roadmap Puteaux Aulnay-sous-Bois --arrival-time 22:00
        """
        departure, arrival = self.parse_command_args(line, 2, 2)

        filters = RoadmapFilters()
        try:
            filters.departure_time = self.parse_datetime(self.options.departure_time)
            filters.arrival_time = self.parse_datetime(self.options.arrival_time)
        except ValueError as e:
            print('Invalid datetime value: %s' % e, file=self.stderr)
            print('Please enter a datetime in form "yyyy-mm-dd HH:MM" or "HH:MM".', file=self.stderr)
            return 1

        for route in self.do('iter_roadmap', departure, arrival, filters):
            self.format(route)

    def parse_datetime(self, text):
        if text is None:
            return None

        try:
            date = datetime.datetime.strptime(text, '%Y-%m-%d %H:%M')
        except ValueError:
            try:
                date = datetime.datetime.strptime(text, '%H:%M')
            except ValueError:
                raise ValueError(text)
            date = datetime.datetime.now().replace(hour=date.hour, minute=date.minute)

        return date
