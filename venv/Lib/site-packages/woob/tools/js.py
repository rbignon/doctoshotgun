# -*- coding: utf-8 -*-

# Copyright(C) 2015      Romain Bignon
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


__all__ = ['Javascript']


from woob.tools.log import getLogger


class Javascript(object):
    HEADER = """
    function btoa(str) {
        var buffer;

        if (str instanceof Buffer) {
            buffer = str;
        } else {
            buffer = new Buffer(str.toString(), 'binary');
        }

        return buffer.toString('base64');
    }

    function atob(str) {
        return new Buffer(str, 'base64').toString('binary');
    }

    document = {
        createAttribute: null,
        styleSheets: null,
        characterSet: "UTF-8",
        documentElement: {}
    };

    history = {};

    screen = {
        width: 1280,
        height: 800
    };

    var XMLHttpRequest = function() {};
    XMLHttpRequest.prototype.onreadystatechange = function(){};
    XMLHttpRequest.prototype.open = function(){};
    XMLHttpRequest.prototype.setRequestHeader = function(){};
    XMLHttpRequest.prototype.send = function(){};

    /* JS code checks that some PhantomJS globals aren't defined on the
    * global window object; put an empty window object, so that all these
    * tests fail.
    * It then tests the user agent against some known scrappers; just put
    * the default Tor user agent in there.
    */
    window = {
        document: document,
        history: history,
        screen: screen,
        XMLHttpRequest: XMLHttpRequest,

        innerWidth: 1280,
        innerHeight: 800,

        close: function(){}
    };

    navigator = {
        userAgent: "Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0",
        appName: "Netscape"
    };
    """

    def __init__(self, script, logger=None, domain=""):
        try:
            import execjs
        except ImportError:
            raise ImportError('Please install PyExecJS')

        self.runner = execjs.get()
        self.logger = getLogger('js', logger)

        window_emulator = self.HEADER

        if domain:
            window_emulator += "document.domain = '" + domain + "';"
            window_emulator += """
            if (typeof(location) === "undefined") {
                var location = window.location = {
                    host: document.domain
                };
            }
            """

        self.ctx = self.runner.compile(window_emulator + script)

    def call(self, *args, **kwargs):
        retval = self.ctx.call(*args, **kwargs)

        self.logger.debug('Calling %s%s = %s', args[0], args[1:], retval)

        return retval
