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

from abc import ABC, abstractmethod
from typing import Any

from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta

import cloudscraper
import colorama
from requests.adapters import ReadTimeout, ConnectionError
from termcolor import colored
from urllib import parse
from urllib3.exceptions import NewConnectionError

from woob.browser.exceptions import ClientError, ServerError, HTTPNotFound
from woob.browser.browsers import LoginBrowser
from woob.browser.url import URL
from woob.browser.pages import JsonPage, HTMLPage
from woob.tools.log import createColoredFormatter

SLEEP_INTERVAL_AFTER_CONNECTION_ERROR = 5
SLEEP_INTERVAL_AFTER_LOGIN_ERROR = 10
SLEEP_INTERVAL_AFTER_CENTER = 1
SLEEP_INTERVAL_AFTER_RUN = 5

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


def log(text, *args, **kwargs):
    args = (colored(arg, 'yellow') for arg in args)
    if 'color' in kwargs:
        text = colored(text, kwargs.pop('color'))
    text = text % tuple(args)
    print(text, **kwargs)


def log_ts(text=None, *args, **kwargs):
    ''' Log with timestamp'''
    now = datetime.datetime.now()
    print("[%s]" % now.isoformat(" ", "seconds"))
    if text:
        log(text, *args, **kwargs)


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
        return ""  # Do not choke on empty response from server


class ChallengePage(JsonPage):
    def build_doc(self, content):
        return ""  # Do not choke on empty response from server


class CentersPage(HTMLPage):
    def iter_centers_ids(self):
        for div in self.doc.xpath('//div[@class="js-dl-search-results-calendar"]'):
            data = json.loads(div.attrib['data-props'])
            yield data['searchResultId']

    def get_next_page(self):
        # French doctolib uses data-u attribute of span-element to create the link when user hovers span
        for span in self.doc.xpath('//div[contains(@class, "next")]/span'):
            if not span.attrib.has_key('data-u'):
                continue

            # How to find the corresponding javascript-code:
            # Press F12 to open dev-tools, select elements-tab, find div.next, right click on element and enable break on substructure change
            # Hover "Next" element and follow callstack upwards
            # JavaScript:
            # var t = (e = r()(e)).data("u")
            #     , n = atob(t.replace(/\s/g, '').split('').reverse().join(''));
            
            import base64
            href = base64.urlsafe_b64decode(''.join(span.attrib['data-u'].split())[::-1]).decode()
            query = dict(parse.parse_qsl(parse.urlsplit(href).query))

            if 'page' in query:
                return int(query['page'])

        for a in self.doc.xpath('//div[contains(@class, "next")]/a'):
            href = a.attrib['href']
            query = dict(parse.parse_qsl(parse.urlsplit(href).query))

            if 'page' in query:
                return int(query['page'])
        
        return None

class CenterResultPage(JsonPage):
    pass


class CenterPage(HTMLPage):
    pass


