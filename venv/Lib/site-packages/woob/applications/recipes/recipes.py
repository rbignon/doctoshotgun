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

import codecs

from woob.capabilities.recipe import CapRecipe
from woob.capabilities.base import empty
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import IFormatter, PrettyFormatter
from woob.tools.capabilities.recipe import recipe_to_krecipes_xml

__all__ = ['AppRecipes']


class RecipeInfoFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'title', 'preparation_time', 'ingredients', 'instructions')

    def format_obj(self, obj, alias):
        result = u'%s%s%s\n' % (self.BOLD, obj.title, self.NC)
        result += 'ID: %s\n' % obj.fullid
        if not empty(obj.author):
            result += 'Author: %s\n' % obj.author
        if not empty(obj.preparation_time):
            result += 'Preparation time: %smin\n' % obj.preparation_time
        if not empty(obj.cooking_time):
            result += 'Cooking time: %smin\n' % obj.cooking_time
        if not empty(obj.nb_person):
            nbstr = '-'.join(str(num) for num in obj.nb_person)
            result += 'Amount of people: %s\n' % nbstr
        result += '\n%sIngredients%s\n' % (self.BOLD, self.NC)
        for i in obj.ingredients:
            result += '  * %s\n' % i
        result += '\n%sInstructions%s\n' % (self.BOLD, self.NC)
        result += '%s\n' % obj.instructions
        if not empty(obj.comments):
            result += '\n%sComments%s\n' % (self.BOLD, self.NC)
            for c in obj.comments:
                result += u'  * %s\n' % c
        return result


class RecipeListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'title', 'short_description', 'preparation_time')

    def get_title(self, obj):
        return obj.title

    def get_description(self, obj):
        result = u''
        if not empty(obj.preparation_time):
            result += 'prep time: %smin' % obj.preparation_time
        if not empty(obj.short_description):
            result += 'description: %s\n' % obj.short_description
        return result.strip()


class AppRecipes(ReplApplication):
    APPNAME = 'recipes'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2013-YEAR Julien Veyssier'
    DESCRIPTION = "Console application allowing to search for recipes on various websites."
    SHORT_DESCRIPTION = "search and consult recipes"
    CAPS = CapRecipe
    EXTRA_FORMATTERS = {'recipe_list': RecipeListFormatter,
                        'recipe_info': RecipeInfoFormatter
                        }
    COMMANDS_FORMATTERS = {'search':    'recipe_list',
                           'info':      'recipe_info'
                           }

    def complete_info(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_info(self, id):
        """
        info ID

        Get information about a recipe.
        """
        recipe = self.get_object(id, 'get_recipe')
        if not recipe:
            print('Recipe not found: %s' % id, file=self.stderr)
            return 3

        self.start_format()
        self.format(recipe)

    def complete_export(self, text, line, *ignored):
        args = line.split(' ', 2)
        if len(args) == 2:
            return self._complete_object()
        elif len(args) >= 3:
            return self.path_completer(args[2])

    def do_export(self, line):
        """
        export ID [FILENAME]

        Export the recipe to a KRecipes XML file
        FILENAME is where to write the file. If FILENAME is '-',
        the file is written to stdout.
        """
        id, dest = self.parse_command_args(line, 2, 1)

        _id, backend_name = self.parse_id(id)

        if dest is None:
            dest = '%s.kreml' % _id

        recipe = self.get_object(id, 'get_recipe')

        if recipe:
            xmlstring = recipe_to_krecipes_xml(recipe, backend_name or None)
            if dest == '-':
                print(xmlstring)
            else:
                if not dest.endswith('.kreml'):
                    dest += '.kreml'
                try:
                    with codecs.open(dest, 'w', 'utf-8') as f:
                        f.write(xmlstring)
                except IOError as e:
                    print('Unable to write .kreml in "%s": %s' % (dest, e), file=self.stderr)
                    return 1
            return
        print('Recipe "%s" not found' % id, file=self.stderr)
        return 3

    @defaultcount(10)
    def do_search(self, pattern):
        """
        search [PATTERN]

        Search recipes.
        """
        self.change_path([u'search'])
        self.start_format(pattern=pattern)
        for recipe in self.do('iter_recipes', pattern=pattern):
            self.cached_format(recipe)
