# -*- coding: utf-8 -*-

# Copyright(C) 2013 Bezleputh
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

from datetime import time, datetime
from dateutil import tz

from woob.tools.date import parse_date
from woob.tools.application.formatters.iformatter import IFormatter, PrettyFormatter
from woob.capabilities.base import empty
from woob.capabilities.calendar import CapCalendarEvent, Query, CATEGORIES, BaseCalendarEvent, TICKET, STATUS
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.config.yamlconfig import YamlConfig

__all__ = ['AppCalendar']


class UpcomingSimpleFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'start_date', 'category', 'summary', 'status')

    def format_obj(self, obj, alias):
        result = u'%s - %s' % (obj.backend, obj.category)
        if not empty(obj.start_date):
            result += u' - %s' % obj.start_date.strftime('%H:%M')
        result += u' - %s' % obj.summary
        if obj.status == STATUS.CANCELLED:
            result += u' (cancelled)'
        return result


class ICalFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'start_date', 'end_date', 'summary', 'status')

    def start_format(self, **kwargs):
        result = u'BEGIN:VCALENDAR\r\n'
        result += u'VERSION:2.0\r\n'
        result += u'PRODID:-//hacksw/handcal//NONSGML v1.0//EN\r\n'
        self.output(result)

    def format_obj(self, obj, alias):
        result = u'BEGIN:VEVENT\r\n'

        utc_zone = tz.gettz('UTC')

        event_timezone = tz.gettz(obj.timezone)
        start_date = obj.start_date if not empty(obj.start_date) else datetime.now()
        if isinstance(start_date, datetime):
            start_date = start_date.replace(tzinfo=event_timezone)
            utc_start_date = start_date.astimezone(utc_zone)
            result += u'DTSTART:%s\r\n' % utc_start_date.strftime("%Y%m%dT%H%M%SZ")
        else:
            result += u'DTSTART:%s\r\n' % start_date.strftime("%Y%m%d")

        end_date = obj.end_date if not empty(obj.end_date) else datetime.combine(start_date, time.max)
        if isinstance(end_date, datetime):
            end_date = end_date.replace(tzinfo=event_timezone)
            utc_end_date = end_date.astimezone(utc_zone)
            result += u'DTEND:%s\r\n' % utc_end_date.strftime("%Y%m%dT%H%M%SZ")
        else:
            result += u'DTEND:%s\r\n' % end_date.strftime("%Y%m%d")

        result += u'SUMMARY:%s\r\n' % obj.summary
        result += u'UID:%s\r\n' % obj.id
        result += u'STATUS:%s\r\n' % obj.status

        location = ''
        if hasattr(obj, 'location') and not empty(obj.location):
            location += obj.location + ' '

        if hasattr(obj, 'city') and not empty(obj.city):
            location += obj.city + ' '

        if not empty(location):
            result += u'LOCATION:%s\r\n' % location

        if hasattr(obj, 'categories') and not empty(obj.categories):
            result += u'CATEGORIES:%s\r\n' % obj.categories

        if hasattr(obj, 'description') and not empty(obj.description):
            result += u'DESCRIPTION:%s\r\n' % obj.description.strip(' \t\n\r')\
                                                             .replace('\r', '')\
                                                             .replace('\n', r'\n')\
                                                             .replace(',', '\,')

        if hasattr(obj, 'transp') and not empty(obj.transp):
            result += u'TRANSP:%s\r\n' % obj.transp

        if hasattr(obj, 'sequence') and not empty(obj.sequence):
            result += u'SEQUENCE:%s\r\n' % obj.sequence

        if hasattr(obj, 'url') and not empty(obj.url):
            result += u'URL:%s\r\n' % obj.url

        result += u'END:VEVENT\r\n'
        return result

    def flush(self, **kwargs):
        self.output(u'END:VCALENDAR')


class UpcomingListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'start_date', 'end_date', 'summary', 'category', 'status')

    def get_title(self, obj):
        return ' %s - %s ' % (obj.category, obj.summary)

    def get_description(self, obj):
        result = u''
        if not empty(obj.start_date):
            result += u'\tDate: %s\n' % obj.start_date.strftime('%A %d %B %Y')
            result += u'\tHour: %s' % obj.start_date.strftime('%H:%M')
            if not empty(obj.end_date):
                result += ' - %s' % obj.end_date.strftime('%H:%M')
                days_diff = (obj.end_date - obj.start_date).days
                if days_diff >= 1:
                    result += ' (%i day(s) later)' % (days_diff)
            result += '\n'
        if obj.status == STATUS.CANCELLED:
            result += '\tStatus: Cancelled\n'
        return result.strip('\n\t')


class UpcomingFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'start_date', 'end_date', 'summary', 'category', 'status')

    def format_obj(self, obj, alias):
        result = u'%s%s - %s%s\n' % (self.BOLD, obj.category, obj.summary, self.NC)

        if not empty(obj.start_date):
            if not empty(obj.end_date):
                days_diff = (obj.end_date - obj.start_date).days
                if days_diff >= 1:
                    result += u'From: %s to %s ' % (obj.start_date.strftime('%A %d %B %Y'),
                                                    obj.end_date.strftime('%A %d %B %Y'))
                else:
                    result += u'Date: %s\n' % obj.start_date.strftime('%A %d %B %Y')
                    result += u'Hour: %s' % obj.start_date.strftime('%H:%M')
                    result += ' - %s' % obj.end_date.strftime('%H:%M')
            else:
                result += u'Date: %s\n' % obj.start_date.strftime('%A %d %B %Y')
                result += u'Hour: %s' % obj.start_date.strftime('%H:%M')

            result += '\n'

        if hasattr(obj, 'location') and not empty(obj.location):
            result += u'Location: %s\n' % obj.location

        if hasattr(obj, 'city') and not empty(obj.city):
            result += u'City: %s\n' % obj.city

        if hasattr(obj, 'event_planner') and not empty(obj.event_planner):
            result += u'Event planner: %s\n' % obj.event_planner

        if hasattr(obj, 'booked_entries') and not empty(obj.booked_entries) and \
           hasattr(obj, 'max_entries') and not empty(obj.max_entries):
            result += u'Entry: %s/%s \n' % (obj.booked_entries, obj.max_entries)
        elif hasattr(obj, 'booked_entries') and not empty(obj.booked_entries):
            result += u'Entry: %s \n' % (obj.booked_entries)
        elif hasattr(obj, 'max_entries') and not empty(obj.max_entries):
            result += u'Max entries: %s \n' % (obj.max_entries)

        if hasattr(obj, 'description') and not empty(obj.description):
            result += u'Description:\n %s\n\n' % obj.description

        if hasattr(obj, 'price') and not empty(obj.price):
            result += u'Price: %.2f\n' % obj.price

        if hasattr(obj, 'ticket') and not empty(obj.ticket):
            result += u'Ticket: %s\n' % obj.ticket

        if hasattr(obj, 'url') and not empty(obj.url):
            result += u'URL: %s\n' % obj.url

        if hasattr(obj, 'status') and not empty(obj.status):
            result += u'Status: %s\n' % obj.status

        return result


