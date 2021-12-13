#!/usr/bin/env python3
import sys
import os
import re
import logging
import tempfile
from time import sleep
import json
import datetime
import argparse
from pathlib import Path
import getpass
import calendar

from dateutil.relativedelta import relativedelta

import colorama
from requests.adapters import ReadTimeout, ConnectionError
from termcolor import colored
from urllib3.exceptions import NewConnectionError

from woob.exceptions import ScrapingBlocked, BrowserInteraction
from woob.tools.log import createColoredFormatter
from woob.tools.misc import get_backtrace

from .doctolib import DoctolibFR, DoctolibDE
from .exceptions import CityNotFound, WaitingInQueue
from .tools import log, log_ts

try:
    from playsound import playsound as _playsound, PlaysoundException

    def playsound(*args):
        try:
            return _playsound(*args)
        except (PlaysoundException, ModuleNotFoundError):
            pass  # do not crash if, for one reason or another, something wrong happens
except ImportError:
    def playsound(*args):
        pass


SLEEP_INTERVAL_AFTER_CONNECTION_ERROR = 5
SLEEP_INTERVAL_AFTER_LOGIN_ERROR = 10
SLEEP_INTERVAL_AFTER_CENTER = 1
SLEEP_INTERVAL_AFTER_RUN = 5

