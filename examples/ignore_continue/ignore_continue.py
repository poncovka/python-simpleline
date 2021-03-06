#!/bin/python3

from simpleline import App
from simpleline.render.prompt import Prompt
from simpleline.render.screen import UIScreen, InputState
from simpleline.render.widgets import TextWidget, CenterWidget


class MyApp(App):
    def application_quit_cb(self):
        print("Application is closing. Bye!")


class InfiniteScreen(UIScreen):

    def __init__(self):
        super().__init__("You need to use 'q' to quit")
        self.continue_count = 0

    def refresh(self, args=None):
        """Print text to user with number of continue clicked"""
        super().refresh(args)
        text = TextWidget("You pressed {} times on continue".format(self.continue_count))
        self.window.add(CenterWidget(text))

    def input(self, args, key):
        """Catch 'c' keys for continue and increase counter"""
        if key == Prompt.CONTINUE:
            self.continue_count += 1
            self.redraw()
            return InputState.PROCESSED

        return key


if __name__ == "__main__":
    App.initialize()
    screen = InfiniteScreen()
    App.get_scheduler().schedule_screen(screen)
    App.run()