class CenterBookingPage(JsonPage):
    def find_motive(self, regex, singleShot=False):
        for s in self.doc['data']['visit_motives']:
            # ignore case as some doctors use their own spelling
            if re.search(regex, s['name'], re.IGNORECASE):
                if s['allow_new_patients'] == False:
                    log('Motive %s not allowed for new patients at this center. Skipping vaccine...',
                        s['name'], flush=True)
                    continue
                if not singleShot and not s['first_shot_motive']:
                    log('Skipping second shot motive %s...',
                        s['name'], flush=True)
                    continue
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
    second_shot_availabilities = URL(
        r'/second_shot_availabilities.json', AvailabilitiesPage)
    appointment = URL(r'/appointments.json', AppointmentPage)
    appointment_edit = URL(
        r'/appointments/(?P<id>.+)/edit.json', AppointmentEditPage)
    appointment_post = URL(
        r'/appointments/(?P<id>.+).json', AppointmentPostPage)
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

    def do_login(self, code):
        try:
            self.open(self.BASEURL + '/sessions/new')
        except ServerError as e:
            if e.response.status_code in [503] \
                and 'text/html' in e.response.headers['Content-Type'] \
                    and ('cloudflare' in e.response.text or 'Checking your browser before accessing' in e .response.text):
                log('Request blocked by CloudFlare', color='red')
            if e.response.status_code in [520]:
                log('Cloudflare is unable to connect to Doctolib server. Please retry later.', color='red')
            raise
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
            if not code:
                if not sys.__stdin__.isatty():
                    log("Auth Code input required, but no interactive terminal available. Please provide it via command line argument '--code'.", color='red')
                    return False
                self.send_auth_code.go(
                    json={'two_factor_auth_method': 'email'}, method="POST")
                code = input("Enter auth code: ")
            try:
                self.challenge.go(
                    json={'auth_code': code, 'two_factor_auth_method': 'email'}, method="POST")
            except HTTPNotFound:
                print("Invalid auth code")
                return False

        return True

    def find_centers(self, where, motives=None, page=1):
        if motives is None:
            motives = self.vaccine_motives.keys()
        for city in where:
            try:
                self.centers.go(where=city, params={
                                'ref_visit_motive_ids[]': motives, 'page': page})
            except ServerError as e:
                if e.response.status_code in [503]:
                    if 'text/html' in e.response.headers['Content-Type'] \
                        and ('cloudflare' in e.response.text or
                             'Checking your browser before accessing' in e .response.text):
                        log('Request blocked by CloudFlare', color='red')
                    return
                if e.response.status_code in [520]:
                    log('Cloudflare is unable to connect to Doctolib server. Please retry later.', color='red')
                    return
                raise
            except HTTPNotFound as e:
                raise CityNotFound(city) from e

            next_page = self.page.get_next_page()

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

            if next_page:
                for center in self.find_centers(where, motives, next_page):
                    yield center

    def get_patients(self):
        self.master_patient.go()

        return self.page.get_patients()

    @classmethod
    def normalize(cls, string):
        nfkd = unicodedata.normalize('NFKD', string)
        normalized = u"".join(
            [c for c in nfkd if not unicodedata.combining(c)])
        normalized = re.sub(r'\W', '-', normalized)
        return normalized.lower()

    def try_to_book(self, center, vaccine_list, start_date, end_date, only_second, only_third, dry_run=False):
        self.open(center['url'])
        p = urlparse(center['url'])
        center_id = p.path.split('/')[-1]

        center_page = self.center_booking.go(center_id=center_id)
        profile_id = self.page.get_profile_id()
        # extract motive ids based on the vaccine names
        motives_id = dict()
        for vaccine in vaccine_list:
            motives_id[vaccine] = self.page.find_motive(
                r'.*({})'.format(vaccine), singleShot=(vaccine == self.vaccine_motives[self.KEY_JANSSEN] or only_second or only_third))

        motives_id = dict((k, v)
                          for k, v in motives_id.items() if v is not None)
        if len(motives_id.values()) == 0:
            log('Unable to find requested vaccines in motives')
            log('Motives: %s', ', '.join(self.page.get_motives()))
            return False

        for place in self.page.get_places():
            if place['name']:
                log('– %s...', place['name'])
            practice_id = place['practice_ids'][0]
            for vac_name, motive_id in motives_id.items():
                log('  Vaccine %s...', vac_name, end=' ', flush=True)
                agenda_ids = center_page.get_agenda_ids(motive_id, practice_id)
                if len(agenda_ids) == 0:
                    # do not filter to give a chance
                    agenda_ids = center_page.get_agenda_ids(motive_id)

                if self.try_to_book_place(profile_id, motive_id, practice_id, agenda_ids, vac_name.lower(), start_date, end_date, only_second, only_third, dry_run):
                    return True

        return False

    def try_to_book_place(self, profile_id, motive_id, practice_id, agenda_ids, vac_name, start_date, end_date, only_second, only_third, dry_run=False):
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
            if only_second == False and only_third == False:
                log('First slot not found :(', color='red')
            else:
                log('Slot not found :(', color='red')
            return False

        # depending on the country, the slot is returned in a different format. Go figure...
        if isinstance(slot, dict) and 'start_date' in slot:
            slot_date_first = slot['start_date']
            if vac_name != "janssen":
                slot_date_second = slot['steps'][1]['start_date']
        elif isinstance(slot, str):
            if vac_name != "janssen" and not only_second and not only_third:
                log('Only one slot for multi-shot vaccination found')
            # should be for Janssen, second or third shots only, otherwise it is a list
            slot_date_first = slot
        elif isinstance(slot, list):
            slot_date_first = slot[0]
            if vac_name != "janssen":  # maybe redundant?
                slot_date_second = slot[1]
        else:
            log('Error while fetching first slot.', color='red')
            return False
        if vac_name != "janssen" and not only_second and not only_third:
            assert slot_date_second
        log('found!', color='green')
        log('  ├╴ Best slot found: %s', parse_date(
            slot_date_first).strftime('%c'))

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

        if vac_name != "janssen" and not only_second and not only_third:  # janssen has only one shot
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
            # elif isinstance(slot, list):
            #    slot_date_second = second_slot[1]
            else:
                log('Error while fetching second slot.', color='red')
                return False

            log('  ├╴ Second shot: %s', parse_date(
                slot_date_second).strftime('%c'))

            data['second_slot'] = slot_date_second
            self.appointment.go(data=json.dumps(data), headers=headers)

            if self.page.is_error():
                log('  └╴ Appointment not available anymore :( %s',
                    self.page.get_error())
                return False

        a_id = self.page.doc['id']

        self.appointment_edit.go(id=a_id)

        log('  ├╴ Booking for %(first_name)s %(last_name)s...' % self.patient)

        self.appointment_edit.go(
            id=a_id, params={'master_patient_id': self.patient['id']})

        custom_fields = {}
        for field in self.page.get_custom_fields():
            if field['id'] == 'cov19':
                value = 'Non'
            elif field['placeholder']:
                value = field['placeholder']
            else:
                print('%s (%s):' %
                      (field['label'], field['placeholder']), end=' ', flush=True)
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

        self.appointment_post.go(id=a_id, data=json.dumps(
            data), headers=headers, method='PUT')

        if 'redirection' in self.page.doc and not 'confirmed-appointment' in self.page.doc['redirection']:
            log('  ├╴ Open %s to complete', self.BASEURL +
                self.page.doc['redirection'])

        self.appointment_post.go(id=a_id)

        log('  └╴ Booking status: %s', self.page.doc['confirmed'])

        return self.page.doc['confirmed']