class AppCalendar(ReplApplication):
    APPNAME = 'calendar'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2012-YEAR Bezleputh'
    DESCRIPTION = "Console application to see upcoming events."
    SHORT_DESCRIPTION = "see upcoming events"
    CAPS = CapCalendarEvent
    EXTRA_FORMATTERS = {'upcoming_list': UpcomingListFormatter,
                        'upcoming': UpcomingFormatter,
                        'simple_upcoming': UpcomingSimpleFormatter,
                        'ical_formatter': ICalFormatter,
                        }
    COMMANDS_FORMATTERS = {'list': 'upcoming_list',
                           'search': 'upcoming_list',
                           'load': 'upcoming_list',
                           'ls': 'upcoming_list',
                           'info': 'upcoming',
                           'export': 'ical_formatter'
                           }

    def main(self, argv):
        self.load_config(klass=YamlConfig)
        return ReplApplication.main(self, argv)

    def comp_object(self, obj1, obj2):
        if isinstance(obj1, BaseCalendarEvent) and isinstance(obj2, BaseCalendarEvent):
            if obj1.start_date == obj2.start_date:
                return 0
            if obj1.start_date > obj2.start_date:
                return 1
            return -1
        else:
            return super(AppCalendar, self).comp_object(obj1, obj2)

    def select_values(self, values_from, values_to, query_str):
        r = 'notempty'
        while r != '':
            for i, value in enumerate(values_from, 1):
                print('  %s%2d)%s [%s] %s' % (self.BOLD,
                                              i,
                                              self.NC,
                                              'x' if value in values_to else ' ',
                                              value))
            r = self.ask(query_str, regexp='(\d+|)', default='')

            if not r.isdigit():
                continue
            r = int(r)
            if r <= 0 or r > len(values_from):
                continue
            value = list(values_from)[r - 1]
            if value in values_to:
                values_to.remove(value)
            else:
                values_to.append(value)

    @defaultcount(10)
    def do_search(self, line):
        """
        search

        search for an event. Parameters interactively asked
        """
        query = Query()
        self.select_values(CATEGORIES, query.categories, '  Select category (or empty to stop)')
        self.select_values(TICKET, query.ticket, '  Select tickets status (or empty to stop)')

        if query.categories and len(query.categories) > 0 and query.ticket and len(query.ticket) > 0:
            query.city = self.ask('Enter a city', default='')
            query.summary = self.ask('Enter a title', default='')

            start_date = self.ask_date('Enter a start date', default='today')
            end_date = self.ask_date('Enter a end date', default='')

            if end_date:
                if end_date == start_date:
                    end_date = datetime.combine(start_date, time.max)
                else:
                    end_date = datetime.combine(end_date, time.max)

            query.start_date = datetime.combine(start_date, time.min)
            query.end_date = end_date

            save_query = self.ask('Save query (y/n)', default='n')
            if save_query.upper() == 'Y':
                name = ''
                while not name:
                    name = self.ask('Query name')

                self.config.set('queries', name, query)
                self.config.save()
            self.complete_search(query)

    def complete_search(self, query):
        self.change_path([u'events'])
        self.start_format()
        for event in self.do('search_events', query):
            if event:
                self.cached_format(event)

    def ask_date(self, txt, default=''):
        r = self.ask(txt, default=default)
        return parse_date(r)

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

    @defaultcount(10)
    def do_list(self, line):
        """
        list [PATTERN]
        List upcoming events, pattern can be an english or french week day, 'today' or a date (dd/mm/yy[yy])
        """

        self.change_path([u'events'])
        if line:
            _date = parse_date(line)
            if not _date:
                print('Invalid argument: %s' % self.get_command_help('list'), file=self.stderr)
                return 2

            date_from = datetime.combine(_date, time.min)
            date_to = datetime.combine(_date, time.max)
        else:
            date_from = datetime.now()
            date_to = None

        for event in self.do('list_events', date_from, date_to):
            self.cached_format(event)

    def complete_info(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_info(self, _id):
        """
        info ID

        Get information about an event.
        """

        if not _id:
            print('This command takes an argument: %s' % self.get_command_help('info', short=True), file=self.stderr)
            return 2

        event = self.get_object(_id, 'get_event')

        if not event:
            print('Upcoming event not found: %s' % _id, file=self.stderr)
            return 3

        self.start_format()
        self.format(event)

    def do_export(self, line):
        """
        export FILENAME [ID1 ID2 ID3 ...]

        ID is the identifier of the event. If no ID every events are exported

        FILENAME is where to write the file. If FILENAME is '-', the file is written to stdout.

        Export event in ICALENDAR format
        """
        if not line:
            print('This command takes at leat one argument: %s' % self.get_command_help('export'), file=self.stderr)
            return 2

        _file, args = self.parse_command_args(line, 2, req_n=1)

        l = self.retrieve_events(args)
        if l == 3:
            return 3

        if not _file == "-":
            dest = self.check_file_ext(_file)
            self.formatter.outfile = dest

        self.formatter.start_format()
        for item in l:
            self.format(item)

    def retrieve_events(self, args):
        l = []

        if not args:
            _ids = []
            for event in self.do('list_events', datetime.now(), None):
                _ids.append(event.id)
        else:
            _ids = args.strip().split(' ')

        for _id in _ids:
            event = self.get_object(_id, 'get_event')

            if not event:
                print('Upcoming event not found: %s' % _id, file=self.stderr)
                return 3

            l.append(event)

        return l

    def check_file_ext(self, _file):
        splitted_file = _file.split('.')
        if splitted_file[-1] != 'ics':
            return "%s.ics" % _file
        else:
            return _file

    def do_attends(self, line):
        """
        attends ID1 [ID2 ID3 ...]

        Register as participant of an event.
        ID is the identifier of the event.
        """
        if not line:
            print('This command takes at leat one argument: %s' % self.get_command_help('attends'), file=self.stderr)
            return 2

        args = self.parse_command_args(line, 1, req_n=1)

        l = self.retrieve_events(args[0])
        for event in l:
            # we wait till the work be done, else the errors are not handled
            self.do('attends_event', event, True).wait()

    def do_unattends(self, line):
        """
        unattends ID1 [ID2 ID3 ...]

        Unregister you participation for an event.
        ID is the identifier of the event.
        """

        if not line:
            print('This command takes at leat one argument: %s' % self.get_command_help('unattends'), file=self.stderr)
            return 2

        args = self.parse_command_args(line, 1, req_n=1)

        l = self.retrieve_events(args[0])
        for event in l:
            self.do('attends_event', event, False)
