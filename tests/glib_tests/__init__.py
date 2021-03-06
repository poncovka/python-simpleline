# Helper functions for the GLib test classes.
#
# Copyright (C) 2017  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from simpleline import App
from simpleline.event_loop.glib_event_loop import GLibEventLoop

import gi
gi.require_version("GLib", "2.0")

from gi.repository import GLib


class GLibUtilityMixin(object):

    def __init__(self):
        self.loop = None
        self.timeout_error = False

    def _quit_loop(self, loop):
        """Kill GLib loop."""
        loop.quit()
        self.timeout_error = True
        return True

    def create_glib_loop(self):
        # clear flags
        self.timeout_error = False
        self.loop = GLibEventLoop()

        loop = self.loop.active_main_loop
        context = loop.get_context()

        # This is prevention from running loop indefinitely
        source = GLib.timeout_source_new_seconds(2)
        source.set_callback(self._quit_loop, loop)
        source.attach(context)

    def schedule_screen_and_run_with_glib(self, screen):
        self.create_glib_loop()

        App.initialize(event_loop=self.loop)
        App.get_scheduler().schedule_screen(screen)
        App.run()

    def teardown_glib(self):
        if self.timeout_error:
            raise AssertionError("Loop was killed by timeout!")