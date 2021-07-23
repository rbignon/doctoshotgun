# -*- coding: utf-8 -*-

# Copyright(C) 2013 Julien Veyssier
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

from datetime import datetime

from woob.applications.torrent.torrent import TorrentInfoFormatter, TorrentListFormatter
from woob.applications.subtitles.subtitles import SubtitleInfoFormatter, SubtitleListFormatter
from woob.capabilities.torrent import CapTorrent, MagnetOnly
from woob.capabilities.cinema import CapCinema
from woob.capabilities.subtitle import CapSubtitle
from woob.capabilities.base import empty, NotAvailable
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import IFormatter, PrettyFormatter
from woob.core import CallErrors


__all__ = ['AppCinema']

ROLE_LIST = ['actor', 'director', 'writer', 'composer', 'producer']
COUNTRY_LIST = ['us', 'fr', 'de', 'jp']


class MovieInfoFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'original_title', 'release_date',
                        'other_titles', 'duration', 'pitch', 'note', 'roles', 'country')

    def format_obj(self, obj, alias):
        result = u'%s%s%s\n' % (self.BOLD, obj.original_title, self.NC)
        result += 'ID: %s\n' % obj.fullid
        if not empty(obj.release_date):
            result += 'Released: %s\n' % obj.release_date.strftime('%Y-%m-%d')
        result += 'Country: %s\n' % obj.country
        if not empty(obj.duration):
            result += 'Duration: %smin\n' % obj.duration
        result += 'Note: %s\n' % obj.note
        if not empty(obj.genres):
            result += '\n%sGenres%s\n' % (self.BOLD, self.NC)
            for g in obj.genres:
                result += ' * %s\n' % g
        if not empty(obj.roles):
            result += '\n%sRelated persons%s\n' % (self.BOLD, self.NC)
            for role, lpersons in obj.roles.items():
                result += ' -- %s\n' % role
                for person in lpersons:
                    result += '   * %s\n' % person[1]
        if not empty(obj.other_titles):
            result += '\n%sOther titles%s\n' % (self.BOLD, self.NC)
            for t in obj.other_titles:
                result += ' * %s\n' % t
        if not empty(obj.pitch):
            result += '\n%sStory%s\n' % (self.BOLD, self.NC)
            result += '%s' % obj.pitch
        return result


class MovieListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'original_title', 'short_description')

    def get_title(self, obj):
        return obj.original_title

    def get_description(self, obj):
        result = u''
        if not empty(obj.short_description):
            result = obj.short_description
        return result


class MovieReleasesFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'original_title', 'all_release_dates')

    def get_title(self, obj):
        return u'Releases of %s' % obj.original_title

    def get_description(self, obj):
        return u'\n%s' % obj.all_release_dates


def yearsago(years, from_date=None):
    if from_date is None:
        from_date = datetime.now()
    try:
        return from_date.replace(year=from_date.year - years)
    except:
        # Must be 2/29
        assert from_date.month == 2 and from_date.day == 29
        return from_date.replace(month=2, day=28,
                                 year=from_date.year-years)


def num_years(begin, end=None):
    if end is None:
        end = datetime.now()
    num_years = int((end - begin).days / 365.25)
    if begin > yearsago(num_years, end):
        return num_years - 1
    else:
        return num_years


class PersonInfoFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'name', 'birth_date', 'birth_place', 'short_biography')

    def format_obj(self, obj, alias):
        result = u'%s%s%s\n' % (self.BOLD, obj.name, self.NC)
        result += 'ID: %s\n' % obj.fullid
        if not empty(obj.real_name):
            result += 'Real name: %s\n' % obj.real_name
        if not empty(obj.birth_place):
            result += 'Birth place: %s\n' % obj.birth_place
        if not empty(obj.birth_date):
            result += 'Birth date: %s\n' % obj.birth_date.strftime('%Y-%m-%d')
            if not empty(obj.death_date):
                age = num_years(obj.birth_date, obj.death_date)
                result += 'Death date: %s at %s years old\n' % (obj.death_date.strftime('%Y-%m-%d'), age)
            else:
                age = num_years(obj.birth_date)
                result += 'Age: %s\n' % age
        if not empty(obj.gender):
            result += 'Gender: %s\n' % obj.gender
        if not empty(obj.nationality):
            result += 'Nationality: %s\n' % obj.nationality
        if not empty(obj.roles):
            result += '\n%sRelated movies%s\n' % (self.BOLD, self.NC)
            for role, lmovies in obj.roles.items():
                result += ' -- %s\n' % role
                for movie in lmovies:
                    result += '   * %s\n' % movie[1]
        if not empty(obj.short_biography):
            result += '\n%sShort biography%s\n' % (self.BOLD, self.NC)
            result += '%s' % obj.short_biography
        return result


class PersonListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'name', 'short_description')

    def get_title(self, obj):
        return obj.name

    def get_description(self, obj):
        result = u''
        if not empty(obj.short_description):
            result = obj.short_description
        return result


class PersonBiographyFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'name', 'biography')

    def get_title(self, obj):
        return u'Biography of %s' % obj.name

    def get_description(self, obj):
        result = u'\n%s' % obj.biography
        return result


