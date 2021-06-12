#!/usr/bin/env python3
import sys
import re
import logging
import tempfile
from time import sleep
import json
from urllib.parse import urlparse
import datetime
import argparse
import getpass
import unicodedata

from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta

import cloudscraper
import colorama
from requests.adapters import ReadTimeout, ConnectionError
from termcolor import colored
from urllib3.exceptions import NewConnectionError

from woob.browser.exceptions import ClientError, ServerError, HTTPNotFound
from woob.browser.browsers import LoginBrowser
from woob.browser.url import URL
from woob.browser.pages import JsonPage, HTMLPage
from woob.tools.log import createColoredFormatter


try:
    from playsound import playsound as _playsound, PlaysoundException
    def playsound(*args):
        try:
            return _playsound(*args)
        except (PlaysoundException,ModuleNotFoundError):
            pass # do not crash if, for one reason or another, something wrong happens
except ImportError:
    def playsound(*args):
        pass


def log(text, *args, **kwargs):
    args = (colored(arg, 'yellow') for arg in args)
    if 'color' in kwargs:
        text = colored(text, kwargs.pop('color'))
    text = text % tuple(args)
    print(text, **kwargs)


class Session(cloudscraper.CloudScraper):
    def send(self, *args, **kwargs):
        callback = kwargs.pop('callback', lambda future, response: response)
        is_async = kwargs.pop('is_async', False)

        if is_async:
            raise ValueError('Async requests are not supported')

        resp = super().send(*args, **kwargs)

        return callback(self, resp)


class LoginPage(JsonPage):
    def redirect(self):
        return self.doc['redirection']

class SendAuthCodePage(JsonPage):
    def build_doc(self, content):
        return "" # Do not choke on empty response from server

class ChallengePage(JsonPage):
    def build_doc(self, content):
        return "" # Do not choke on empty response from server

class CentersPage(HTMLPage):
    def iter_centers_ids(self):
        for div in self.doc.xpath('//div[@class="js-dl-search-results-calendar"]'):
            data = json.loads(div.attrib['data-props'])
            yield data['searchResultId']


class CenterResultPage(JsonPage):
    pass


class CenterPage(HTMLPage):
    pass


class CenterBookingPage(JsonPage):
    def find_motive(self, regex):
        for s in self.doc['data']['visit_motives']:
            if re.search(regex, s['name']) and s['allow_new_patients']:
                return s['id']

        return None

    def get_motives(self):
        return [s['name'] for s in self.doc['data']['visit_motives']]

    def get_places(self):
        return self.doc['data']['places']

    def get_practice(self):
        return self.doc['data']['places'][0]['practice_ids'][0]

    def get_agenda_ids(self, motive_id, practice_id=None):
        agenda_ids = []
        for a in self.doc['data']['agendas']:
            if motive_id in a['visit_motive_ids'] and \
               not a['booking_disabled'] and \
               (not practice_id or a['practice_id'] == practice_id):
                agenda_ids.append(str(a['id']))

        return agenda_ids

    def get_profile_id(self):
        return self.doc['data']['profile']['id']


class AvailabilitiesPage(JsonPage):
    def find_best_slot(self, start_date=None, end_date=None):
        for a in self.doc['availabilities']:
            date = parse_date(a['date']).date()
            if start_date and date < start_date or end_date and date > end_date:
                continue
            if len(a['slots']) == 0:
                continue
            return a['slots'][-1]


class AppointmentPage(JsonPage):
    def get_error(self):
        return self.doc['error']

    def is_error(self):
        return 'error' in self.doc


class AppointmentEditPage(JsonPage):
    def get_custom_fields(self):
        for field in self.doc['appointment']['custom_fields']:
            if field['required']:
                yield field


class AppointmentPostPage(JsonPage):
    pass


class MasterPatientPage(JsonPage):
    def get_patients(self):
        return self.doc

    def get_name(self):
        return '%s %s' % (self.doc[0]['first_name'], self.doc[0]['last_name'])


class CityNotFound(Exception):
    pass

