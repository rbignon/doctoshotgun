# -*- coding: utf-8 -*-

# Copyright(C) 2011 Romain Bignon
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

from woob.tools.compat import unicode

from .base import Capability, BaseObject, Field, StringField,\
                  IntField, UserError, Enum
from .date import DateField, DeltaField


__all__ = ['IssueError', 'Project', 'User', 'Version', 'Status', 'Attachment',
           'Change', 'Update', 'Issue', 'Query', 'CapBugTracker']


class IssueError(UserError):
    """
    Raised when there is an error with an issue.
    """


class Project(BaseObject):
    """
    Represents a project.
    """
    name =          StringField('Name of the project')
    members =       Field('Members of projects', list)
    versions =      Field('List of versions available for this project', list)
    trackers =      Field('All trackers', list)
    categories =    Field('All categories', list)
    statuses =      Field('Available statuses for issues', list)
    priorities =    Field('Available priorities for issues', list)
    tags =          Field('All tags', tuple, list)
    fields =        Field('Custom fields names', list)

    def __init__(self, id, name, url=None):
        super(Project, self).__init__(id, url)
        self.name = unicode(name)

    def __repr__(self):
        return '<Project %r>' % self.name

    def find_user(self, id, name):
        """
        Find a user from its ID.

        If not found, create a :class:`User` with the specified name.

        :param id: ID of user
        :type id: str
        :param name: Name of user
        :type name: str
        :rtype: :class:`User`
        """
        for user in self.members:
            if user.id == id:
                return user
        if name is None:
            return None
        return User(id, name)

    def find_version(self, id, name):
        """
        Find a version from an ID.

        If not found, create a :class:`Version` with the specified name.

        :param id: ID of version
        :type id: str
        :param name: Name of version
        :type name: str
        :rtype: :class:`Version`
        """
        for version in self.versions:
            if version.id == id:
                return version
        if name is None:
            return None
        return Version(id, name)

    def find_status(self, name):
        """
        Find a status from a name.

        :param name: Name of status
        :type name: str
        :rtype: :class:`Status`
        """
        for status in self.statuses:
            if status.name == name:
                return status
        if name is None:
            return None
        return None


class User(BaseObject):
    """
    User.
    """
    name =      StringField('Name of user')

    def __init__(self, id, name, url=None):
        super(User, self).__init__(id, url)
        self.name = unicode(name)

    def __repr__(self):
        return '<User %r>' % self.name


class Version(BaseObject):
    """
    Version of a project.
    """
    name =      StringField('Name of version')

    def __init__(self, id, name, url=None):
        super(Version, self).__init__(id, url)
        self.name = unicode(name)

    def __repr__(self):
        return '<Version %r>' % self.name


class StatusType(Enum):
    NEW      = 0
    PROGRESS = 1
    RESOLVED = 2
    REJECTED = 3


class Status(BaseObject):
    """
    Status of an issue.

    **VALUE_** constants are the primary status
    types.
    """
    VALUE_NEW = StatusType.NEW
    VALUE_PROGRESS = StatusType.PROGRESS
    VALUE_RESOLVED = StatusType.RESOLVED
    VALUE_REJECTED = StatusType.REJECTED

    name =      StringField('Name of status')
    value =     IntField('Value of status (constants VALUE_*)')

    def __init__(self, id, name, value, url=None):
        super(Status, self).__init__(id, url)
        self.name = unicode(name)
        self.value = value

    def __repr__(self):
        return '<Status %r>' % self.name


class Attachment(BaseObject):
    """
    Attachment of an issue.
    """
    filename =      StringField('Filename')

    def __repr__(self):
        return '<Attachment %r>' % self.filename


class Change(BaseObject):
    """
    A change of an update.
    """
    field =         StringField('What field has been changed')
    last =          StringField('Last value of field')
    new =           StringField('New value of field')

    def __repr__(self):
        return '<%s %r: %r (old: %r)>' % (type(self).__name__, self.field, self.new, self.last)


