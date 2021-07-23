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
from .image import BaseImage


__all__ = ['CapRecipe', 'Recipe', 'Comment']


class Comment(BaseObject):
    author = StringField('Author of the comment')
    rate = StringField('Rating')
    text = StringField('Comment')

    def __unicode__(self):
        result = u''
        if self.author:
            result += u'author: %s, ' % self.author
        if self.rate:
            result += u'note: %s, ' % self.rate
        if self.text:
            result += u'comment: %s' % self.text
        return result


class Recipe(BaseObject):
    """
    Recipe object.
    """
    title =             StringField('Title of the recipe')
    author =            StringField('Author name of the recipe')
    picture =           Field('Picture of the dish', BaseImage)
    short_description = StringField('Short description of a recipe')
    nb_person =         Field('The recipe was made for this amount of persons', list)
    preparation_time =  IntField('Preparation time of the recipe in minutes')
    cooking_time =      IntField('Cooking time of the recipe in minutes')
    ingredients =       Field('Ingredient list necessary for the recipe', list)
    instructions =      StringField('Instruction step list of the recipe')
    comments =          Field('User comments about the recipe', list)

    def __init__(self, id='', title=u'', url=None):
        super(Recipe, self).__init__(id, url)
        self.title = title


class CapRecipe(Capability):
    """
    Recipe providers.
    """

    def iter_recipes(self, pattern):
        """
        Search recipes and iterate on results.

        :param pattern: pattern to search
        :type pattern: str
        :rtype: iter[:class:`Recipe`]
        """
        raise NotImplementedError()

    def get_recipe(self, _id):
        """
        Get a recipe object from an ID.

        :param _id: ID of recipe
        :type _id: str
        :rtype: :class:`Recipe`
        """
        raise NotImplementedError()