class DoctolibDE(Doctolib):
    BASEURL = 'https://www.doctolib.de'
    KEY_PFIZER = '6768'
    KEY_PFIZER_SECOND = '6769'
    KEY_PFIZER_THIRD = None
    KEY_MODERNA = '6936'
    KEY_MODERNA_SECOND = '6937'
    KEY_MODERNA_THIRD = None
    KEY_JANSSEN = '7978'
    KEY_ASTRAZENECA = '7109'
    KEY_ASTRAZENECA_SECOND = '7110'
    vaccine_motives = {
        KEY_PFIZER: 'Pfizer',
        KEY_PFIZER_SECOND: 'Zweit.*Pfizer|Pfizer.*Zweit',
        KEY_PFIZER_THIRD: 'Dritt.*Pfizer|Pfizer.*Dritt',
        KEY_MODERNA: 'Moderna',
        KEY_MODERNA_SECOND: 'Zweit.*Moderna|Moderna.*Zweit',
        KEY_MODERNA_THIRD: 'Dritt.*Moderna|Moderna.*Dritt',
        KEY_JANSSEN: 'Janssen',
        KEY_ASTRAZENECA: 'AstraZeneca',
        KEY_ASTRAZENECA_SECOND: 'Zweit.*AstraZeneca|AstraZeneca.*Zweit',
    }
    centers = URL(r'/impfung-covid-19-corona/(?P<where>\w+)', CentersPage)
    center = URL(r'/praxis/.*', CenterPage)


