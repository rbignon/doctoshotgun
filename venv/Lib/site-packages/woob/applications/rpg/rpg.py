# -*- coding: utf-8 -*-

# Copyright(C) 2019-2020 Célande Adrien
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


from woob.capabilities.rpg import CapRPG, Character, Skill, CharacterClass, CollectableItem
from woob.tools.application.repl import ReplApplication, defaultcount


class AppRPG(ReplApplication):
    APPNAME = 'rpg'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2019-YEAR Célande Adrien'
    CAPS = CapRPG
    DESCRIPTION = 'Console application allowing to list informations from a RPG.'
    SHORT_DESCRIPTION = 'manage RPG data'
    DEFAULT_FORMATTER = 'table'
    COLLECTION_OBJECTS = (Character, Skill, CharacterClass, CollectableItem, )

    def do_characters(self, line):
        """
        characters

        List all characters
        """
        print('do characterS')
        print(f'line: "{line}"')
        return self.do_ls(line)

    def do_character(self, line):
        """
        character ID

        Get data on one character
        """
        character_id, = self.parse_command_args(line, 1, 1)
        self.start_format()
        # cannot use get_object because it can be skipped after a ls
        for c in self.do('get_character', character_id):
            self.format(c)

    @defaultcount(20)
    def do_skills(self, line):
        """
        skills [TYPE]

        List all skills
        """
        print('do skills')
        skill_type, = self.parse_command_args(line, 1, 0)
        print('skill type', skill_type)
        self.start_format()
        for skill in self.do('iter_skills', skill_type):
            self.format(skill)

    def do_skill(self, line):
        """
        skill ID

        Details for one skill
        """
        skill_id, = self.parse_command_args(line, 1, 1)
        self.start_format()
        skill = self.get_object(skill_id, 'get_skill', [])
        self.format(skill)

    @defaultcount(20)
    def do_skill_set(self, line):
        """
        skill_set CHARACTER_ID [TYPE]

        List of skills for a character
        """
        character_id, skill_type = self.parse_command_args(line, 2, 1)
        self.start_format()
        for skill in  self.do('iter_skill_set', character_id, skill_type):
            self.format(skill)

    @defaultcount(20)
    def do_classes(self, line):
        """
        classes

        List all character classes
        """
        self.start_format()
        for character_class in self.do('iter_character_classes'):
            self.format(character_class)

    def do_class(self, line):
        """
        class ID

        Details for one character class
        """
        class_id, = self.parse_command_args(line, 1, 1)
        self.start_format()
        character_class = self.get_object(class_id, 'get_character_class', [])
        self.format(character_class)

    @defaultcount(20)
    def do_items(self, line):
        """
        items

        List all collectable items
        """
        self.start_format()
        for item in self.do('iter_collectable_items'):
            self.format(item)

    def do_item(self, line):
        """
        item ID

        Details for one collectable item
        """
        item_id, = self.parse_command_args(line, 1, 1)
        self.start_format()
        item = self.get_object(item_id, 'get_collectable_item', [])
        self.format(item)
