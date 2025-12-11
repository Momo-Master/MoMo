import logging
import os
import sys

from pwnagotchi import plugins
from pwnagotchi.ui import fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

try:
    sys.path.append(os.path.dirname(__file__))
    from Touch_UI import Touch_Button
except Exception as e:
    logging.warning(repr(e))

class enable_assoc(plugins.Plugin):
    __author__ = "evilsocket@gmail.com"
    __version__ = "1.0.0"
    __license__ = "GPL3"
    __description__ = "Enable and disable ASSOC  on the fly. Enabled when plugin loads, disabled when plugin unloads."

    def __init__(self):
        self._agent = None
        self._count = 0
        self.hasTouch = False
        self._touchscreen = None

    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        pass

    # called when the plugin is loaded
    def on_loaded(self):
        self._count = 0

    # called before the plugin is unloaded
    def on_unload(self, ui):
        try:
            if not self.hasTouch and self._agent:
                self._agent._config["personality"]["associate"] = False
            ui.remove_element("assoc_count")
            logging.info("[Enable_Assoc] unloading")
        except Exception as e:
            logging.warning(repr(e))

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._agent = agent

        self.hasTouch = self._touchscreen and self._touchscreen.running

        if self.hasTouch and self._ui:
            self._ui._state._state["assoc_count"].state = self._agent._config["personality"]["associate"]
        else:
            agent._config["personality"]["associate"] = True

        logging.info("[Enable_Assoc] ready: enabled association")

    def on_touch_ready(self, touchscreen):
        logging.info(f"[ASSOC] Touchscreen {touchscreen!r}")
        self._touchscreen = touchscreen
        self.hasTouch = self._touchscreen and self._touchscreen.running

    def on_touch_release(self, ts, ui, ui_element, touch_data):
        logging.debug(f"[ASSOC] Touch release: {touch_data!r}")
        try:
            if ui_element == "assoc_count":
                logging.debug("Toggling assoc {}".format(repr(self._agent._config["personality"]["associate"])))
                self._agent._config["personality"]["associate"] = self._ui._state._state["assoc_count"].state
                logging.info("Toggled assoc to {}".format(repr(self._ui._state._state["assoc_count"].state)))

        except Exception as err:
            logging.info(f"{err!r}")

    def on_touch_press(self, ts, ui, ui_element, touch_data):
        logging.debug(f"[ASSOC] Touch press: {touch_data!r}")

    def on_association(self, agent, access_point):
        self._count += 1

    # called to setup the ui elements
    def on_ui_setup(self, ui):
        self._ui = ui
        self.hasTouch = self._touchscreen and self._touchscreen.running
        # add custom UI elements
        if "position" in self.options:
            pos = self.options["position"].split(",")
            pos = [int(x.strip()) for x in pos]
        else:
            pos = (209,111,30,59)

        try:
            ui.add_element("assoc_count", Touch_Button(position=pos,
                                                       color="#ccccff", alt_color="White",
                                                       outline="DarkGray",
                                                       state=False,
                                                       text="assoc", value=0, text_color="Black",
                                                       alt_text=None, alt_text_color="Green",
                                                       shadow="Black", highlight="White",
                                                       event_handler="enable_assoc",
                                                       ),
                           )
        except Exception:
            ui.add_element("assoc_count", LabeledValue(color=BLACK, label="A", value="", position=pos,
                                                       label_font=fonts.BoldSmall, text_font=fonts.Small))

        # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        ui.set("assoc_count")