class Doctolib(LoginBrowser):
    # individual properties for each country. To be defined in subclasses
    BASEURL = ""
    vaccine_motives = {}
    centers = URL('')
    center = URL('')
    # common properties
    login = URL('/login.json', LoginPage)
    send_auth_code = URL('/api/accounts/send_auth_code', SendAuthCodePage)
    challenge = URL('/login/challenge', ChallengePage)
    center_result = URL(r'/search_results/(?P<id>\d+).json', CenterResultPage)
    center_booking = URL(r'/booking/(?P<center_id>.+).json', CenterBookingPage)
    availabilities = URL(r'/availabilities.json', AvailabilitiesPage)
    second_shot_availabilities = URL(r'/second_shot_availabilities.json', AvailabilitiesPage)
    appointment = URL(r'/appointments.json', AppointmentPage)
    appointment_edit = URL(r'/appointments/(?P<id>.+)/edit.json', AppointmentEditPage)
    appointment_post = URL(r'/appointments/(?P<id>.+).json', AppointmentPostPage)
    master_patient = URL(r'/account/master_patients.json', MasterPatientPage)

    def _setup_session(self, profile):
        session = Session()

        session.hooks['response'].append(self.set_normalized_url)
        if self.responses_dirname is not None:
            session.hooks['response'].append(self.save_response)

        self.session = session


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session.headers['sec-fetch-dest'] = 'document'
        self.session.headers['sec-fetch-mode'] = 'navigate'
        self.session.headers['sec-fetch-site'] = 'same-origin'
        self.session.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36'

        self.patient = None

    def do_login(self):
        self.open(self.BASEURL + '/sessions/new')
        try:
            self.login.go(json={'kind': 'patient',
                                'username': self.username,
                                'password': self.password,
                                'remember': True,
                                'remember_username': True})
        except ClientError:
            print('Wrong login/password')
            return False

        if self.page.redirect() == "/sessions/two-factor":
            print("Requesting 2fa code...")
            self.send_auth_code.go(json={'two_factor_auth_method': 'email'}, method="POST")
            code = input("Enter auth code: ")
            try:
                self.challenge.go(json={'auth_code': code, 'two_factor_auth_method': 'email'}, method="POST")
            except HTTPNotFound:
                print("Invalid auth code")
                return False

        return True

    def find_centers(self, where, motives=None):
        if motives is None:
            motives = self.vaccine_motives.keys()
        for city in where:
            try:
                self.centers.go(where=city, params={'ref_visit_motive_ids[]': motives})
            except ServerError as e:
                if e.response.status_code in [503]:
                    return
                raise
            except HTTPNotFound as e:
                raise CityNotFound(city) from e

            for i in self.page.iter_centers_ids():
                page = self.center_result.open(
                    id=i,
                    params={
                        'limit': '4',
                        'ref_visit_motive_ids[]': motives,
                        'speciality_id': '5494',
                        'search_result_format': 'json'
                        }
                )
                try:
                    yield page.doc['search_result']
                except KeyError:
                    pass

    def get_patients(self):
        self.master_patient.go()

        return self.page.get_patients()

    @classmethod
    def normalize(cls, string):
        nfkd = unicodedata.normalize('NFKD', string)
        normalized = u"".join([c for c in nfkd if not unicodedata.combining(c)])
        normalized = re.sub(r'\W', '-', normalized)
        return normalized.lower()

    def try_to_book(self, center, vaccine_list, start_date, end_date, dry_run=False):
        self.open(center['url'])
        p = urlparse(center['url'])
        center_id = p.path.split('/')[-1]

        center_page = self.center_booking.go(center_id=center_id)
        profile_id = self.page.get_profile_id()

        # extract motive ids based on the vaccine names
        motives_id = {}
        for vaccine in vaccine_list:
            motive_id = self.page.find_motive(r'.*({})'.format(vaccine))
            if motive_id:
                motives_id[vaccine] = motive_id

        if len(motives_id.values()) == 0:
            log(colored('unable to find requested vaccines', 'red'))
            return False

        for place in self.page.get_places():
            if place['name']:
                log('– %s', place['name'])
            practice_id = place['practice_ids'][0]
            for vac_name, motive_id in motives_id.items():
                log('  Vaccine %s...', vac_name, end=' ', flush=True)
                agenda_ids = center_page.get_agenda_ids(motive_id, practice_id)
                if len(agenda_ids) == 0:
                    # do not filter to give a chance
                    agenda_ids = center_page.get_agenda_ids(motive_id)

                if self.try_to_book_place(profile_id, motive_id, practice_id, agenda_ids, vac_name.lower(), start_date, end_date, dry_run):
                    return True

        return False

    def try_to_book_place(self, profile_id, motive_id, practice_id, agenda_ids, vac_name, start_date, end_date, dry_run=False):
        date = start_date.strftime('%Y-%m-%d')
        while date is not None:
            self.availabilities.go(
                params={'start_date': date,
                        'visit_motive_ids': motive_id,
                        'agenda_ids': '-'.join(agenda_ids),
                        'insurance_sector': 'public',
                        'practice_ids': practice_id,
                        'destroy_temporary': 'true',
                        'limit': 3})
            if 'next_slot' in self.page.doc:
                date = self.page.doc['next_slot']
            else:
                date = None

        if len(self.page.doc['availabilities']) == 0:
            log('no availabilities', color='red')
            return False

        slot = self.page.find_best_slot(start_date, end_date)
        if not slot:
            log('first slot not found :(', color='red')
            return False

        # depending on the country, the slot is returned in a different format. Go figure...
        if isinstance(slot, dict) and 'start_date' in slot:
            slot_date_first = slot['start_date']
            if vac_name != "janssen":
                slot_date_second = slot['steps'][1]['start_date']
        elif isinstance(slot, str) and vac_name == 'janssen':
            slot_date_first = slot # should be for Janssen only, otherwise it is a list
        elif isinstance(slot, list):
            slot_date_first = slot[0]
            if vac_name != "janssen": # maybe redundant?
                slot_date_second = slot[1]
        else:
            log('error while fetching first slot.', color='red')
            return False

        log('found!', color='green')
        log('  ├╴ Best slot found: %s', parse_date(slot_date_first).strftime('%c'))

        appointment = {'profile_id':    profile_id,
                       'source_action': 'profile',
                       'start_date':    slot_date_first,
                       'visit_motive_ids': str(motive_id),
                      }

        data = {'agenda_ids': '-'.join(agenda_ids),
                'appointment': appointment,
                'practice_ids': [practice_id]}

        headers = {
                   'content-type': 'application/json',
                  }
        self.appointment.go(data=json.dumps(data), headers=headers)

        if self.page.is_error():
            log('  └╴ Appointment not available anymore :( %s', self.page.get_error())
            return False

        playsound('ding.mp3')

        if vac_name != "janssen": # janssen has only one shot
            self.second_shot_availabilities.go(
                params={'start_date': slot_date_second.split('T')[0],
                        'visit_motive_ids': motive_id,
                        'agenda_ids': '-'.join(agenda_ids),
                        'first_slot': slot_date_first,
                        'insurance_sector': 'public',
                        'practice_ids': practice_id,
                        'limit': 3})

            second_slot = self.page.find_best_slot()
            if not second_slot:
                log('  └╴ No second shot found')
                return False

            # in theory we could use the stored slot_date_second result from above,
            # but we refresh with the new results to play safe
            if isinstance(second_slot, dict) and 'start_date' in second_slot:
                slot_date_second = second_slot['start_date']
            elif isinstance(slot, str):
                slot_date_second = second_slot
            # TODO: is this else needed?
            #elif isinstance(slot, list):
            #    slot_date_second = second_slot[1]
            else:
                log('error while fetching second slot.', color='red')
                return False

            log('  ├╴ Second shot: %s', parse_date(slot_date_second).strftime('%c'))

            data['second_slot'] = slot_date_second
            self.appointment.go(data=json.dumps(data), headers=headers)

            if self.page.is_error():
                log('  └╴ Appointment not available anymore :( %s', self.page.get_error())
                return False

        a_id = self.page.doc['id']

        self.appointment_edit.go(id=a_id)

        log('  ├╴ Booking for %s %s...', self.patient['first_name'], self.patient['last_name'])

        self.appointment_edit.go(id=a_id, params={'master_patient_id': self.patient['id']})

        custom_fields = {}
        for field in self.page.get_custom_fields():
            if field['id'] == 'cov19':
                value = 'Non'
            elif field['placeholder']:
                value = field['placeholder']
            else:
                print('%s (%s):' % (field['label'], field['placeholder']), end=' ', flush=True)
                value = sys.stdin.readline().strip()

            custom_fields[field['id']] = value

        if dry_run:
            log('  └╴ Booking status: %s', 'fake')
            return True

        data = {'appointment': {'custom_fields_values': custom_fields,
                                'new_patient': True,
                                'qualification_answers': {},
                                'referrer_id': None,
                               },
                'bypass_mandatory_relative_contact_info': False,
                'email': None,
                'master_patient': self.patient,
                'new_patient': True,
                'patient': None,
                'phone_number': None,
               }

        self.appointment_post.go(id=a_id, data=json.dumps(data), headers=headers, method='PUT')

        if 'redirection' in self.page.doc and not 'confirmed-appointment' in self.page.doc['redirection']:
            log('  ├╴ Open %s to complete', self.BASEURL + self.page.doc['redirection'])

        self.appointment_post.go(id=a_id)

        log('  └╴ Booking status: %s', self.page.doc['confirmed'])

        return self.page.doc['confirmed']