class Application:
    DATA_DIRNAME = (Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")) / 'doctoshotgun'
    STATE_FILENAME = DATA_DIRNAME / 'state.json'

    @classmethod
    def create_default_logger(cls):
        # stderr logger
        format = '%(asctime)s:%(levelname)s:%(name)s:' \
                 ':%(filename)s:%(lineno)d:%(funcName)s %(message)s'
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(createColoredFormatter(sys.stderr, format))
        return handler

    def setup_loggers(self, level):
        logging.root.handlers = []

        logging.root.setLevel(level)
        logging.root.addHandler(self.create_default_logger())

    def load_state(self):
        try:
            with open(self.STATE_FILENAME, 'r') as fp:
                state = json.load(fp)
        except IOError:
            return {}
        else:
            return state

    def save_state(self, state):
        if not os.path.exists(self.DATA_DIRNAME):
            os.makedirs(self.DATA_DIRNAME)
        with open(self.STATE_FILENAME, 'w') as fp:
            json.dump(state, fp)

    def main(self, cli_args=None):
        colorama.init()  # needed for windows

        doctolib_map = {
            "fr": DoctolibFR,
            "de": DoctolibDE
        }

        parser = argparse.ArgumentParser(
            description="Book a vaccine slot on Doctolib")
        parser.add_argument('--debug', '-d', action='store_true',
                            help='show debug information')
        parser.add_argument('--pfizer', '-z', action='store_true',
                            help='select only Pfizer vaccine')
        parser.add_argument('--moderna', '-m', action='store_true',
                            help='select only Moderna vaccine')
        parser.add_argument('--janssen', '-j', action='store_true',
                            help='select only Janssen vaccine')
        parser.add_argument('--astrazeneca', '-a', action='store_true',
                            help='select only AstraZeneca vaccine')
        parser.add_argument('--only-second', '-2',
                            action='store_true', help='select only second dose')
        parser.add_argument('--only-third', '-3',
                            action='store_true', help='select only third dose')
        parser.add_argument('--patient', '-p', type=int,
                            default=-1, help='give patient ID')
        parser.add_argument('--time-window', '-t', type=int, default=7,
                            help='set how many next days the script look for slots (default = 7)')
        parser.add_argument(
            '--center', '-c', action='append', help='filter centers')
        parser.add_argument(
            '--zipcode', action='append', help='filter centers by zipcode (e.g. 76012)', type=str)
        parser.add_argument('--center-regex',
                            action='append', help='filter centers by regex')
        parser.add_argument('--center-exclude', '-x',
                            action='append', help='exclude centers')
        parser.add_argument('--center-exclude-regex',
                            action='append', help='exclude centers by regex')
        parser.add_argument(
            '--include-neighbor-city', '-n', action='store_true', help='include neighboring cities')
        parser.add_argument('--start-date', type=str, default=None,
                            help='first date on which you want to book the first slot (format should be DD/MM/YYYY)')
        parser.add_argument('--end-date', type=str, default=None,
                            help='last date on which you want to book the first slot (format should be DD/MM/YYYY)')
        parser.add_argument('--weekday-exclude', '-w', nargs='*', type=str, default=[], action='append',
                            help='Exclude specific weekdays, e.g. "tuesday Wednesday FRIDAY"')
        parser.add_argument('--dry-run', action='store_true',
                            help='do not really book the slot')
        parser.add_argument('--confirm', action='store_true',
                            help='prompt to confirm before booking')
        parser.add_argument(
            'country', help='country where to book', choices=list(doctolib_map.keys()))
        parser.add_argument('city', help='city where to book')
        parser.add_argument('username', help='Doctolib username')
        parser.add_argument('password', nargs='?', help='Doctolib password')
        parser.add_argument('--code', type=str, default=None, help='2FA code')
        args = parser.parse_args(cli_args if cli_args else sys.argv[1:])

        if args.debug:
            responses_dirname = tempfile.mkdtemp(prefix='woob_session_')
            self.setup_loggers(logging.DEBUG)
        else:
            responses_dirname = None
            self.setup_loggers(logging.WARNING)

        if not args.password:
            args.password = getpass.getpass()

        docto = doctolib_map[args.country](
            args.username, args.password, responses_dirname=responses_dirname)
        docto.load_state(self.load_state())

        motives = []
        if not args.pfizer and not args.moderna and not args.janssen and not args.astrazeneca:
            if args.only_second:
                motives.append(docto.KEY_PFIZER_SECOND)
                motives.append(docto.KEY_MODERNA_SECOND)
                # motives.append(docto.KEY_ASTRAZENECA_SECOND) #do not add AstraZeneca by default
            elif args.only_third:
                if not docto.KEY_PFIZER_THIRD and not docto.KEY_MODERNA_THIRD:
                    print('Invalid args: No third shot vaccinations in this country')
                    return 1
                motives.append(docto.KEY_PFIZER_THIRD)
                motives.append(docto.KEY_MODERNA_THIRD)
            else:
                motives.append(docto.KEY_PFIZER)
                motives.append(docto.KEY_MODERNA)
                motives.append(docto.KEY_JANSSEN)
                # motives.append(docto.KEY_ASTRAZENECA) #do not add AstraZeneca by default
        if args.pfizer:
            if args.only_second:
                motives.append(docto.KEY_PFIZER_SECOND)
            elif args.only_third:
                if not docto.KEY_PFIZER_THIRD:  # not available in all countries
                    print('Invalid args: Pfizer has no third shot in this country')
                    return 1
                motives.append(docto.KEY_PFIZER_THIRD)
            else:
                motives.append(docto.KEY_PFIZER)
        if args.moderna:
            if args.only_second:
                motives.append(docto.KEY_MODERNA_SECOND)
            elif args.only_third:
                if not docto.KEY_MODERNA_THIRD:  # not available in all countries
                    print('Invalid args: Moderna has no third shot in this country')
                    return 1
                motives.append(docto.KEY_MODERNA_THIRD)
            else:
                motives.append(docto.KEY_MODERNA)
        if args.janssen:
            if args.only_second or args.only_third:
                print('Invalid args: Janssen has no second or third shot')
                return 1
            else:
                motives.append(docto.KEY_JANSSEN)
        if args.astrazeneca:
            if args.only_second:
                motives.append(docto.KEY_ASTRAZENECA_SECOND)
            elif args.only_third:
                print('Invalid args: AstraZeneca has no third shot')
                return 1
            else:
                motives.append(docto.KEY_ASTRAZENECA)

        vaccine_list = [docto.vaccine_motives[motive] for motive in motives]

        if args.start_date:
            try:
                start_date = datetime.datetime.strptime(
                    args.start_date, '%d/%m/%Y').date()
            except ValueError as e:
                print('Invalid value for --start-date: %s' % e)
                return 1
        else:
            start_date = datetime.date.today()
        if args.end_date:
            try:
                end_date = datetime.datetime.strptime(
                    args.end_date, '%d/%m/%Y').date()
            except ValueError as e:
                print('Invalid value for --end-date: %s' % e)
                return 1
        else:
            end_date = start_date + relativedelta(days=args.time_window)

        _day_names = dict((name.lower(), k) for k, name in enumerate(calendar.day_name))
        try:
            excluded_weekdays = [d for days in args.weekday_exclude for d in days]
            excluded_weekdays = set(sorted([_day_names[d.lower()] for d in excluded_weekdays]))
        except KeyError as e:
            print('Invalid element value for --excluded-weekday: %s' % e)
            return 1

        try:
            try:
                if not docto.do_login(args.code):
                    print('Wrong login/password')
                    return 1
            except ScrapingBlocked as e:
                log(e, color='red')
                return 1
            except BrowserInteraction as e:
                if not sys.stdin.isatty():
                    log("Auth Code input required, but no interactive terminal available. "
                        "Please provide it via command line argument '--code'.",
                        color='red')
                    return 1

                code = input("%s: " % e)
                if not docto.do_otp(code):
                    print('Invalid auth code')
                    return 1

            patients = docto.get_patients()
            if len(patients) == 0:
                print("It seems that you don't have any Patient registered in your Doctolib account. Please fill your Patient data on Doctolib Website.")
                return 1
            if args.patient >= 0 and args.patient < len(patients):
                docto.patient = patients[args.patient]
            elif len(patients) > 1:
                print('Available patients are:')
                for i, patient in enumerate(patients):
                    print('* [%s] %s %s' %
                          (i, patient['first_name'], patient['last_name']))
                while True:
                    print('For which patient do you want to book a slot?',
                          end=' ', flush=True)
                    try:
                        docto.patient = patients[int(sys.stdin.readline().strip())]
                    except (ValueError, IndexError):
                        continue
                    else:
                        break
            else:
                docto.patient = patients[0]

            log('Starting to look for vaccine slots for %s %s between %s and %s...',
                docto.patient['first_name'], docto.patient['last_name'], start_date, end_date)
            if len(excluded_weekdays) != 0:
                log('Excluded weekdays: %s', ', '.join([calendar.day_name[d] for d in excluded_weekdays]))
            log('Vaccines: %s', ', '.join(vaccine_list))
            log('Country: %s ', args.country)
            log('This may take a few minutes/hours, be patient!')
            cities = [docto.normalize(city) for city in args.city.split(',')]

            while True:
                log_ts()
                try:
                    for center in docto.find_centers(cities, motives):
                        if not args.include_neighbor_city and not docto.normalize(center['city']).startswith(tuple(cities)):
                            logging.debug("Skipping city '%(city)s' %(name_with_title)s" % center)
                            continue
                        if args.center:
                            if center['name_with_title'] not in args.center:
                                logging.debug("Skipping center '%s'" %
                                              center['name_with_title'])
                                continue
                        if args.zipcode:
                            center_matched = False
                            for zipcode in args.zipcode:
                                if center['zipcode'] == zipcode:
                                    center_matched = True
                            if not center_matched:
                                logging.debug("Skipping center '%(name_with_title)s' ['%(zipcode)s']" % center)
                                continue
                        if args.center_regex:
                            center_matched = False
                            for center_regex in args.center_regex:
                                if re.match(center_regex, center['name_with_title']):
                                    center_matched = True
                                else:
                                    logging.debug(
                                        "Skipping center '%(name_with_title)s'" % center)
                            if not center_matched:
                                continue
                        if args.center_exclude:
                            if center['name_with_title'] in args.center_exclude:
                                logging.debug(
                                    "Skipping center '%(name_with_title)s' because it's excluded" % center)
                                continue
                        if args.center_exclude_regex:
                            center_excluded = False
                            for center_exclude_regex in args.center_exclude_regex:
                                if re.match(center_exclude_regex, center['name_with_title']):
                                    logging.debug(
                                        "Skipping center '%(name_with_title)s' because it's excluded" % center)
                                    center_excluded = True
                            if center_excluded:
                                continue

                        log('')

                        log('Center %(name_with_title)s (%(city)s):' % center)

                        for appointment in docto.find_appointments(center, vaccine_list, start_date, end_date, excluded_weekdays, args.only_second, args.only_third):
                            playsound('ding.mp3')

                            if args.confirm:
                                r = input('  ├╴ Do you want to book it? (y/N) ')
                                if r.strip().lower() != 'y':
                                    log('  └╴ Skipped')
                                    continue

                            custom_fields = {}
                            for field in appointment.custom_fields:
                                if field['id'] == 'cov19':
                                    value = 'Non'
                                elif field['placeholder']:
                                    value = field['placeholder']
                                else:
                                    for key, value in field.get('options', []):
                                        print('  │  %s %s' % (colored(key, 'green'), colored(value, 'yellow')))
                                    print('  ├╴ %s%s:' % (field['label'], (' (%s)' % field['placeholder']) if field['placeholder'] else ''),
                                          end=' ', flush=True)
                                    value = sys.stdin.readline().strip()

                                custom_fields[field['id']] = value

                            if args.dry_run:
                                log('  └╴ Booking status: %s', 'fake')
                            else:
                                r = docto.book_appointment(appointment, custom_fields)
                                log('  └╴ Booking status: %s', r)

                            log('')
                            log('💉 %s Congratulations.' %
                                colored('Booked!', 'green', attrs=('bold',)))
                            return 0

                        sleep(SLEEP_INTERVAL_AFTER_CENTER)

                        log('')
                    log('No free slots found at selected centers. Trying another round in %s sec...', SLEEP_INTERVAL_AFTER_RUN)
                    sleep(SLEEP_INTERVAL_AFTER_RUN)
                except CityNotFound as e:
                    print('\n%s: City %s not found. Make sure you selected a city from the available countries.' % (
                        colored('Error', 'red'), colored(e, 'yellow')))
                    return 1
                except WaitingInQueue as waiting_time:
                    log('Within the queue, estimated waiting time %s minutes', waiting_time)
                    sleep(30)
                except (ReadTimeout, ConnectionError, NewConnectionError) as e:
                    print('\n%s' % (colored(
                        'Connection error. Check your internet connection. Retrying ...', 'red')))
                    print(str(e))
                    sleep(SLEEP_INTERVAL_AFTER_CONNECTION_ERROR)
                except Exception as e:
                    template = "An unexpected exception of type {0} occurred. Arguments:\n{1!r}"
                    message = template.format(type(e).__name__, e.args)
                    print(message)
                    if args.debug:
                        print(get_backtrace())
                    return 1
            return 0
        finally:
            self.save_state(docto.dump_state())
