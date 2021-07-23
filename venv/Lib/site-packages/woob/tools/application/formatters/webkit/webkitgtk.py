# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Christophe Benz
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


import os

import gtk
import webkit

from woob.tools.application.javascript import get_javascript
from ..table import HTMLTableFormatter


__all__ = ['WebkitGtkFormatter']


class WebBrowser(gtk.Window):
    def __init__(self):
        super(WebBrowser, self).__init__()
        self.connect('destroy', gtk.main_quit)
        self.set_default_size(800, 600)
        self.web_view = webkit.WebView()
        sw = gtk.ScrolledWindow()
        sw.add(self.web_view)
        self.add(sw)
        self.show_all()


class WebkitGtkFormatter(HTMLTableFormatter):
    def flush(self):
        table_string = self.get_formatted_table()
        js_filepaths = []
        js_filepaths.append(get_javascript('jquery'))
        js_filepaths.append(get_javascript('tablesorter'))
        scripts = ['<script type="text/javascript" src="%s"></script>' % js_filepath for js_filepath in js_filepaths]
        html_string_params = dict(table=table_string)
        if scripts:
            html_string_params['scripts'] = ''.join(scripts)
        html_string = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        %(scripts)s
    </head>
    <body>
        <style type="text/css">
*
{
    font-size: 10pt;
}
        </style>
        <script type="text/javascript">
$(function() {
    var $table = $("table");
    $table
        .prepend(
            $("<thead>")
                .append(
                    $table.find("tr:first")
                )
        )
        .tablesorter();
});
        </script>
        %(table)s
    </body>
</html>
""" % html_string_params
        web_browser = WebBrowser()
        web_browser.web_view.load_html_string(html_string, 'file://%s' % os.path.abspath(os.getcwd()))
        gtk.main()
