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


from .base import Capability, BaseObject, StringField, IntField, Field
from .date import DateField


__all__ = ['Movie', 'Person', 'CapCinema']


class Movie(BaseObject):
    """
    Movie object.
    """
    original_title    = StringField('Original title of the movie')
    other_titles      = Field('Titles in other countries', list)
    release_date      = DateField('Release date of the movie')
    all_release_dates = StringField('Release dates list of the movie')
    duration          = IntField('Duration of the movie in minutes')
    short_description = StringField('Short description of the movie')
    genres            = Field('Genres of the movie', list)
    pitch             = StringField('Short story description of the movie')
    country           = StringField('Origin country of the movie')
    note              = StringField('Notation of the movie')
    roles             = Field('Lists of Persons related to the movie indexed by roles', dict)
    thumbnail_url     = StringField('Url of movie thumbnail')

    def __init__(self, id, original_title, url=None):
        super(Movie, self).__init__(id, url)
        self.original_title = original_title

    def get_roles_by_person_name(self, name):
        for role in self.roles.keys():
            if name.lower() in [person[1].lower() for person in self.roles[role]]:
                return role
        return None

    def get_roles_by_person_id(self, id):
        result = []
        for role in self.roles.keys():
            if id in [person[0] for person in self.roles[role]]:
                result.append(role)

        return result


class Person(BaseObject):
    """
    Person object.
    """
    name              = StringField('Star name of a person')
    real_name         = StringField('Real name of a person')
    birth_date        = DateField('Birth date of a person')
    death_date        = DateField('Death date of a person')
    birth_place       = StringField('City and country of birth of a person')
    gender            = StringField('Gender of a person')
    nationality       = StringField('Nationality of a person')
    short_biography   = StringField('Short biography of a person')
    biography         = StringField('Full biography of a person')
    short_description = StringField('Short description of a person')
    roles             = Field('Lists of movies related to the person indexed by roles', dict)
    thumbnail_url     = StringField('Url of person thumbnail')

    def __init__(self, id, name, url=None):
        super(Person, self).__init__(id, url)
        self.name = name

    def get_roles_by_movie_title(self, title):
        for role in self.roles.keys():
            for mt in [movie[1] for movie in self.roles[role]]:
                # title we have is included ?
                if title.lower() in mt.lower():
                    return role
        return None

    def get_roles_by_movie_id(self, id):
        result = []
        for role in self.roles.keys():
            if id in [movie[0] for movie in self.roles[role]]:
                result.append(role)

        return result


class CapCinema(Capability):
    """
    Cinema databases.
    """

    def iter_movies(self, pattern):
        """
        Search movies and iterate on results.

        :param pattern: pattern to search
        :type pattern: str
        :rtype: iter[:class:`Movies`]
        """
        raise NotImplementedError()

    def get_movie(self, _id):
        """
        Get a movie object from an ID.

        :param _id: ID of movie
        :type _id: str
        :rtype: :class:`Movie`
        """
        raise NotImplementedError()

    def get_movie_releases(self, _id, country=None):
        """
        Get a list of a movie releases from an ID.

        :param _id: ID of movie
        :type _id: str
        :rtype: :class:`String`
        """
        raise NotImplementedError()

    def iter_movie_persons(self, _id, role=None):
        """
        Get the list of persons who are related to a movie.

        :param _id: ID of movie
        :type _id: str
        :rtype: iter[:class:`Person`]
        """
        raise NotImplementedError()

    def iter_persons(self, pattern):
        """
        Search persons and iterate on results.

        :param pattern: pattern to search
        :type pattern: str
        :rtype: iter[:class:`persons`]
        """
        raise NotImplementedError()

    def get_person(self, _id):
        """
        Get a person object from an ID.

        :param _id: ID of person
        :type _id: str
        :rtype: :class:`Person`
        """
        raise NotImplementedError()

    def iter_person_movies(self, _id, role=None):
        """
        Get the list of movies related to a person.

        :param _id: ID of person
        :type _id: str
        :rtype: iter[:class:`Movie`]
        """
        raise NotImplementedError()

    def iter_person_movies_ids(self, _id):
        """
        Get the list of movie ids related to a person.

        :param _id: ID of person
        :type _id: str
        :rtype: iter[str]
        """
        raise NotImplementedError()

    def iter_movie_persons_ids(self, _id):
        """
        Get the list of person ids related to a movie.

        :param _id: ID of movie
        :type _id: str
        :rtype: iter[str]
        """
        raise NotImplementedError()

    def get_person_biography(self, id):
        """
        Get the person full biography.

        :param _id: ID of person
        :type _id: str
        :rtype: str
        """
        raise NotImplementedError()
