#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright(C) 2017  Vincent A
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
#
# This file is distributed under the WTFPLv2 license.

from __future__ import division

import sys
import os

import PIL.Image as Image
import PIL.ImageColor as PILColor

from woob.tools.compat import range

"""
XTerm can decode sequences and display 256 colors:
- 16 system colors, supported by many terms [0-15]
- 216 colors (not the web-safe palette) [16-231]
- 24 grey colors (excluding black and white) [231-255]

Other terminals do support these 256 colors escape codes, e.g. roxterm, xfce-terminal.
"""

__all__ = ('make256xterm', 'imageRGB_to_256', 'image2xterm', 'image256_to_ansi')


def make256xterm():
    """Return a [r, g, b, r, g, b, ...] table with the colors of the 256 xterm colors.

    The table is indexed: [0:3] corresponds to color 0.
    """
    color256 = []
    # standard 16 colors
    color256 += list(sum((PILColor.getrgb(c) for c in
        '''black maroon green olive navy purple teal silver
        gray red lime yellow blue fuchsia aqua white'''.split()), ()))

    steps = (0, 95, 135, 175, 215, 255)
    for r in steps:
        for g in steps:
            for b in steps:
                color256 += [r, g, b]

    # grays
    for v in range(8, 248, 10):
        color256 += [v, v, v]

    assert len(color256) == 256 * 3

    return color256


TABLE_XTERM_256 = make256xterm()


def imageRGB_to_256(im):
    """Returns `im` converted to the XTerm 256 colors palette.

    The image should be resized *before* applying this function.
    """
    paletter = Image.new('P', (1, 1))
    paletter.putpalette(TABLE_XTERM_256)
    return im.quantize(palette=paletter)


def image256_to_ansi(im, halfblocks):
    """Print PIL image `im` to `fd` using XTerm escape codes.

    1 pixel corresponds to exactly 1 character on the terminal. 1 row of pixels is terminated by a newline.
    `im` has to be a 256 colors image (ideally in the XTerm palette if you want it to make sense).
    `im` should be resized appropriately to fit terminal size and character aspect (characters are never square).
    """
    buf = []
    pix = im.load()
    w, h = im.size

    if halfblocks:
        yrange = range(0, h, 2)
    else:
        yrange = range(h)

    for y in yrange:
        for x in range(w):
            if halfblocks:
                if y + 1 >= h:
                    buf.append(u'\x1b[38;5;%dm\u2580' % pix[x, y])
                else:
                    buf.append(u'\x1b[38;5;%dm\x1b[48;5;%dm\u2580' % (pix[x, y], pix[x, y + 1]))
            else:
                buf.append(u'\x1b[48;5;%dm ' % pix[x, y])
        buf.append(u'\x1b[0m%s' % os.linesep)
    return ''.join(buf)


def image2xterm(imagepath, newsize=(80, 24), halfblocks=True):
    image = Image.open(imagepath)
    image.load()

    stretch = 2
    curratio = image.size[1] / (image.size[0] * stretch)
    targetsize = newsize[0], int(newsize[0] * curratio)
    if targetsize[1] > newsize[1]:
        targetsize = int(newsize[1] / curratio), newsize[1]
    if halfblocks:
        targetsize = targetsize[0], targetsize[1] * 2

    image = image.convert('RGB')
    image = image.resize(targetsize, Image.ANTIALIAS)
    image2 = imageRGB_to_256(image)
    return image256_to_ansi(image2, halfblocks=halfblocks)


def _getoutsize(infoname, default):
    """Get suitable dimension for tty or default"""
    if sys.stdout.isatty():
        import curses
        curses.setupterm()
        return curses.tigetnum(infoname)
    else:
        return default


def get_term_size():
    return (_getoutsize('cols', 80), _getoutsize('lines', 24))


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Print an image on terminal with 256 colors palette')
    parser.add_argument('-r', '--rows', dest='rows', metavar='SIZE', type=int)
    parser.add_argument('-c', '--columns', dest='cols', metavar='SIZE', type=int)
    parser.add_argument('--spaces', action='store_true')
    parser.add_argument('file')
    opts = parser.parse_args()

    if opts.rows is None:
        opts.rows = _getoutsize('lines', 24)
    if opts.cols is None:
        opts.cols = _getoutsize('cols', 80)

    data = image2xterm(opts.file, (opts.cols, opts.rows), halfblocks=not opts.spaces)
    sys.stdout.write(data)


if __name__ == '__main__':
    main()
