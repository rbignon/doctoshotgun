#!/usr/bin/env python3
import re
import json
from urllib.parse import urlparse
from urllib import parse
import unicodedata

from dateutil.parser import parse as parse_date

import cloudscraper

from woob.exceptions import ScrapingBlocked, BrowserInteraction
from woob.browser.exceptions import ClientError, ServerError, HTTPNotFound
from woob.browser.browsers import LoginBrowser, StatesMixin
from woob.browser.url import URL
from woob.browser.pages import JsonPage, HTMLPage

from .tools import log
from .exceptions import CityNotFound, WaitingInQueue


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
    def on_load(self):
        try:
            v = self.doc.xpath('//input[@id="wait-time-value"]')[0]
        except IndexError:
            return
        raise WaitingInQueue(int(v.attrib['value']))

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
    def find_best_slot(self, start_date=None, end_date=None, excluded_weekdays=[]):
        for a in self.doc['availabilities']:
            date = parse_date(a['date']).date()
            if start_date and date < start_date or end_date and date > end_date:
                continue
            if date.weekday() in excluded_weekdays:
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


class Appointment:
    def __init__(self):
        self.id = None
        self.custom_fields = {}
        self.slots = []
        self.vaccine = ''
        self.map_url = ''
        self.name = ''
        self.address = ''
        self.zipcode = ''
        self.city = ''


