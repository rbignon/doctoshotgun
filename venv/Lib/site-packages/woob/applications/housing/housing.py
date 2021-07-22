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

from woob.capabilities.housing import (CapHousing, Query, POSTS_TYPES,
                                         ADVERT_TYPES, HOUSE_TYPES)
from woob.capabilities.base import empty
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import IFormatter, PrettyFormatter
from woob.tools.config.yamlconfig import YamlConfig


__all__ = ['AppHousing']


class HousingFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'title', 'cost', 'currency', 'area', 'date', 'text')

    def format_obj(self, obj, alias):
        result = u'%s%s%s\n' % (self.BOLD, obj.title, self.NC)
        result += 'ID: %s\n' % obj.fullid

        if hasattr(obj, 'url') and obj.url:
            result += 'URL: %s\n' % obj.url

        result += 'Cost: %s%s %s\n' % (obj.cost, obj.currency, obj.utilities)
        area = u'%.2fm²' % (obj.area) if obj.area else u'%s' % obj.area
        result += u'Area: %s\n' % area
        if hasattr(obj, 'price_per_meter') and not empty(obj.price_per_meter):
            result += u'Price per square meter: %.2f %s/m²\n' % (obj.price_per_meter, obj.currency)
        if hasattr(obj, 'rooms') and not empty(obj.rooms):
            result += u'Rooms: %d\n' % (obj.rooms)
        if hasattr(obj, 'bedrooms') and not empty(obj.bedrooms):
            result += u'Bedrooms: %d\n' % (obj.bedrooms)
        if obj.date:
            result += 'Date: %s\n' % obj.date.strftime('%Y-%m-%d')
        result += 'Phone: %s\n' % obj.phone
        if hasattr(obj, 'location') and obj.location:
            result += 'Location: %s\n' % obj.location
        if hasattr(obj, 'station') and obj.station:
            result += 'Station: %s\n' % obj.station

        if hasattr(obj, 'photos') and obj.photos:
            result += '\n%sPhotos%s\n' % (self.BOLD, self.NC)
            for photo in obj.photos:
                result += ' * %s\n' % photo.url

        result += '\n%sDescription%s\n' % (self.BOLD, self.NC)
        result += obj.text

        if hasattr(obj, 'details') and obj.details:
            result += '\n\n%sDetails%s\n' % (self.BOLD, self.NC)
            for key, value in obj.details.items():
                result += ' %s: %s\n' % (key, value)

        return result


class HousingListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'title', 'cost', 'text')

    def get_title(self, obj):
        return '%s%s %s - %s' % (obj.cost, obj.currency, obj.utilities, obj.title)

    def get_description(self, obj):
        result = u''
        if hasattr(obj, 'date') and obj.date:
            result += '%s - ' % obj.date.strftime('%Y-%m-%d')
        result += obj.text
        return result