class DoctolibDE(Doctolib):
    BASEURL = 'https://www.doctolib.de'
    KEY_PFIZER = '6768'
    KEY_MODERNA = '6936'
    KEY_JANSSEN = '7978'
    vaccine_motives = {
        KEY_PFIZER: 'Pfizer',
        KEY_MODERNA: 'Moderna',
        KEY_JANSSEN: 'Janssen',
    }
    centers = URL(r'/impfung-covid-19-corona/(?P<where>\w+)', CentersPage)
    center = URL(r'/praxis/.*', CenterPage)

class DoctolibFR(Doctolib):
    BASEURL = 'https://www.doctolib.fr'
    KEY_PFIZER = '6970'
    KEY_MODERNA = '7005'
    KEY_JANSSEN = '7945'
    vaccine_motives = {
        KEY_PFIZER: 'Pfizer',
        KEY_MODERNA: 'Moderna',
        KEY_JANSSEN: 'Janssen',
    }

    centers = URL(r'/vaccination-covid-19/(?P<where>\w+)', CentersPage)
    center = URL(r'/centre-de-sante/.*', CenterPage)

class Application:
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

    def main(self):
        colorama.init() # needed for windows

        doctolib_map = {
            "fr": DoctolibFR,
            "de": DoctolibDE
        }

        parser = argparse.ArgumentParser(description="Book a vaccine slot on Doctolib")
        parser.add_argument('--debug', '-d', action='store_true', help='show debug information')
        parser.add_argument('--pfizer', '-z', action='store_true', help='select only Pfizer vaccine')
        parser.add_argument('--moderna', '-m', action='store_true', help='select only Moderna vaccine')
        parser.add_argument('--janssen', '-j', action='store_true', help='select only Janssen vaccine')
        parser.add_argument('--patient', '-p', type=int, default=-1, help='give patient ID')
        parser.add_argument('--time-window', '-t', type=int, default=7, help='set how many next days the script look for slots (default = 7)')
        parser.add_argument('--center', '-c', action='append', help='filter centers')
        parser.add_argument('--start-date', type=str, default=None, help='first date on which you want to book the first slot (format should be DD/MM/YYYY)')
        parser.add_argument('--end-date', type=str, default=None, help='last date on which you want to book the first slot (format should be DD/MM/YYYY)')
        parser.add_argument('--dry-run', action='store_true', help='do not really book the slot')
        parser.add_argument('country', help='country where to book', choices=list(doctolib_map.keys()))
        parser.add_argument('city', help='city where to book')
        parser.add_argument('username', help='Doctolib username')
        parser.add_argument('password', nargs='?', help='Doctolib password')
        args = parser.parse_args()

        if args.debug:
            responses_dirname = tempfile.mkdtemp(prefix='woob_session_')
            self.setup_loggers(logging.DEBUG)
        else:
            responses_dirname = None
            self.setup_loggers(logging.WARNING)

        if not args.password:
            args.password = getpass.getpass()

        docto = doctolib_map[args.country](args.username, args.password, responses_dirname=responses_dirname)
        if not docto.do_login():
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
                print('* [%s] %s %s' % (i, patient['first_name'], patient['last_name']))
            while True:
                print('For which patient do you want to book a slot?', end=' ', flush=True)
                try:
                    docto.patient = patients[int(sys.stdin.readline().strip())]
                except (ValueError, IndexError):
                    continue
                else:
                    break
        else:
            docto.patient = patients[0]

        motives = []
        if not args.pfizer and not args.moderna and not args.janssen:
            motives = docto.vaccine_motives.keys()
        if args.pfizer:
            motives.append(docto.KEY_PFIZER)
        if args.moderna:
            motives.append(docto.KEY_MODERNA)
        if args.janssen:
            motives.append(docto.KEY_JANSSEN)

        vaccine_list = [docto.vaccine_motives[motive] for motive in motives]

        if args.start_date:
            try:
                start_date = datetime.datetime.strptime(args.start_date, '%d/%m/%Y').date()
            except ValueError as e:
                print('Invalid value for --start-date: %s' % e)
                return 1
        else:
            start_date = datetime.date.today()
        if args.end_date:
            try:
                end_date = datetime.datetime.strptime(args.end_date, '%d/%m/%Y').date()
            except ValueError as e:
                print('Invalid value for --end-date: %s' % e)
                return 1
        else:
            end_date = start_date + relativedelta(days=args.time_window)
        log('Starting to look for vaccine slots for %s %s between %s and %s...', docto.patient['first_name'], docto.patient['last_name'], start_date, end_date)
        log('Vaccines: %s', ', '.join(vaccine_list))
        log('Country: %s ', args.country)
        log('This may take a few minutes/hours, be patient!')
        cities = [docto.normalize(city) for city in args.city.split(',')]

        while True:
            try:
                for center in docto.find_centers(cities, motives):
                    if args.center:
                        if center['name_with_title'] not in args.center:
                            logging.debug("Skipping center '%s'", center['name_with_title'])
                            continue
                    else:
                        if docto.normalize(center['city']) not in cities:
                            logging.debug("Skipping city '%(city)s' %(name_with_title)s", center)
                            continue

                    log('')
                    log('Center %s:', center['name_with_title'])

                    if docto.try_to_book(center, vaccine_list, start_date, end_date, args.dry_run):
                        log('')
                        log('💉 %s Congratulations.' % colored('Booked!', 'green', attrs=('bold',)))
                        return 0

                    sleep(1)

                sleep(5)
            except CityNotFound as e:
                print('\n%s: City %s not found. Make sure you selected a city from the available countries.' % (colored('Error', 'red'), colored(e, 'yellow')))
                return 1
            except (ReadTimeout, ConnectionError, NewConnectionError) as e:
                print('\n%s' % (colored('Connection error. Check your internet connection. Retrying ...', 'red')))
                print(str(e))
                sleep(5)
            except Exception as e:
                template = "An unexpected exception of type {0} occurred. Arguments:\n{1!r}"
                message = template.format(type(e).__name__, e.args)
                print(message)
                return 1
        return 0


if __name__ == '__main__':
    try:
        sys.exit(Application().main())
    except KeyboardInterrupt:
        print('Abort.')
        sys.exit(1)
