# -*- coding: utf-8 -*-

# Copyright(C) 2018 Julien Veyssier
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

import base64
import re

import lxml.etree as ET
import requests
from woob.capabilities.base import empty

__all__ = ['recipe_to_krecipes_xml']


def recipe_to_krecipes_xml(recipe, author=None):
    """
    Export recipe to KRecipes XML string
    """
    sauthor = u''
    if not empty(recipe.author):
        sauthor += '%s@' % recipe.author

    if author is None:
        sauthor += 'Cookboob'
    else:
        sauthor += author

    header = u'<?xml version="1.0" encoding="UTF-8" ?>\n'
    initial_xml = '''\
<krecipes version='2.0-beta2' lang='fr' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xsi:noNamespaceSchemaLocation='krecipes.xsd'>
<krecipes-recipe id='1'>
</krecipes-recipe>
</krecipes>'''
    doc = ET.fromstring(initial_xml)
    xrecipe = doc.find('krecipes-recipe')
    desc = ET.SubElement(xrecipe, 'krecipes-description')
    title = ET.SubElement(desc, 'title')
    title.text = recipe.title
    authors = ET.SubElement(desc, 'author')
    authors.text = sauthor
    eyield = ET.SubElement(desc, 'yield')
    if not empty(recipe.nb_person):
        amount = ET.SubElement(eyield, 'amount')
        if len(recipe.nb_person) == 1:
            amount.text = '%s' % recipe.nb_person[0]
        else:
            mini = ET.SubElement(amount, 'min')
            mini.text = u'%s' % recipe.nb_person[0]
            maxi = ET.SubElement(amount, 'max')
            maxi.text = u'%s' % recipe.nb_person[1]
        etype = ET.SubElement(eyield, 'type')
        etype.text = 'persons'
    if not empty(recipe.preparation_time):
        preptime = ET.SubElement(desc, 'preparation-time')
        preptime.text = '%02d:%02d' % (recipe.preparation_time / 60, recipe.preparation_time % 60)
    if recipe.picture and recipe.picture.url:
        data = requests.get(recipe.picture.url).content
        datab64 = base64.encodestring(data)[:-1]

        pictures = ET.SubElement(desc, 'pictures')
        pic = ET.SubElement(pictures, 'pic', {'format': 'JPEG', 'id': '1'})
        pic.text = ET.CDATA(datab64)

    if not empty(recipe.ingredients):
        ings = ET.SubElement(xrecipe, 'krecipes-ingredients')
        pat = re.compile('^[0-9,.]*')
        for i in recipe.ingredients:
            sname = u'%s' % i
            samount = ''
            sunit = ''
            first_nums = pat.match(i).group()
            if first_nums != '':
                samount = first_nums
                sname = i.lstrip('0123456789 ')

            ing = ET.SubElement(ings, 'ingredient')
            am = ET.SubElement(ing, 'amount')
            am.text = samount
            unit = ET.SubElement(ing, 'unit')
            unit.text = sunit
            name = ET.SubElement(ing, 'name')
            name.text = sname

    if not empty(recipe.instructions):
        instructions = ET.SubElement(xrecipe, 'krecipes-instructions')
        instructions.text = recipe.instructions

    if not empty(recipe.comments):
        ratings = ET.SubElement(xrecipe, 'krecipes-ratings')
        for c in recipe.comments:
            rating = ET.SubElement(ratings, 'rating')
            if c.author:
                rater = ET.SubElement(rating, 'rater')
                rater.text = c.author
            if c.text:
                com = ET.SubElement(rating, 'comment')
                com.text = c.text
            crits = ET.SubElement(rating, 'criterion')
            if c.rate:
                crit = ET.SubElement(crits, 'criteria')
                critname = ET.SubElement(crit, 'name')
                critname.text = 'Overall'
                critstars = ET.SubElement(crit, 'stars')
                critstars.text = c.rate.split('/')[0]

    return header + ET.tostring(doc, encoding='UTF-8', pretty_print=True).decode('utf-8')

