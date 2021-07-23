# -*- coding: utf-8 -*-

# Copyright(C) 2018 Phyks
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

from __future__ import unicode_literals

import itertools
from collections import Counter

from woob.capabilities.base import empty
from woob.capabilities.housing import POSTS_TYPES


class HousingTest(object):
    """
    Testing class to standardize the housing modules tests.
    """
    # Fields to be checked for values across all items in housings list
    FIELDS_ALL_HOUSINGS_LIST = [
        "id", "type", "advert_type", "house_type", "url", "title", "area",
        "cost", "currency", "utilities", "date", "location", "station", "text",
        "phone", "rooms", "bedrooms", "DPE", "GES", "details"
    ]
    # Fields to be checked for at least one item in housings list
    FIELDS_ANY_HOUSINGS_LIST = [
        "photos"
    ]
    # Fields to be checked for values across all items when querying
    # individually
    FIELDS_ALL_SINGLE_HOUSING = [
        "id", "url", "type", "advert_type", "house_type", "title", "area",
        "cost", "currency", "utilities", "date", "location", "station", "text",
        "phone", "rooms", "bedrooms", "DPE", "GES", "details"
    ]
    # Fields to be checked for values at least once for all items when querying
    # individually
    FIELDS_ANY_SINGLE_HOUSING = [
        "photos"
    ]
    # Some backends cannot distinguish between rent and furnished rent for
    # single housing post. Set this to True if this is the case.
    DO_NOT_DISTINGUISH_FURNISHED_RENT = False

    def assertNotEmpty(self, obj, field):
        self.assertFalse(
            empty(getattr(obj, field)),
            'Field "%s" is empty and should not be.' % field
        )


    def check_housing_lists(self, query):
        results = list(itertools.islice(
            self.backend.search_housings(query),
            20
        ))
        self.assertGreater(len(results), 0)

        for field in self.FIELDS_ANY_HOUSINGS_LIST:
            self.assertTrue(
                any(not empty(getattr(x, field)) for x in results),
                'Missing a "%s" field.' % field
            )

        for x in results:
            if 'type' in self.FIELDS_ALL_HOUSINGS_LIST:
                self.assertEqual(x.type, query.type)
            if 'advert_type' in self.FIELDS_ALL_HOUSINGS_LIST:
                self.assertIn(x.advert_type, query.advert_types)
            if 'house_type' in self.FIELDS_ALL_HOUSINGS_LIST:
                self.assertIn(x.house_type, query.house_types)
            for field in self.FIELDS_ALL_HOUSINGS_LIST:
                self.assertNotEmpty(x, field)
            if not empty(x.cost):
                self.assertNotEmpty(x, 'price_per_meter')
            for photo in x.photos:
                self.assertRegexpMatches(photo.url, r'^http(s?)://')

        return results

    def check_single_housing_all(self, housing,
                                 type, house_type, advert_type):
        for field in self.FIELDS_ALL_SINGLE_HOUSING:
            self.assertNotEmpty(housing, field)
        if 'type' in self.FIELDS_ALL_SINGLE_HOUSING:
            if (
                self.DO_NOT_DISTINGUISH_FURNISHED_RENT and
                type in [POSTS_TYPES.RENT, POSTS_TYPES.FURNISHED_RENT]
            ):
                self.assertIn(housing.type,
                              [POSTS_TYPES.RENT, POSTS_TYPES.FURNISHED_RENT])
            else:
                self.assertEqual(housing.type, type)
        if 'house_type' in self.FIELDS_ALL_SINGLE_HOUSING:
            if not empty(house_type):
                self.assertEqual(housing.house_type, house_type)
            else:
                self.assertNotEmpty(housing, 'house_type')
        if 'advert_type' in self.FIELDS_ALL_SINGLE_HOUSING:
            self.assertEqual(housing.advert_type, advert_type)

    def check_single_housing_any(self, housing, counter):
        for field in self.FIELDS_ANY_SINGLE_HOUSING:
            if not empty(getattr(housing, field)):
                counter[field] += 1
        for photo in housing.photos:
            self.assertRegexpMatches(photo.url, r'^http(s?)://')
        return counter

    def check_against_query(self, query):
        # Check housing listing results
        results = self.check_housing_lists(query)

        # Check mandatory fields in all housings
        housing = self.backend.get_housing(results[0].id)
        if 'phone' in self.FIELDS_ANY_SINGLE_HOUSING + self.FIELDS_ALL_SINGLE_HOUSING:
            self.backend.fillobj(housing, 'phone')  # Fetch phone
        self.check_single_housing_all(
            housing,
            results[0].type,
            results[0].house_type,
            results[0].advert_type
        )

        # Check fields that should appear in at least one housing
        counter = Counter()
        counter = self.check_single_housing_any(housing, counter)
        for result in results[1:]:
            if all(counter[field] > 0 for field in
                   self.FIELDS_ANY_SINGLE_HOUSING):
                break
            housing = self.backend.get_housing(result.id)
            if 'phone' in self.FIELDS_ANY_SINGLE_HOUSING + self.FIELDS_ALL_SINGLE_HOUSING:
                self.backend.fillobj(housing, 'phone')  # Fetch phone
            counter = self.check_single_housing_any(housing, counter)
        for field in self.FIELDS_ANY_SINGLE_HOUSING:
            self.assertGreater(
                counter[field],
                0,
                'Optional field "%s" should appear at least once.' % field
            )
