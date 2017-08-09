# Default event loop for Simpleline application.
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
# Author(s): Jiri Konecny <jkonecny@redhat.com>
#

from threading import Lock

from simpleline.event_loop import AbstractEventLoop, ExitMainLoop
from simpleline.event_loop.signals import ExceptionSignal
from simpleline.event_loop.event_queue import EventQueue


class MainLoop(AbstractEventLoop):
    """Default main event loop for the Simpleline.

    This event loop can be replaced by your event loop by implementing `simpleline.event_loop.AbstractEventLoop` class.
    """

    def __init__(self):
        super().__init__()
        self._handlers = {}
        self._active_queue = EventQueue()
        self._event_queues = [self._active_queue]
        self._processed_signals = TicketMachine()
        self._lock = Lock()

    def register_signal_handler(self, signal, callback, data=None):
        """Register a callback which will be called when message "event"
        is encountered during process_events.

        The callback has to accept two arguments:
        - the received message in the form of (type, [arguments])
        - the data registered with the handler

        :param signal: signal we want to react on
        :type signal: class of the signal class

        :param callback: the callback function
        :type callback: func(signal, data)

        :param data: optional data to pass to callback
        :type data: anything
        """
        if signal not in self._handlers:
            self._handlers[signal] = []
        self._handlers[signal].append(EventHandler(callback, data))

    def register_signal_source(self, signal_source):
        """Register source of signal for actual event queue.

        :param signal_source: Source for future signals.
        :type signal_source: `simpleline.render.ui_screen.UIScreen`
        """
        self._active_queue.add_source(signal_source)

    def run(self):
        """This methods starts the application.

        Do not use self.mainloop() directly as run() handles all the required exceptions
        needed to keep nested mainloop working.
        """
        self._mainloop()
        if self._quit_callback:
            self._quit_callback()

    def execute_new_loop(self, signal):
        """Starts the new event loop and pass `signal` in it.

        This is required for processing a modal screens.

        :param signal: signal passed to the new event loop
        :type signal: `AbstractSignal` based class
        """
        self._active_queue = EventQueue()

        # TODO: Remove when python3-astroid 1.5.3 will be in Fedora
        # pylint: disable=not-context-manager
        with self._lock:
            self._event_queues.append(self._active_queue)

        self.enqueue_signal(signal)
        self._mainloop()

    def close_loop(self):
        """Close active event loop.

        Close an event loop created by the `execute_new_loop()` method.
        """
        self.process_signals()

        # TODO: Remove when python3-astroid 1.5.3 will be in Fedora
        # pylint: disable=not-context-manager
        with self._lock:
            self._event_queues.pop()
            try:
                self._active_queue = self._event_queues[-1]
            except IndexError:
                raise ExitMainLoop()

        raise ExitMainLoop()

    def enqueue_signal(self, signal):
        """Enqueue new event for processing.

        Enqueue signal to the most inner queue (nearest to the active queue) where the `signal.source` belongs.
        If it belongs nowhere enqueue it to the active one.

        This method is thread safe.

        :param signal: event which you want to add to the event queue for processing
        :type signal: instance based on AbstractEvent class
        """
        # TODO: Remove when python3-astroid 1.5.3 will be in Fedora
        # pylint: disable=not-context-manager
        with self._lock:
            for queue in reversed(self._event_queues):
                if queue.enqueue_if_source_belongs(signal, signal.source):
                    return

        self._active_queue.enqueue(signal)

    def _mainloop(self):
        """Single mainloop. Do not use directly, start the application using run()."""
        # run infinite loop
        # this will always wait on input processing or similar so it is not busy waiting
        while True:
            try:
                self.process_signals()
            # end just this loop
            except ExitMainLoop:
                break

    def process_signals(self, return_after=None):
        """This method processes incoming async messages.

        Process signals enqueued by the `self.enqueue_signal()` method. Call handlers registered to the signals by
        the `self.register_signal_handler()` method.

        When `return_after` is specified then wait to the point when this signal is processed. This could be after
        some more signals was processed because of recursion in calls.
        Without `return_after` parameter this method will return after all queued signals will be processed.

        The method is NOT thread safe!

        :param return_after: Wait on this signal to be processed.
        :type return_after: Class of the signal.
        """
        # get unique ID when waiting for the signal
        unique_id = self._register_wait_on_signal(return_after)

        while not self._active_queue.empty() or return_after is not None:
            signal = self._active_queue.get()
            # all who is waiting on this signal can stop waiting
            self._mark_signal_processed(signal)

            # do the signal processing (call handlers)
            self._process_signal(signal)

            # was our signal processed if yes, return this method
            if self._check_if_signal_processed(return_after, unique_id):
                return

    def _process_signal(self, signal):
        if type(signal) in self._handlers:
            for handler_data in self._handlers[type(signal)]:
                try:
                    handler_data.callback(signal, handler_data.data)
                except ExitMainLoop:
                    raise
        elif type(signal) is ExceptionSignal:
            self._raise_exception(signal)

    def _raise_exception(self, signal):
        raise signal.exception_info[0] from signal.exception_info[1]

    def _register_wait_on_signal(self, wait_on_signal):
        if wait_on_signal is None:
            return -1

        return self._processed_signals.take_ticket(wait_on_signal.__name__)

    def _mark_signal_processed(self, signal):
        self._processed_signals.mark_line_to_go(signal.__class__.__name__)

    def _check_if_signal_processed(self, wait_on_signal, unique_id):
        if wait_on_signal is None:
            # return false because we are not waiting on specific signal
            # continue with signal processing
            return False

        return self._processed_signals.check_ticket(wait_on_signal.__name__, unique_id)


class EventHandler(object):
    """Data class to save event handlers."""

    def __init__(self, callback, data):
        self.callback = callback
        self.data = data


class TicketMachine(object):
    """Hold signals processed by the event loop if someone wait on them.

    This is useful when recursive process events will skip required signal.
    """

    def __init__(self):
        self._lines = {}
        self._counter = 0

    def take_ticket(self, line_id):
        """Take ticket (id) and go line (processing events).

        Use `check_ticket` if you are ready to go.

        :param line_id: Line where you are waiting.
        :type line_id: Anything.
        """
        obj_id = self._counter
        if line_id not in self._lines:
            self._lines[line_id] = {obj_id: False}
        else:
            self._lines[line_id][obj_id] = False

        self._counter += 1
        return obj_id

    def check_ticket(self, line, unique_id):
        """Check if you are ready to go.

        If True the unique_id is not valid anymore.

        :param unique_id: Your id used to identify you in the line.
        :type unique_id: int

        :param line: Line where you are waiting.
        :type line: Anything.
        """
        if self._lines[line][unique_id]:
            return self._lines[line].pop(unique_id)

    def mark_line_to_go(self, line):
        """All in the `line` are ready to go.

        Mark all tickets in the line as True.

        :param line: Line which should processed.
        :type line: Anything.
        """
        if line in self._lines:
            our_line = self._lines[line]
            for key in our_line:
                our_line[key] = True