class Update(BaseObject):
    """
    Represents an update of an issue.
    """
    author =        Field('Author of update', User)
    date =          DateField('Date of update')
    hours =         DeltaField('Time activity')
    message =       StringField('Log message')
    attachments =   Field('Files attached to update', list, tuple)
    changes =       Field('List of changes', list, tuple)

    def __repr__(self):
        return '<Update %r>' % self.id


class Issue(BaseObject):
    """
    Represents an issue.
    """
    project =       Field('Project of this issue', Project)
    title =         StringField('Title of issue')
    body =          StringField('Text of issue')
    creation =      DateField('Date when this issue has been created')
    updated =       DateField('Date when this issue has been updated for the last time')
    start =         DateField('Date when this issue starts')
    due =           DateField('Date when this issue is due for')
    attachments =   Field('List of attached files', list, tuple)
    history =       Field('History of updates', list, tuple)
    author =        Field('Author of this issue', User)
    assignee =      Field('User assigned to this issue', User)
    tracker =       StringField('Name of the tracker')
    category =      StringField('Name of the category')
    version =       Field('Target version of this issue', Version)
    status =        Field('Status of this issue', Status)
    fields =        Field('Custom fields (key,value)', dict)
    priority =      StringField('Priority of the issue') #XXX
    tags =          Field('Categories/Tags of the issue', tuple, list)
    related_issues = Field('Related issues', list)


class Query(BaseObject):
    """
    Query to find an issue.
    """
    project =       Field('Filter on projects', str, unicode, Project)
    title =         StringField('Filter on titles')
    author =        Field('Filter on authors', str, unicode, User)
    assignee =      Field('Filter on assignees', str, unicode, User)
    version =       Field('Filter on versions', str, unicode, Version)
    category =      StringField('Filter on categories')
    status =        Field('Filter on statuses', str, unicode, Status)
    tags =          Field('Filter on tags', tuple, list)
    fields =        Field('Filter on custom fields', dict)

    def __init__(self, id='', url=None):
        super(Query, self).__init__(id, url)


class CapBugTracker(Capability):
    """
    Bug trackers websites.
    """

    (SORT_RELEVANCE,
     SORT_RATING,
     SORT_PRIORITY,
     SORT_DATE) = range(4)

    def iter_issues(self, query, sortby=SORT_RELEVANCE, ascending=False):
        """
        Iter issues with optionnal patterns.

        :param query: query
        :type query: :class:`Query`
        :rtype: iter[:class:`Issue`]
        """
        raise NotImplementedError()

    def get_issue(self, id):
        """
        Get an issue from its ID.

        :param id: ID of issue
        :rtype: :class:`Issue`
        """
        raise NotImplementedError()

    def create_issue(self, project):
        """
        Create an empty issue on the given project.

        :param project: project
        :type project: :class:`Project`
        :returns: the created issue
        :rtype: :class:`Issue`
        """
        raise NotImplementedError()

    def post_issue(self, issue):
        """
        Post an issue to create or update it.

        :param issue: issue to create or update
        :type issue: :class:`Issue`
        """
        raise NotImplementedError()

    def update_issue(self, issue, update):
        """
        Add an update to an issue.

        :param issue: issue or id of issue
        :type issue: :class:`Issue`
        :param update: an Update object
        :type update: :class:`Update`
        """
        raise NotImplementedError()

    def remove_issue(self, issue):
        """
        Remove an issue.

        :param issue: issue
        :type issue: :class:`Issue`
        """
        raise NotImplementedError()

    def iter_projects(self):
        """
        Iter projects.

        :rtype: iter[:class:`Project`]
        """
        raise NotImplementedError()

    def get_project(self, id):
        """
        Get a project from its ID.

        :rtype: :class:`Project`
        """
        raise NotImplementedError()