class AppCinema(ReplApplication):
    APPNAME = 'cinema'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2013-YEAR Julien Veyssier'
    DESCRIPTION = "Console application allowing to search for movies and persons on various cinema databases " \
                  ", list persons related to a movie, list movies related to a person and list common movies " \
                  "of two persons."
    SHORT_DESCRIPTION = "search movies and persons around cinema"
    CAPS = (CapCinema, CapTorrent, CapSubtitle)
    EXTRA_FORMATTERS = {'movie_list': MovieListFormatter,
                        'movie_info': MovieInfoFormatter,
                        'movie_releases': MovieReleasesFormatter,
                        'person_list': PersonListFormatter,
                        'person_info': PersonInfoFormatter,
                        'person_bio': PersonBiographyFormatter,
                        'torrent_list': TorrentListFormatter,
                        'torrent_info': TorrentInfoFormatter,
                        'subtitle_list': SubtitleListFormatter,
                        'subtitle_info': SubtitleInfoFormatter
                        }
    COMMANDS_FORMATTERS = {'search_movie':    'movie_list',
                           'info_movie':      'movie_info',
                           'search_person':   'person_list',
                           'info_person':     'person_info',
                           'casting':         'person_list',
                           'filmography':     'movie_list',
                           'biography':     'person_bio',
                           'releases':     'movie_releases',
                           'movies_in_common': 'movie_list',
                           'persons_in_common': 'person_list',
                           'search_torrent':    'torrent_list',
                           'search_movie_torrent':    'torrent_list',
                           'info_torrent':      'torrent_info',
                           'search_subtitle':    'subtitle_list',
                           'search_movie_subtitle':    'subtitle_list',
                           'info_subtitle':      'subtitle_info'
                           }

    def complete_filmography(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 3:
            return ROLE_LIST

    def complete_casting(self, text, line, *ignored):
        return self.complete_filmography(text, line, ignored)

    def do_movies_in_common(self, line):
        """
        movies_in_common  person_ID  person_ID

        Get the list of common movies between two persons.
        """
        id1, id2 = self.parse_command_args(line, 2, 1)

        person1 = self.get_object(id1, 'get_person', caps=CapCinema)
        if not person1:
            print('Person not found: %s' % id1, file=self.stderr)
            return 3
        person2 = self.get_object(id2, 'get_person', caps=CapCinema)
        if not person2:
            print('Person not found: %s' % id2, file=self.stderr)
            return 3

        initial_count = self.options.count
        self.options.count = None

        lid1 = []
        for id in self.do('iter_person_movies_ids', person1.id, caps=CapCinema):
            lid1.append(id)
        lid2 = []
        for id in self.do('iter_person_movies_ids', person2.id, caps=CapCinema):
            lid2.append(id)
        self.options.count = initial_count
        inter = list(set(lid1) & set(lid2))

        chrono_list = []
        for common in inter:
            movie = self.get_object(common, 'get_movie', caps=CapCinema)
            role1 = movie.get_roles_by_person_id(person1.id)
            if not role1:
                role1 = movie.get_roles_by_person_name(person1.name)
            role2 = movie.get_roles_by_person_id(person2.id)
            if not role2:
                role2 = movie.get_roles_by_person_name(person2.name)

            if (movie.release_date != NotAvailable):
                year = movie.release_date.year
            else:
                year = '????'
            movie.short_description = '(%s) %s as %s ; %s as %s'%(year, person1.name, ', '.join(role1), person2.name, ', '.join(role2))
            if movie:
                i = 0
                while (i<len(chrono_list) and movie.release_date != NotAvailable and
                      (chrono_list[i].release_date == NotAvailable or year > chrono_list[i].release_date.year)):
                    i += 1
                chrono_list.insert(i, movie)

        for movie in chrono_list:
            self.cached_format(movie)

    def do_persons_in_common(self, line):
        """
        persons_in_common  movie_ID  movie_ID

        Get the list of common persons between two movies.
        """
        id1, id2 = self.parse_command_args(line, 2, 1)

        movie1 = self.get_object(id1, 'get_movie', caps=CapCinema)
        if not movie1:
            print('Movie not found: %s' % id1, file=self.stderr)
            return 3
        movie2 = self.get_object(id2, 'get_movie', caps=CapCinema)
        if not movie2:
            print('Movie not found: %s' % id2, file=self.stderr)
            return 3

        initial_count = self.options.count
        self.options.count = None

        lid1 = []
        for id in self.do('iter_movie_persons_ids', movie1.id, caps=CapCinema):
            lid1.append(id)
        lid2 = []
        for id in self.do('iter_movie_persons_ids', movie2.id, caps=CapCinema):
            lid2.append(id)
        self.options.count = initial_count
        inter = list(set(lid1) & set(lid2))
        for common in inter:
            person = self.get_object(common, 'get_person', caps=CapCinema)
            role1 = person.get_roles_by_movie_id(movie1.id)
            if not role1:
                role1 = person.get_roles_by_movie_title(movie1.original_title)
            role2 = person.get_roles_by_movie_id(movie2.id)
            if not role2:
                role2 = person.get_roles_by_movie_title(movie2.original_title)
            person.short_description = '%s in %s ; %s in %s'%(', '.join(role1), movie1.original_title, ', '.join(role2), movie2.original_title)
            self.cached_format(person)

    def do_info_movie(self, id):
        """
        info_movie  movie_ID

        Get information about a movie.
        """
        movie = self.get_object(id, 'get_movie', caps=CapCinema)

        if not movie:
            print('Movie not found: %s' % id, file=self.stderr)
            return 3

        self.start_format()
        self.format(movie)

    def do_info_person(self, id):
        """
        info_person  person_ID

        Get information about a person.
        """
        person = self.get_object(id, 'get_person', caps=CapCinema)

        if not person:
            print('Person not found: %s' % id, file=self.stderr)
            return 3

        self.start_format()
        self.format(person)

    @defaultcount(10)
    def do_search_movie(self, pattern):
        """
        search_movie  [PATTERN]

        Search movies.
        """
        self.change_path([u'search movies'])
        if not pattern:
            pattern = None

        self.start_format(pattern=pattern)
        for movie in self.do('iter_movies', pattern=pattern, caps=CapCinema):
            self.cached_format(movie)

    @defaultcount(10)
    def do_search_person(self, pattern):
        """
        search_person  [PATTERN]

        Search persons.
        """
        self.change_path([u'search persons'])
        if not pattern:
            pattern = None

        self.start_format(pattern=pattern)
        for person in self.do('iter_persons', pattern=pattern, caps=CapCinema):
            self.cached_format(person)

    def do_casting(self, line):
        """
        casting  movie_ID  [ROLE]

        List persons related to a movie.
        If ROLE is given, filter by ROLE
        """
        movie_id, role = self.parse_command_args(line, 2, 1)

        movie = self.get_object(movie_id, 'get_movie', caps=CapCinema)
        if not movie:
            print('Movie not found: %s' % id, file=self.stderr)
            return 3

        for person in self.do('iter_movie_persons', movie.id, role, backends=movie.backend, caps=CapCinema):
            self.cached_format(person)

    def do_filmography(self, line):
        """
        filmography  person_ID  [ROLE]

        List movies of a person.
        If ROLE is given, filter by ROLE
        """
        person_id, role = self.parse_command_args(line, 2, 1)

        person = self.get_object(person_id, 'get_person', caps=CapCinema)
        if not person:
            print('Person not found: %s' % id, file=self.stderr)
            return 3

        for movie in self.do('iter_person_movies', person.id, role, backends=person.backend, caps=CapCinema):
            self.cached_format(movie)

    def do_biography(self, person_id):
        """
        biography  person_ID

        Show the complete biography of a person.
        """
        person = self.get_object(person_id, 'get_person', ('name', 'biography'), caps=CapCinema)
        if not person:
            print('Person not found: %s' % person_id, file=self.stderr)
            return 3

        self.start_format()
        self.format(person)

    def complete_releases(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()
        if len(args) == 3:
            return COUNTRY_LIST

    def do_releases(self, line):
        """
        releases  movie_ID [COUNTRY]

        Get releases dates of a movie.
        If COUNTRY is given, show release in this country.
        """
        id, country = self.parse_command_args(line, 2, 1)

        movie = self.get_object(id, 'get_movie', ('original_title'), caps=CapCinema)
        if not movie:
            print('Movie not found: %s' % id, file=self.stderr)
            return 3

        # i would like to clarify with fillobj but how could i fill the movie AND choose the country ?
        for release in self.do('get_movie_releases', movie.id, country, caps=CapCinema, backends=movie.backend):
            if not empty(release):
                movie.all_release_dates = u'%s' % (release)
            else:
                print('Movie releases not found for %s' % movie.original_title, file=self.stderr)
                return 3
        self.start_format()
        self.format(movie)

    # ================== TORRENT ==================

    def complete_info_torrent(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_info_torrent(self, id):
        """
        info_torrent ID

        Get information about a torrent.
        """

        torrent = self.get_object(id, 'get_torrent', caps=CapTorrent)
        if not torrent:
            print('Torrent not found: %s' % id, file=self.stderr)
            return 3

        self.start_format()
        self.format(torrent)

    def complete_getfile_torrent(self, text, line, *ignored):
        args = line.split(' ', 2)
        if len(args) == 2:
            return self._complete_object()
        elif len(args) >= 3:
            return self.path_completer(args[2])

    def do_getfile_torrent(self, line):
        """
        getfile_torrent ID [FILENAME]

        Get the .torrent file.
        FILENAME is where to write the file. If FILENAME is '-',
        the file is written to stdout.
        """
        id, dest = self.parse_command_args(line, 2, 1)

        _id, backend_name = self.parse_id(id)

        if dest is None:
            dest = '%s.torrent' % _id

        try:
            for buf in self.do('get_torrent_file', _id, backends=backend_name, caps=CapTorrent):
                if buf:
                    if dest == '-':
                        print(buf)
                    else:
                        try:
                            with open(dest, 'wb') as f:
                                f.write(buf)
                        except IOError as e:
                            print('Unable to write .torrent in "%s": %s' % (dest, e), file=self.stderr)
                            return 1
                    return
        except CallErrors as errors:
            for backend, error, backtrace in errors:
                if isinstance(error, MagnetOnly):
                    print(u'Error(%s): No direct URL available, '
                          u'please provide this magnet URL '
                          u'to your client:\n%s' % (backend, error.magnet), file=self.stderr)
                    return 4
                else:
                    self.bcall_error_handler(backend, error, backtrace)

        print('Torrent "%s" not found' % id, file=self.stderr)
        return 3

    @defaultcount(10)
    def do_search_torrent(self, pattern):
        """
        search_torrent [PATTERN]

        Search torrents.
        """
        self.change_path([u'search torrent'])
        if not pattern:
            pattern = None

        self.start_format(pattern=pattern)
        for torrent in self.do('iter_torrents', pattern=pattern, caps=CapTorrent):
            self.cached_format(torrent)

    @defaultcount(10)
    def do_search_movie_torrent(self, id):
        """
        search_movie_torrent movie_ID

        Search torrents of movie_ID.
        """
        movie = self.get_object(id, 'get_movie', ('original_title'), caps=CapCinema)
        if not movie:
            print('Movie not found: %s' % id, file=self.stderr)
            return 3

        pattern = movie.original_title

        self.change_path([u'search torrent'])
        if not pattern:
            pattern = None

        self.start_format(pattern=pattern)
        for torrent in self.do('iter_torrents', pattern=pattern, caps=CapTorrent):
            self.cached_format(torrent)

    # ================== SUBTITLE ==================

    def complete_info_subtitle(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_info_subtitle(self, id):
        """
        info_subtitle subtitle_ID

        Get information about a subtitle.
        """

        subtitle = self.get_object(id, 'get_subtitle', caps=CapCinema)
        if not subtitle:
            print('Subtitle not found: %s' % id, file=self.stderr)
            return 3

        self.start_format()
        self.format(subtitle)

    def complete_getfile_subtitle(self, text, line, *ignored):
        args = line.split(' ', 2)
        if len(args) == 2:
            return self._complete_object()
        elif len(args) >= 3:
            return self.path_completer(args[2])

    def do_getfile_subtitle(self, line):
        """
        getfile_subtitle subtitle_ID [FILENAME]

        Get the subtitle or archive file.
        FILENAME is where to write the file. If FILENAME is '-',
        the file is written to stdout.
        """
        id, dest = self.parse_command_args(line, 2, 1)

        _id, backend_name = self.parse_id(id)

        if dest is None:
            dest = '%s' % _id

        for buf in self.do('get_subtitle_file', _id, backends=backend_name, caps=CapSubtitle):
            if buf:
                if dest == '-':
                    print(buf)
                else:
                    try:
                        with open(dest, 'w') as f:
                            f.write(buf)
                    except IOError as e:
                        print('Unable to write file in "%s": %s' % (dest, e), file=self.stderr)
                        return 1
                return

        print('Subtitle "%s" not found' % id, file=self.stderr)
        return 3

    @defaultcount(10)
    def do_search_subtitle(self, line):
        """
        search_subtitle language [PATTERN]

        Search subtitles.

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
        language, pattern = self.parse_command_args(line, 2, 1)
        self.change_path([u'search subtitle'])
        if not pattern:
            pattern = None

        self.start_format(pattern=pattern)
        for subtitle in self.do('iter_subtitles', language=language, pattern=pattern, caps=CapSubtitle):
            self.cached_format(subtitle)

    @defaultcount(10)
    def do_search_movie_subtitle(self, line):
        """
        search_movie_subtitle language movie_ID

        Search subtitles of movie_ID.

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
        language, id = self.parse_command_args(line, 2, 2)
        movie = self.get_object(id, 'get_movie', ('original_title'), caps=CapCinema)
        if not movie:
            print('Movie not found: %s' % id, file=self.stderr)
            return 3

        pattern = movie.original_title
        self.change_path([u'search subtitle'])
        if not pattern:
            pattern = None

        self.start_format(pattern=pattern)
        for subtitle in self.do('iter_subtitles', language=language, pattern=pattern, caps=CapSubtitle):
            self.cached_format(subtitle)