class Doctolib(LoginBrowser, StatesMixin):
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

    def locate_browser(self, state):
        # When loading state, do not locate browser on the last url.
        pass

    def do_login(self, code=None):
        try:
            self.open(self.BASEURL + '/sessions/new')
        except ServerError as e:
            if e.response.status_code in [503] \
                and 'text/html' in e.response.headers['Content-Type'] \
                    and ('cloudflare' in e.response.text or 'Checking your browser before accessing' in e .response.text):
                raise ScrapingBlocked('Request blocked by CloudFlare')
            if e.response.status_code in [520]:
                raise ScrapingBlocked('Cloudflare is unable to connect to Doctolib server. Please retry later.')
            raise
        try:
            self.login.go(json={'kind': 'patient',
                                'username': self.username,
                                'password': self.password,
                                'remember': True,
                                'remember_username': True})
        except ClientError:
            return False

        if self.page.redirect() == "/sessions/two-factor":
            if code:
                return self.do_otp(code)

            self.send_auth_code.go(json={'two_factor_auth_method': 'email'}, method="POST")

            raise BrowserInteraction('Enter auth code receveid by email')

        return True

    def do_otp(self, code):
        try:
            self.challenge.go(
                json={'auth_code': code, 'two_factor_auth_method': 'email'}, method="POST")
        except HTTPNotFound:
            print("Invalid auth code")
            return False

        return True

    def find_centers(self, cities, motives=None, page=1):
        if motives is None:
            motives = self.vaccine_motives.keys()
        for city in cities:
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
                for center in self.find_centers(cities, motives, next_page):
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

    def find_appointments(self, center, vaccine_list, start_date, end_date, excluded_weekdays, only_second, only_third):
        try:
            self.open(center['url'])
        except ClientError as e:
            # Sometimes there are referenced centers which are not available anymore (410 Gone)
            log('Error: %s', e, color='red')
            return

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
            log('Unable to find requested vaccines in motives', color='red')
            log('Motives: %s', ', '.join(self.page.get_motives()), color='red')
            return

        for place in self.page.get_places():
            if place['name']:
                log('– %s...', place['name'])
            for vac_name, motive_id in motives_id.items():
                log('  Vaccine %s...', vac_name, end=' ', flush=True)
                agenda_ids = center_page.get_agenda_ids(motive_id, place['practice_ids'][0])
                if len(agenda_ids) == 0:
                    # do not filter to give a chance
                    agenda_ids = center_page.get_agenda_ids(motive_id)

                if appointment := self.prebook_appointment(profile_id,
                                                           motive_id,
                                                           place,
                                                           agenda_ids,
                                                           vac_name.lower(),
                                                           start_date,
                                                           end_date,
                                                           excluded_weekdays,
                                                           only_second,
                                                           only_third):
                    yield appointment

        return

    def prebook_appointment(self, profile_id, motive_id, place, agenda_ids, vac_name, start_date, end_date, excluded_weekdays, only_second, only_third):
        practice_id = place['practice_ids'][0]

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

        slot = self.page.find_best_slot(start_date, end_date, excluded_weekdays)
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


        appointment = Appointment()
        appointment.name = place['name']
        appointment.address = place['address']
        appointment.city = place['city']
        appointment.zipcode = place['zipcode']
        appointment.vaccine = vac_name
        appointment.map_url = ('https://www.google.com/maps/embed/v1/place?center=%(lat)s,%(lon)s&q=%(lat)s,%(lon)s'
                               '&key=AIzaSyDpnSscoubUpsnOs48Kt1x5LhAXPSr4gU4') % {'lat': place['latitude'], 'lon': place['longitude']}

        if vac_name != "janssen" and not only_second and not only_third:
            assert slot_date_second

        log('found!', color='green')
        log('  ├╴ Best slot found: %s', parse_date(slot_date_first).strftime('%c'))

        data = {'agenda_ids': '-'.join(agenda_ids),
                'appointment': {'profile_id':    profile_id,
                                'source_action': 'profile',
                                'start_date':    slot_date_first,
                                'visit_motive_ids': str(motive_id),
                                },
                'practice_ids': [practice_id]}

        headers = {
            'content-type': 'application/json',
        }
        self.appointment.go(data=json.dumps(data), headers=headers)

        if self.page.is_error():
            log('  └╴ Appointment not available anymore :( %s', self.page.get_error())
            return False

        appointment.slots.append(parse_date(slot_date_first))

        if vac_name != "janssen" and not only_second and not only_third:  # janssen has only one shot
            self.second_shot_availabilities.go(
                params={'start_date': slot_date_second.split('T')[0],
                        'visit_motive_ids': motive_id,
                        'agenda_ids': '-'.join(agenda_ids),
                        'first_slot': slot_date_first,
                        'insurance_sector': 'public',
                        'practice_ids': practice_id,
                        'limit': 3})

            second_slot = self.page.find_best_slot(excluded_weekdays=excluded_weekdays)
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

            appointment.slots.append(parse_date(slot_date_second))

        appointment.id = self.page.doc['id']

        self.appointment_edit.go(id=appointment.id)

        log('  ├╴ Booking for %(first_name)s %(last_name)s...' % self.patient)

        self.appointment_edit.go(
            id=appointment.id,
            params={'master_patient_id': self.patient['id']}
        )

        appointment.custom_fields = self.page.get_custom_fields()
        return appointment

    def book_appointment(self, appointment, custom_fields):
        headers = {
            'content-type': 'application/json',
        }
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

        self.appointment_post.go(id=appointment.id,
                                 data=json.dumps(data),
                                 headers=headers,
                                 method='PUT')

        if 'redirection' in self.page.doc and not 'confirmed-appointment' in self.page.doc['redirection']:
            log('  ├╴ Open %s to complete', self.BASEURL +
                self.page.doc['redirection'])

        self.appointment_post.go(id=appointment.id)

        return self.page.doc['confirmed']


class DoctolibDE(Doctolib):
    BASEURL = 'https://www.doctolib.de'
    KEY_PFIZER = '6768'
    KEY_PFIZER_SECOND = '6769'
    KEY_PFIZER_THIRD = '9039'
    KEY_MODERNA = '6936'
    KEY_MODERNA_SECOND = '6937'
    KEY_MODERNA_THIRD = '9040'
    KEY_JANSSEN = '7978'
    KEY_ASTRAZENECA = '7109'
    KEY_ASTRAZENECA_SECOND = '7110'
    vaccine_motives = {
        KEY_PFIZER: 'Pfizer',
        KEY_PFIZER_SECOND: 'Zweit.*Pfizer|Pfizer.*Zweit',
        KEY_PFIZER_THIRD: 'Auffrischung.*Pfizer|Pfizer.*Auffrischung|Dritt.*Pfizer|Booster.*Pfizer',
        KEY_MODERNA: 'Moderna',
        KEY_MODERNA_SECOND: 'Zweit.*Moderna|Moderna.*Zweit',
        KEY_MODERNA_THIRD: 'Auffrischung.*Moderna|Moderna.*Auffrischung|Dritt.*Moderna|Booster.*Moderna',
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
