# -*- coding: utf-8 -*-

# Copyright(C) 2013  Romain Bignon
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

from woob.capabilities.base import empty
from woob.capabilities.parcel import CapParcel, Parcel, ParcelNotFound
from woob.core import CallErrors
from woob.tools.application.repl import ReplApplication
from woob.tools.application.formatters.iformatter import IFormatter


__all__ = ['AppParcel']


STATUS = {Parcel.STATUS_PLANNED:    ('PLANNED', 'red'),
          Parcel.STATUS_IN_TRANSIT: ('IN TRANSIT', 'yellow'),
          Parcel.STATUS_ARRIVED:    ('ARRIVED', 'green'),
          Parcel.STATUS_UNKNOWN:    ('', 'white'),
         }


def get_backend_name(backend):
    return backend.name


class HistoryFormatter(IFormatter):
    MANDATORY_FIELDS = ()

    def format_obj(self, obj, alias):
        if isinstance(obj, Parcel):
            result =  u'Parcel %s (%s)\n' % (self.colored(obj.id, 'red', 'bold'),
                                              self.colored(obj.backend, 'blue', 'bold'))
            result += u'%sArrival:%s %s\n' % (self.BOLD, self.NC, obj.arrival)
            status, status_color = STATUS[obj.status]
            result += u'%sStatus:%s  %s\n' % (self.BOLD, self.NC, self.colored(status, status_color))
            result += u'%sInfo:%s  %s\n\n' % (self.BOLD, self.NC, obj.info)
            result += u' Date                  Location          Activity                                          \n'
            result += u'---------------------+-----------------+---------------------------------------------------'
            return result

        return ' %s   %s %s' % (self.colored('%-19s' % obj.date, 'blue'),
                                self.colored('%-17s' % (obj.location or ''), 'magenta'),
                                self.colored(obj.activity or '', 'yellow'))


class StatusFormatter(IFormatter):
    MANDATORY_FIELDS = ('id',)

    def format_obj(self, obj, alias):
        if alias is not None:
            id = '%s (%s)' % (self.colored('%3s' % ('#' + alias), 'red', 'bold'),
                              self.colored(obj.backend, 'blue', 'bold'))
            clean = '#%s (%s)' % (alias, obj.backend)
            if len(clean) < 15:
                id += (' ' * (15 - len(clean)))
        else:
            id = self.colored('%30s' % obj.fullid, 'red', 'bold')

        status, status_color = STATUS[obj.status]
        arrival = obj.arrival.strftime('%Y-%m-%d') if not empty(obj.arrival) else ''
        result = u'%s %s %s %s  %s' % (id, self.colored(u'—', 'cyan'),
                                       self.colored('%-10s' % status, status_color),
                                       self.colored('%-10s' % arrival, 'blue'),
                                       self.colored('%-20s' % obj.info, 'yellow'))

        return result


class AppParcel(ReplApplication):
    APPNAME = 'parcel'
    OLD_APPNAME = 'parceloob'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2013-YEAR Romain Bignon'
    CAPS = CapParcel
    DESCRIPTION = "Console application to track your parcels."
    SHORT_DESCRIPTION = "manage your parcels"
    EXTRA_FORMATTERS = {'status':   StatusFormatter,
                        'history':  HistoryFormatter,
                       }
    DEFAULT_FORMATTER = 'table'
    COMMANDS_FORMATTERS = {'status':      'status',
                           'info':        'history',
                          }
    STORAGE = {'tracking': []}

    def do_track(self, line):
        """
        track ID

        Track a parcel.
        """
        parcel = self.get_object(line, 'get_parcel_tracking')
        if not parcel:
            print('Error: the parcel "%s" is not found' % line, file=self.stderr)
            return 2

        parcels = set(self.storage.get('tracking', default=[]))
        parcels.add(parcel.fullid)
        self.storage.set('tracking', list(parcels))
        self.storage.save()

        print('Parcel "%s" has been tracked.' % parcel.fullid)

    def do_untrack(self, line):
        """
        untrack ID

        Stop tracking a parcel.
        """
        removed = False
        # Always try to first remove the parcel, the untrack should always success
        parcels = set(self.storage.get('tracking', default=[]))
        try:
            parcels.remove(line)
            removed = True
        except KeyError:
            pass

        if not removed:
            try:
                parcel = self.get_object(line, 'get_parcel_tracking')
            except ParcelNotFound:
                parcel = False

            if not parcel:
                print('Error: the parcel "%s" is not found. Did you provide the full id@backend parameter?' % line, file=self.stderr)
                return 2

            try:
                parcels.remove(parcel.fullid)
            except KeyError:
                print("Error: parcel \"%s\" wasn't tracked" % parcel.fullid, file=self.stderr)
                return 2

        self.storage.set('tracking', list(parcels))
        self.storage.save()

        if removed:
            print("Parcel \"%s\" isn't tracked anymore." % line)
        else:
            print("Parcel \"%s\" isn't tracked anymore." % parcel.fullid)

    def do_status(self, line):
        """
        status

        Display status for all of the tracked parcels.
        """
        backends = list(map(get_backend_name, self.enabled_backends))
        self.start_format()
        # XXX cleaning of cached objects may be by start_format()?
        self.objects = []
        for id in self.storage.get('tracking', default=[]):
            # It should be safe to do it here, since all objects in storage
            # are stored with the fullid
            _id, backend_name = id.rsplit('@', 1)
            # If the user use the -b or -e option, do not try to get
            # the status of parcel of not loaded backends
            if backend_name not in backends:
                continue

            try:
                p = self.get_object(id, 'get_parcel_tracking')
            except CallErrors as errors:
                print('Error with parcel', id, file=self.stderr)
                self.bcall_errors_handler(errors)
                continue

            if p is None:
                continue
            self.cached_format(p)

    def do_info(self, id):
        """
        info ID

        Get information about a parcel.
        """
        parcel = self.get_object(id, 'get_parcel_tracking', [])
        if not parcel:
            print('Error: parcel not found', file=self.stderr)
            return 2

        self.start_format()
        self.format(parcel)
        for event in parcel.history:
            self.format(event)