class DoctolibFR(Doctolib):
    BASEURL = 'https://www.doctolib.fr'
    KEY_PFIZER = '6970'
    KEY_PFIZER_SECOND = '6971'
    KEY_PFIZER_THIRD = '8192'
    KEY_MODERNA = '7005'
    KEY_MODERNA_SECOND = '7004'
    KEY_MODERNA_THIRD = '8193'
    KEY_JANSSEN = '7945'
    KEY_ASTRAZENECA = '7107'
    KEY_ASTRAZENECA_SECOND = '7108'
    vaccine_motives = {
        KEY_PFIZER: 'Pfizer',
        KEY_PFIZER_SECOND: '2de.*Pfizer',
        KEY_PFIZER_THIRD: '3e.*Pfizer',
        KEY_MODERNA: 'Moderna',
        KEY_MODERNA_SECOND: '2de.*Moderna',
        KEY_MODERNA_THIRD: '3e.*Moderna',
        KEY_JANSSEN: 'Janssen',
        KEY_ASTRAZENECA: 'AstraZeneca',
        KEY_ASTRAZENECA_SECOND: '2de.*AstraZeneca',
    }

    centers = URL(r'/vaccination-covid-19/(?P<where>\w+)', CentersPage)
    center = URL(r'/centre-de-sante/.*', CenterPage)

class Builder(ABC):
    
    """
    This Builder is to lay out the Connection methods that are needed to 
    create a connection to various parts of the DoctoLib website.
    """
    
    """
    This is the method that creates the object upon being built.
    """
    @abstractmethod
    def page(self) -> None:
        pass
    
    
    """
    This is the method that connects to the defined page, and returns the object to perform further actions.
    """
    @abstractmethod
    def connectLogin(self) -> None:
        pass
    
    """
    This is the method that gets to the patient information.
    """
    @abstractmethod
    def getPatients(self) -> None:
        pass
    
    """
    This is the method that finds the centers.
    """
    @abstractmethod
    def findCenters(self) -> None:
        pass
    
    """
    This is the method that books the appointment.
    """
    @abstractmethod
    def tryBooking(self) -> None:
        pass
 
    
class ConcerteBuilderDoctoLibFR(Builder):
    
    def __init__(self, *args, **kwargs) -> None:
        self.reset(*args, **kwargs)
        
    def reset(self, *args, **kwargs) -> None:
        self._page = DoctolibFRConnect(*args, **kwargs)

    @property
    def page(self):
        
        page = self._page
        self.reset()
        return page
    
    def connectLogin(self, code):
        return self._page.connect("Login", code)
    
    def getPatients(self):
        return self._page.connect("Get Patients")
        
    def findCenters(self, cities, motives) -> None:
        self._page.connect("Find Centers", cities, motives)
    
    def tryBooking(self, center, vaccine_list, start_date, end_date, only_second, only_third, dry_run) -> None:
        self._page.connect("Try To Book", center, vaccine_list, start_date, end_date, only_second, only_third, dry_run)
    
    
class DoctolibFRConnect(DoctolibFR):
    
    """
    This connection is specifically for the French website of DoctoLib.
    """
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.visits = []
    
    
    """
    Describes what is done at each connect step, depenidng on the visit parameter provided.
    """
    def connect(self, visit: Any, code=None,cities=None, motives=None, center=None, vaccine_list=None, start_date=None, end_date=None, only_second=None, only_third=None, dry_run=None, doctoLib=None) -> Any:
        self.visits.append(visit)
        if visit == "Login":
            self.do_login(code)
            return self
        elif visit == "Get Patients":
            patient = self.get_patients()
            return patient
        elif visit == "Find Centers":
            self.find_centers(cities, motives)
        elif visit == "Try To Book":
            self.try_to_book(center, vaccine_list, start_date, end_date, only_second, only_third, dry_run)
            
    """
    Lists what has been done at each step of the connection.
    """    
    def list_visits(self) -> None:
        print(f"Page Visits: {', '.join(self.visits)}", end="")


class ConcerteBuilderDoctoLibDE(Builder):
    
    def __init__(self, *args, **kwargs) -> None:
        self.reset(*args, **kwargs)
        
    def reset(self, *args, **kwargs) -> None:
        self._page = DoctolibDEConnect(*args, **kwargs)

    @property
    def page(self):
        
        page = self._page
        self.reset()
        return page
    
    def connectLogin(self, code):
        return self._page.connect("Login", code)
    
    def getPatients(self):
        return self._page.connect("Get Patients")
        
    def findCenters(self, cities, motives) -> None:
        self._page.connect("Find Centers", cities, motives)
    
    def tryBooking(self, center, vaccine_list, start_date, end_date, only_second, only_third, dry_run) -> None:
        self._page.connect("Try To Book", center, vaccine_list, start_date, end_date, only_second, only_third, dry_run)
    
    
