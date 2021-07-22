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


from woob.capabilities.base import find_object

from .base import (
    BaseObject,
    Field, StringField,  BoolField,
    EnumField, Enum,
    UserError,
)
from .collection import CapCollection

__all__ = ['CapRPG', 'Character', 'Skill', 'CharacterClass', 'CollectableItem']


class CharacterNotFound(UserError):
    """ Raised when a character is not found """
    def __init__(self, msg='Character not found'):
        super(CharacterNotFound, self).__init__(msg)


class SkillNotFound(UserError):
    """ Raised when a skill is not found """
    def __init__(self, msg='Skill not found'):
        super(SkillNotFound, self).__init__(msg)


class CharacterClassNotFound(UserError):
    """ Raised when a class is not found """
    def __init__(self, msg='Class not found'):
        super(CharacterClassNotFound, self).__init__(msg)


class CollectableItemNotFound(UserError):
    """ Raised when an item is not found """
    def __init__(self, msg='Item not found'):
        super(CollectableItemNotFound, self).__init__(msg)


class ListField(Field):
    """ Field made of a list """
    def __init__(self, doc, **kwargs):
        if 'default' not in kwargs:
            kwargs['default'] = []
        super(ListField, self).__init__(doc, list, **kwargs)


class DictField(Field):
    """ Field made of a dict """
    def __init__(self, doc, **kwargs):
        if 'default' not in kwargs:
            kwargs['default'] = {}
        super(DictField, self).__init__(doc, dict, **kwargs)


class BaseRPGObject(BaseObject):
    """ Object used to build up all the objects of the CapRPG """
    # TODO: check id and origin for duplicates
    name = StringField('Name', mandatory=True)
    description = StringField('Description', mandatory=False)
    origin = StringField('From which game/platform the object comes from', mandatory=False)
    picture = StringField('URL of a picture', mandatory=False)


class CharacterClass(BaseRPGObject):
    """ CharacterClass of a character """
    pass


class SkillType(Enum):
    """
    Types of skill
    """
    UNKNOWN = 0
    """UNKNOWN: Unknown type"""

    PASSIVE = 1
    """PASSIVE: The effects of the skill are always on. The skill does not need to be activated."""

    ACTIVE = 2
    """ACTIVE: The skill must be activated."""


class SkillTarget(Enum):
    """
    Target of a skill
    """
    UNKNOWN = 0
    """UNKNOWN: Unknown target"""

    SELF = 1
    """SELF: The target is the one that launched it"""

    FOE = 2
    """FOE: The target is a different character than the one who launched it"""

    SELF_AND_FOE = 3
    """SELF_AND_FOE: The target is a different character and the one who lanched it"""

    FIELD = 4
    """FIELD: The target is the field or the environment"""


class SkillCategory(Enum):
    """
    Category of a skill
    """
    UNKNOWN = 0
    """UNKNOWN: Unknown category"""

    PHYSICAL = 1
    """PHYSICAL: The skill is meant to deal physical damages (and effects)"""

    MAGICAL = 2
    """MAGICAL: The skill is meant to deal magical or special damages (and effects)"""

    PHYSICAL_AND_MAGICAL = 3
    """PHYSICAL_AND_MAGICAM: The skill is meant to deal physical and magical damages (and effects)"""

    STATUS = 4
    """STATUS: The skill does not deal direct damages."""


class Skill(BaseRPGObject):
    """ Skill of a character """
    type = EnumField('Type of skill', SkillType, mandatory=True, default=SkillType.UNKNOWN)
    target = EnumField('Target of the skill', SkillTarget, mandatory=True, default=SkillTarget.UNKNOWN)

    statistics = DictField('Dict of statistics', mandatory=False)
    character_classes = ListField('List of CharacterClass ids that can use this move', mandatory=False)
    category = EnumField('Category of skill', SkillCategory, mandatory=False)


class Character(BaseRPGObject):
    """ Creature or person """
    base_stats = DictField('Base statistics')

    character_classes = ListField('List of CharacterClasses id', mandatory=False)
    skills = ListField('List of Skills id', mandatory=False)
    next_forms = ListField('List of the next forms of the character', mandatory=False)
    locations = ListField('List of locations of the character', mandatory=False)


class CollectableItem(BaseRPGObject):
    """ Object that you can find in the game """
    to_use = BoolField('The object can be used at anytime', mandatory=False)
    to_carry = BoolField('The object must be carried to be used (like in battle)', mandatory=False)
    category = StringField('Category of the item', mandatory=False)
    locations = ListField('List of locations of the item', mandatory=False)


class CapRPG(CapCollection):
    """
    Capability for rpg games to list characters, objects, etc.
    """
    def iter_resources(self, objs, split_path):
        """
        Iter reources.

        return :func:`iter_characters` for 'character'
        """
        if Character in objs:
            self._restrict_level(split_path)
            return self.iter_characters()


    def iter_characters(self):
        """
        Iter characters.

        :rtype: iter[:class: `Character`]
        """
        raise NotImplementedError()

    def get_character(self, character_id):
        """
        Get a character with its ID.

        :param character_id: ID of the character
        :type character_id: :class:`str`
        :rtype: :class: `Character`
        :raises: :class: `CharcterNotFound`
        """
        # TODO: find from id and version?
        return find_object(self.iter_characters(), id=character_id, error=CharacterNotFound)

    def iter_skills(self, skill_type=None):
        """
        Iter all available skills.

        :param skill_type: Type of skill
        :type skill_type: :class:`int`
        :rtype: iter[:class: `Skill`]
        """
        raise NotImplementedError()

    def get_skill(self, skill_id):
        """
        Get a skill from with ID.

        :param skill_id: ID of the skill
        :type skill_id: :class:`str`
        :rtype: :class: `Skill`
        :raises: :class: `SkillNotFound`
        """
        return find_object(self.iter_skills(), id=skill_id, error=SkillNotFound)

    def iter_skill_set(self, character_id, skill_type=None):
        """
        Iter skills for a specific character

        :param character_id: ID of the character
        :type character_id: :class:`str`
        :param skill_type: Type of skill
        :type skill_type: :class:`int`
        :rtype: :class: iter[:class: `Skill`]
        """
        raise NotImplementedError()

    def iter_character_classes(self):
        """
        Iter all classes

        :rtype: :class: iter[:class: `CharacterClass`]
        """
        raise NotImplementedError()

    def get_character_class(self, class_id):
        """
        Get details of a class according to id

        :param class_id: ID of the skill
        :type class_id: :class:`str`
        :rtype: :class: `CharacterClass`
        :raises: :class: `CharacterClassNotFound`
        """
        return find_object(self.iter_character_classes(), id=class_id, error=CharacterClassNotFound)

    def iter_collectable_items(self):
        """
        Iter all collectable items

        :rtype: :class: iter[:class: `CollectableItem`]
        """
        raise NotImplementedError()

    def get_collectable_item(self, item_id):
        """
        Get details of a collectable item according to id

        :param item_id: ID of the skill
        :type item_id: :class:`str`
        :rtype: :class: `CollectableItem`
        :raises: :class: `CollectableItemNotFound`
        """
        return find_object(self.iter_collectable_items(), id=item_id, error=CollectableItemNotFound)