class AppHousing(ReplApplication):
    APPNAME = 'housing'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2012-YEAR Romain Bignon'
    DESCRIPTION = "Console application to search for housing."
    SHORT_DESCRIPTION = "search for housing"
    CAPS = CapHousing
    CONFIG = {'queries': {}}
    EXTRA_FORMATTERS = {'housing_list': HousingListFormatter,
                        'housing':      HousingFormatter,
                       }
    COMMANDS_FORMATTERS = {'search': 'housing_list',
                           'info': 'housing',
                           'load': 'housing_list'
                          }

    def main(self, argv):
        self.load_config(klass=YamlConfig)
        return ReplApplication.main(self, argv)

    @defaultcount(10)
    def do_search(self, line):
        """
        search

        Search for housing. Parameters are interactively asked.
        """
        pattern = 'notempty'
        query = Query()
        query.cities = []
        while pattern:
            if len(query.cities) > 0:
                print('\n%sSelected cities:%s %s' % (self.BOLD, self.NC, ', '.join([c.name for c in query.cities])))
            pattern = self.ask('Enter a city pattern (or empty to stop)', default='')
            if not pattern:
                break

            cities = []
            for city in self.woob.do('search_city', pattern):
                cities.append(city)

            if len(cities) == 0:
                print('  Not found!')
                continue
            if len(cities) == 1:
                if city in query.cities:
                    query.cities.remove(city)
                else:
                    query.cities.append(city)
                continue

            r = 'notempty'
            while r != '':
                for i, city in enumerate(cities):
                    print('  %s%2d)%s [%s] %s (%s)' % (self.BOLD, i+1, self.NC, 'x' if city in query.cities else ' ', city.name, city.backend))
                r = self.ask('Select cities (or empty to stop)', regexp='(\d+|)', default='')
                if not r.isdigit():
                    continue
                r = int(r)
                if r <= 0 or r > len(cities):
                    continue
                city = cities[r-1]
                if city in query.cities:
                    query.cities.remove(city)
                else:
                    query.cities.append(city)

        r = 'notempty'
        while r != '':
            for i, good in enumerate(HOUSE_TYPES, 1):
                print('  %s%2d)%s [%s] %s' % (self.BOLD,
                                              i,
                                              self.NC,
                                              'x' if good in query.house_types else ' ', good))
            r = self.ask('Select type of house (or empty to stop)', regexp='(\d+|)', default='')
            if not r.isdigit():
                continue
            r = int(r)
            if r <= 0 or r > len(HOUSE_TYPES):
                continue
            value = list(HOUSE_TYPES)[r - 1]
            if value in query.house_types:
                query.house_types.remove(value)
            else:
                query.house_types.append(value)

        _type = None
        posts_types = sorted(POSTS_TYPES)
        while _type not in range(len(posts_types)):
            for i, t in enumerate(posts_types):
                print('  %s%2d)%s %s' % (self.BOLD,
                                         i,
                                         self.NC,
                                         t))
            _type = self.ask_int('Type of query')

        query.type = posts_types[_type]

        r = 'notempty'
        while r != '':
            for i, good in enumerate(ADVERT_TYPES, 1):
                print('  %s%2d)%s [%s] %s' % (self.BOLD,
                                              i,
                                              self.NC,
                                              'x' if good in query.advert_types else ' ', good))
            r = self.ask('Select type of posts (or empty to stop)', regexp='(\d+|)', default='')
            if not r.isdigit():
                continue
            r = int(r)
            if r <= 0 or r > len(ADVERT_TYPES):
                continue
            value = list(ADVERT_TYPES)[r - 1]
            if value in query.advert_types:
                query.advert_types.remove(value)
            else:
                query.advert_types.append(value)

        query.area_min = self.ask_int('Enter min area')
        query.area_max = self.ask_int('Enter max area')
        query.cost_min = self.ask_int('Enter min cost')
        query.cost_max = self.ask_int('Enter max cost')
        query.nb_rooms = self.ask_int('Enter number of rooms')
        save_query = self.ask('Save query (y/n)', default='n')
        if save_query.upper() == 'Y':
            name = ''
            while not name:
                name = self.ask('Query name')

            self.config.set('queries', name, query)
            self.config.save()
        self.complete_search(query)

    def complete_search(self, query):
        self.change_path([u'housings'])
        self.start_format()
        for housing in self.do('search_housings', query):
            self.cached_format(housing)

    def ask_int(self, txt):
        r = self.ask(txt, default='', regexp='(\d+|)')
        if r:
            return int(r)
        return None

    @defaultcount(10)
    def do_load(self, query_name):
        """
        load [query name]
        without query name : list loadable queries
        with query name laod query
        """
        queries = self.config.get('queries')
        if not queries:
            print('There is no saved queries', file=self.stderr)
            return 2

        if not query_name:
            for name in queries.keys():
                print('  %s* %s %s' % (self.BOLD,
                                       self.NC,
                                       name))
            query_name = self.ask('Which one')

        if query_name in queries:
            self.complete_search(queries.get(query_name))
        else:
            print('Unknown query', file=self.stderr)
            return 2

    def complete_info(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_info(self, _id):
        """
        info ID

        Get information about a housing.
        """
        if not _id:
            print('This command takes an argument: %s' % self.get_command_help('info', short=True), file=self.stderr)
            return 2

        housing = self.get_object(_id, 'get_housing')
        if not housing:
            print('Housing not found: %s' % _id, file=self.stderr)
            return 3

        self.start_format()
        self.format(housing)