class DoctolibDEConnect(DoctolibDE):
    
    """
    This connection is specifically for the German website of DoctoLib.
    """
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.visits = []
    
    def connect(self, visit: Any, code=None,cities=None, motives=None, center=None, vaccine_list=None, start_date=None, end_date=None, only_second=None, only_third=None, dry_run=None, doctoLib=None) -> Any:
        self.visits.append(visit)
        if visit == "Login":
            self.do_login(code)
            return self
        elif visit == "Get Patients":
            patient = self.get_patients()
            return patient
        elif visit == "Find Centers":
            self.find_centers(cities, motives)
        elif visit == "Try To Book":
            self.try_to_book(center, vaccine_list, start_date, end_date, only_second, only_third, dry_run)
            
        
    def list_visits(self) -> None:
        print(f"Page Visits: {', '.join(self.visits)}", end="")
    

class Director:
    
    """
    This describes the director, which dictates how the builder is used.
    """
    
    def __init__(self) -> None:
        self._builder = None
        
    @property
    def builder(self) -> Builder:
        return self._builder
    
    @builder.setter
    def builder(self, builder: Builder) -> None:
        self._builder = builder
        
    def build_vaccine_booking_connection(self, code):
        docto = self.builder.connectLogin(code)
        patients = self.builder.getPatients()
        return [patients, docto]
        


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

    def main(self, cli_args=None):
        colorama.init()  # needed for windows

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
        parser.add_argument('--dry-run', action='store_true',
                            help='do not really book the slot')
        parser.add_argument(
            'country', help='country where to book')
        parser.add_argument('city', help='city where to book')
        parser.add_argument('username', help='Doctolib username')
        parser.add_argument('password', nargs='?', help='Doctolib password')
        parser.add_argument('--code', type=str, default=None, help='2FA code')
        args = parser.parse_args(cli_args if cli_args else sys.argv[1:])

        from types import SimpleNamespace

        if args.debug:
            responses_dirname = tempfile.mkdtemp(prefix='woob_session_')
            self.setup_loggers(logging.DEBUG)
        else:
            responses_dirname = None
            self.setup_loggers(logging.WARNING)

        if not args.password:
            args.password = getpass.getpass()

        director = Director()
        
        country = args.country;
        
        if country == "fr":
            builder = ConcerteBuilderDoctoLibFR(
            args.username, args.password, responses_dirname=responses_dirname)
        else:
            builder = ConcerteBuilderDoctoLibDE(
            args.username, args.password, responses_dirname=responses_dirname)
        director.builder = builder
        
        [patients, docto] = director.build_vaccine_booking_connection(args.code)

        #patients = docto.get_patients()
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
        log('Starting to look for vaccine slots for %s %s between %s and %s...',
            docto.patient['first_name'], docto.patient['last_name'], start_date, end_date)
        log('Vaccines: %s', ', '.join(vaccine_list))
        log('Country: %s ', args.country)
        log('This may take a few minutes/hours, be patient!')
        cities = [docto.normalize(city) for city in args.city.split(',')]

        while True:
            log_ts()
            try:
                for center in docto.find_centers(cities, motives):
                    if args.center:
                        if center['name_with_title'] not in args.center:
                            logging.debug("Skipping center '%s'" %
                                          center['name_with_title'])
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
                    if not args.include_neighbor_city and not docto.normalize(center['city']).startswith(tuple(cities)):
                        logging.debug(
                            "Skipping city '%(city)s' %(name_with_title)s" % center)
                        continue

                    log('')

                    log('Center %(name_with_title)s (%(city)s):' % center)

                    if docto.try_to_book(center, vaccine_list, start_date, end_date, args.only_second, args.only_third, args.dry_run):
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
            except (ReadTimeout, ConnectionError, NewConnectionError) as e:
                print('\n%s' % (colored(
                    'Connection error. Check your internet connection. Retrying ...', 'red')))
                print(str(e))
                sleep(SLEEP_INTERVAL_AFTER_CONNECTION_ERROR)
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
