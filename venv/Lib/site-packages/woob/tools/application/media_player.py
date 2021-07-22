# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Christophe Benz, Romain Bignon, John Obbele
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

from contextlib import closing
from subprocess import PIPE, Popen
import subprocess
import shlex
from shutil import which

import requests

from woob.tools.log import getLogger

__all__ = ['InvalidMediaPlayer', 'MediaPlayer', 'MediaPlayerNotFound']


PLAYERS = (
    ('mpv',      '-'),
    ('mplayer2', '-'),
    ('mplayer',  '-'),
    ('vlc',      '-'),
    ('parole',   'fd://0'),
    ('totem',    'fd://0'),
    ('xine',     'stdin:/'),
)


class MediaPlayerNotFound(Exception):
    def __init__(self):
        super(MediaPlayerNotFound, self).__init__(u'No media player found on this system. Please install one of them: %s.' %
                           ', '.join(player[0] for player in PLAYERS))


class InvalidMediaPlayer(Exception):
    def __init__(self, player_name):
        super(InvalidMediaPlayer, self).__init__(u'Invalid media player: %s. Valid media players: %s.' % (
            player_name, ', '.join(player[0] for player in PLAYERS)))


class MediaPlayer(object):
    """
    Black magic invoking a media player to this world.

    Presently, due to strong disturbances in the holidays of the ether
    world, the media player used is chosen from a static list of
    programs. See PLAYERS for more information.
    """

    def __init__(self, logger=None):
        self.logger = getLogger('mediaplayer', logger)

    def guess_player_name(self):
        for player_name in [player[0] for player in PLAYERS]:
            if which(player_name) is not None:
                return player_name
        return None

    def play(self, media, player_name=None, player_args=None):
        """
        Play a media object, using programs from the PLAYERS list.

        This function dispatch calls to either _play_default or
        _play_rtmp for special rtmp streams using SWF verification.
        """
        player_names = [player[0] for player in PLAYERS]
        if not player_name:
            self.logger.debug(u'No media player given. Using the first available from: %s.' %
                              ', '.join(player_names))
            player_name = self.guess_player_name()
            if player_name is None:
                raise MediaPlayerNotFound()
        if media.url.startswith('rtmp'):
            self._play_rtmp(media, player_name, args=player_args)
        else:
            self._play_default(media, player_name, args=player_args)

    def _play_default(self, media, player_name, args=None):
        """
        Play media.url with the media player.
        """
        # if flag play_proxy...
        if hasattr(media, '_play_proxy') and media._play_proxy is True:
            # use requests to handle redirect and cookies
            self._play_proxy(media, player_name, args)
            return None

        args = shlex.split(player_name)
        args.append(media.url)

        print('Invoking "%s".' % (' '.join(args)))
        subprocess.call(args)

    def _play_proxy(self, media, player_name, args):
        """
        Load data with python requests and pipe data to a media player.

        We need this function for url that use redirection and cookies.
        This function is used if the non-standard,
        non-API compliant '_play_proxy' attribute of the 'media' object is defined and is True.
        """
        if args is None:
            for (binary, stdin_args) in PLAYERS:
                if binary == player_name:
                    args = stdin_args

        assert args is not None

        print(':: Play_proxy streaming from %s' % media.url)
        print(':: to %s %s' % (player_name, args))
        print(player_name + ' ' + args)
        proc = Popen(player_name + ' ' + args, stdin=PIPE, shell=True)

        # Handle cookies (and redirection 302...)
        session = requests.sessions.Session()

        with closing(proc.stdin):
            with closing(session.get(media.url, stream=True)) as response:
                for buffer in response.iter_content(8192):
                    try:
                        proc.stdin.write(buffer)
                    except:
                        print("play_proxy broken pipe. Can't write anymore.")
                        break

    def _play_rtmp(self, media, player_name, args):
        """
        Download data with rtmpdump and pipe them to a media player.

        You need a working version of rtmpdump installed and the SWF
        object url in order to comply with SWF verification requests
        from the server. The last one is retrieved from the non-standard
        non-API compliant 'swf_player' attribute of the 'media' object.
        """
        if which('rtmpdump') is None:
            self.logger.warning('"rtmpdump" binary not found')
            return self._play_default(media, player_name)
        media_url = media.url
        try:
            player_url = media.swf_player
            if media.swf_player:
                rtmp = 'rtmpdump -r %s --swfVfy %s' % (media_url, player_url)
            else:
                rtmp = 'rtmpdump -r %s' % media_url
        except AttributeError:
            self.logger.warning('Your media object does not have a "swf_player" attribute. SWF verification will be '
                                'disabled and may prevent correct media playback.')
            return self._play_default(media, player_name)

        rtmp += ' --quiet'

        if args is None:
            for (binary, stdin_args) in PLAYERS:
                if binary == player_name:
                    args = stdin_args

        assert args is not None

        player_name = shlex.split(player_name)
        args = shlex.split(args)

        print(':: Streaming from %s' % media_url)
        print(':: to %s %s' % (player_name, args))
        print(':: %s' % rtmp)
        p1 = Popen(shlex.split(rtmp), stdout=PIPE)
        Popen(player_name + args, stdin=p1.stdout, stderr=PIPE)
