import html
import json
import logging
import os
import sys
import time

from PIL import ImageFont
from pwnagotchi import plugins
from pwnagotchi.ui import fonts
from pwnagotchi.ui.components import *

try:
    sys.path.append(os.path.dirname(__file__))
except Exception:
    pass
    #logging.warn(repr(e))

from textwrap import TextWrapper

from flask import abort, render_template_string


class Tweak_View(plugins.Plugin):
    __author__ = "Sniffleupagus"
    __version__ = "1.0.0"
    __license__ = "GPL3"
    __description__ = "Edit the UI layout. Ugly interface, no guardrails. Be careful!!!"

    # load from save file, parse JSON. dict maps from view_state_state key to new val
    # store originals when tweaks are applie
    #
    # have multiple base tweak files (for different display types, whatever)
    # and choose from them in config
    # - tweaks can be "system-wide" or associated with a specific base
    # - when updating the display, create a dict adding base tweaks, system-wide mods, base-specific mods
    #   so specific overrides global
    #

    def __init__(self):
        self._agent = None
        self._start = time.time()
        self._logger = logging.getLogger(__name__)
        self._tweaks = {}
        self._untweak = {}
        self._already_updated = []

        self.myFonts = {"Small": fonts.Small,
                   "BoldSmall": fonts.BoldSmall,
                   "Medium": fonts.Medium,
                   "Bold": fonts.Bold,
                   "BoldBig": fonts.BoldBig,
                   "Huge": fonts.Huge,
        }


    def show_tweaks(self, request):
        res = ""
        res += f'<form method=POST action="{request.path}/delete_mods"><input id="csrf_token" name="csrf_token" type="hidden" value="{{{{ csrf_token() }}}}">\n'
        res += "<ul>\n"

        for tw, val in self._tweaks.items():
            res += f'<li><input type=checkbox name=delete_me id="{tw}" value="{tw}"> {tw}: {val!r}\n'
            if tw in self._untweak:
                res += f"(orig: {self._untweak[tw]!r})\n"
        res += "</ul>"
        res += '<input type=submit value="Delete Selected Mods"></form>'

        return res


    def dump_item(self, name, item, prefix=""):
        self._logger.debug(f"{prefix}[[[{name}:{type(item)}]]]")
        res = ""
        if type(item) is int:
            res += f'{name}: <input type=text name="{prefix}{name}" value="{item}">'
        elif type(item) is str:
            if item.startswith("{"):
                #print("********************\n%s JSON %s" % (prefix, item))
                try:
                    j = json.loads(item)
                    res += f"{prefix}JSON\n", json.dumps(j, sort_keys=True,indent=4)
                except Exception:
                    res += f"{prefix}{name} = '{item}'\n"
                else:
                    res += f'{name}: <input type=text name="{prefix}{name}" value="{item}">'
                    res += f"{prefix}{name} = '{item}'\n"
        elif type(item) is float:
            res += f"{prefix}{name} = {item}\n"
            res += f'{name}: <input type=text name="{prefix}{name}" value="{item}">'
        elif type(item) is bool:
            res += f"{prefix}{name} is {item}\n"
        elif type(item) is list:
            #if (prefix is ""):
            if len(item) > 1: res += "\n"
            res += f"{prefix}[{name}]\n"
            i = 0
            for key in item:
                i=i+1
                self._logger.debug("%s<%i> %s\n" % (prefix, i, key))
                res += self.dump_item("{%i}" % (i), key, "  {} {}".format(" " * len(prefix), name)) + "\n"

            if (prefix == ""):
                res += f"{prefix}[{name} END]\n"

        elif type(item) is dict:
            #res += "Dict: [%s] [%s]<ul>\n" % (prefix, name)
            for key in item:
                self._logger.debug(f"{prefix}>>> {key}:{type(item[key])}")
                res += "<li>" + self.dump_item(f"{key}", item[key], f"{prefix}{name}") + "\n"
                #prefix = " " * len(prefix)
                #name = " " * len(name)
            res += "</ul>"
        elif isinstance(item, Widget):
            res += f"<b>{html.escape(str(type(item).__name__))}:</b> {name}\n<ul>"
            try:
                for key in dir(item):
                    val = getattr(item, key)
                    if key.startswith("__"):
                        pass
                    elif key == "value":
                        res += f'<li>{name}.{html.escape(key)} = "{html.escape(str(val))}"\n'
                    elif key == "draw":
                        pass
                    elif key == "xy": # n-tuple of coordinates, 2 for text & label, 4 for line
                        res += '<li>{}.xy: <input type=text name="{}.{}.xy" value="{}">'.format(name, prefix, name, html.escape(",".join(map(str,val))))
                    elif key in ("label", "label_spacing") or type(val) in (int, str):
                        res += f'<li>{name}.{html.escape(key)}: <input type=text name="{prefix}.{name}.{html.escape(key)}" value="{html.escape(str(val))}"><br>'
                    elif "font" in key:
                        tag = f"{prefix}.{name}.{html.escape(key)}"
                        res += f'<li>{name}.{html.escape(key)}: <select id="{tag}" name="{tag}">\n'

                        for l,f in self.myFonts.items():
                            if val == f:
                                res += f'  <option value="{l}" selected>{l}</option>'
                            else:
                                res += f'  <option value="{l}">{l}</option>'
                        res += "</select>"
                    else:
                        res += '<li>{}["{}"].{} = {}\n'.format(prefix, name, html.escape(key),  html.escape("<" + str(type(val).__name__) + ">"))
                        #res += self.dump_item('%s["%s"].%s' % (prefix, name, html.escape(key)), val)

            except Exception as inst:
                res += f"*{prefix}] Error processing {name}<br>\n"
                res += f"{prefix}, {type(inst)}<br>\n"
                res += f"{prefix} {inst.args}<br>\n"
                res += f"{prefix} {inst}<br>\n"
            res += "</ul>"
        else:
            try:
                res += f"{prefix}Unknown type {name}<br>\n"
                res += f"{prefix} {name} is a {html.escape(str(type(item)))}<br><ul>\n"
                for key in dir(item):
                    val = getattr(item, key)
                    if key.startswith("__"):
                        res += f"<li>{prefix}{name}.{key} = {html.escape(repr(getattr(item, key)))}\n"
                    else:
                        self._logger.debug(f"{prefix}>>> {key}:{html.escape(str(type(getattr(item, key))))}")
                        res += "<li>{}{}.{} = {} {}\n".format(prefix, name, key, html.escape("<"+ str(type(val).__name__) + ">"), html.escape(repr(val)))
                        #res += self.dump_item("%s" % (key), repr(getattr(item, key), "%s%s." % (prefix, name)) + "\n"
                res += "</ul>"
            except Exception as inst:
                res += f"*{prefix}] Error processing {name}\n"
                res += f"{prefix}, {type(inst)}\n"
                res += f"{prefix} {inst.args}\n"
                res += f"{prefix} {inst}\n"


        return res


    def update_from_request(self, request):
        res = "<ul>"
        changed = False
        try:
            view = self._agent.view()
            for k,val in request.form.items():
                if k.startswith("VSS."):
                    key = k.split(".")
                    key = [ x.strip() for x in key]
                    #res += "<li> %s" % "-".join(key)
                    if key[2] in dir(view._state._state[key[1]]):
                        # SECURITY: Use getattr instead of eval to prevent RCE
                        oldval = getattr(view._state._state[key[1]], key[2], None)
                        if "font" in key[2]:
                            if oldval != self.myFonts[val]:
                                oldf = f"unknown {oldval!r}"
                                for n,f in self.myFonts.items():
                                    if f == oldval:   # found existing font
                                        oldf = n
                                        res += f"<li>{key[1]}.{key[2]} == {html.escape(val)}, {html.escape(oldf)}"
                                self._tweaks[k] = val
                                changed = True
                        elif "color" in key[2]:
                            if val != f"{oldval}":
                                res += f"<li>*{key[1]}.{key[2]} : new {html.escape(repr(val))}, old {html.escape(repr(oldval))}"
                                # validate that it is actual color?
                                if self._ui:
                                    self._ui._state._state[key[1]].color = val
                                self._tweaks[k] = val
                                changed = True
                        elif "xyz" in key[2]:
                            old_xy = ",".join(map(str,oldval))
                            new_xy = val.split(",")
                            new_xy = [float(x.strip()) for x in new_xy]
                            for i in range(len(oldval)):
                                if oldval[i] != new_xy[i]:
                                    res += f"<li>-{key[1]}.{key[2]} != {html.escape(repr(new_xy))}, {html.escape(repr(oldval))}"
                                    res += f"<li>-{key[1]}.{key[2]} != {val}, {old_xy}"
                                    break
                        elif type(oldval) in (list, tuple):
                            for i in range(len(oldval)):
                                new_xy = val.split(",")
                                new_xy = [int(float(x.strip())) for x in new_xy]
                                if float(oldval[i]) != new_xy[i]:
                                    res += f"<li>LIST {key[1]}.{key[2]} != {html.escape(repr(val))}, {html.escape(repr(oldval))}"
                                    self._tweaks[k] = val
                                    changed = True
                                    res += f"<li>Tweak {k} -> {self._tweaks[k]}"
                        elif type(oldval) is int:
                            if oldval != int(float(val)):
                                res += f"<li>*{key[1]}.{key[2]} != {html.escape(repr(val))}, {html.escape(repr(oldval))}"
                                self._tweaks[k] = int(float(val))
                                changed = True
                        elif type(oldval) is str:
                            if oldval != str(val):
                                res += f"<li>S{key[1]}.{key[2]} != {html.escape(str(val))}, {html.escape(str(oldval))} ({html.escape(str(type(val)))})"
                                self._tweaks[k] = val
                                changed = True
                        elif str(val) != str(oldval):
                            res += f"<li>^{key[1]}.{key[2]} != {html.escape(str(val))}, {html.escape(str(oldval))} ({html.escape(str(type(val)))})"

                        if changed:
                            if key[1] in self._already_updated:
                                self._already_updated.remove(key[1])

            if changed:
                try:
                    with open(self._conf_file, "w") as f:
                        f.write(json.dumps(self._tweaks, indent=4))
                except Exception as err:
                    res += f"<li><b>Unable to save settings:</b> {err!r}"


        except Exception as err:
            res += f"<li><b>update from request err:</b> {err!r}"
        res += "</ul>"
        return res

    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        try:
            if request.method == "GET":
                if path == "/" or not path:

                    ret = '<html><head><title>Tweak view. Woohoo!</title><meta name="csrf_token" content="{{ csrf_token() }}"></head>'
                    ret += "<body><h1>Tweak View</h1>"
                    ret += f'<img src="/ui?{int(time.time())}">'
                    if path: ret += f"<h2>Path</h2><code>{path!r}</code><p>"
                    #ret += "<h2>Request</h2><code>%s</code><p>" % self.dump_item("Request", request)
                    if self._agent:
                        view = self._agent.view()
                        ret += '<h2>Available View Elements</h2><pre><form method=post><input id="csrf_token" name="csrf_token" type="hidden" value="{{ csrf_token() }}">'
                        ret += "{}".format(self.dump_item("VSS", view._state._state ))
                        ret += '<input type=submit name=submit value="Update View"></form></pre><p>'
                        ret += "</body></html>"
                    return render_template_string(ret)
                abort(404)
            elif request.method == "POST":
                if path == "update":
                    ret = '<html><head><title>Tweak view. Update!</title><meta name="csrf_token" content="{{ csrf_token() }}"></head>'
                    ret += "<body><h1>Tweak View Update</h1>"
                    ret += f'<img src="/ui?{int(time.time())}">'
                    ret += f"<h2>Path</h2><code>{path!r}</code><p>"
                    ret += "<h2>Request</h2><code>{}</code><p>".format(self.dump_item("Request", request.values))
                    ret += f"<h2>Current Mods</h2>{self.show_tweaks(request)}<p>"
                    ret += "</body></html>"
                elif path == "delete_mods":
                    ret = '<html><head><title>Tweak view. Update!</title><meta name="csrf_token" content="{{ csrf_token() }}"></head>'
                    ret += "<body><h1>Tweak View Update</h1>"
                    ret += f'<img src="/ui?{int(time.time())}">'
                    if "delete_me" in request.form:
                        ret += "<h2>Delete Mods</h2><ul>\n"
                        changed = False
                        for d in request.form.getlist("delete_me"):
                            if d in self._untweak:
                                try:
                                    ret += f"<li>Revert {d}: {self._untweak[d]!r}"
                                    vss, element, key = d.split(".")
                                    ui = self._agent.view()
                                    if hasattr(ui._state._state[element], key):
                                        value = self._untweak[d]
                                        setattr(ui._state._state[element], key, value)
                                        ret += f"<li>Reverted {element} {key} to {value!r}\n"
                                        self._logger.info(f"Reverted {element} xy to {getattr(ui._state._state[element], key)!r}")
                                        del(self._untweak[d])
                                except Exception as err:
                                    ret += f"<li>Revert {d} failed: {err!r}"
                            else:
                                ret += f"<li>{d} not in backups\n"

                            if d in self._tweaks:
                                try:
                                    del(self._tweaks[d])
                                    ret += f"<li>Removed mod {d}\n"
                                    changed = True
                                except Exception as err:
                                    ret += f"<li>Error deleting {d}: {err!r}"
                        if changed:
                            try:
                                with open(self._conf_file, "w") as f:
                                    f.write(json.dumps(self._tweaks, indent=4))
                                    ret += "<li>Saved mods\n"
                            except Exception as err:
                                ret += f"<li><b>Unable to save settings:</b> {err!r}"

                        ret += "</ul>\n"
                    ret += f"<h2>Path</h2><code>{path!r}</code><p>"
                    ret += "<h2>Request</h2><code>{}</code><p>".format(self.dump_item("Request", request.values))
                    ret += f"<h2>Current Mods</h2>{self.show_tweaks(request)}<p>"
                    ret += "</body></html>"
                else:
                    ret = '<html><head><title>Tweak view. Result!</title><meta name="csrf_token" content="{{ csrf_token() }}"></head>'
                    ret += "<body><h1>Tweak View POST</h1>"
                    ret += f'<img src="/ui?{int(time.time())}">'
                    ret += f"<h2>Path</h2><code>{path!r}</code><p>"
                    #ret += "<h2>Request</h2><code>%s</code><p>" % self.dump_item("request", request)
                    ret += f"<h2>Form</h2><code>{self.update_from_request(request)}</code><p>"
                    ret += f"<h2>Current Mods</h2>{self.show_tweaks(request)}<p>"
                    ret += "</body></html>"
                return render_template_string(ret)
            else:
                ret = '<html><head><title>Tweak view. Woohoo!</title><meta name="csrf_token" content="{{ csrf_token() }}"></head>'
                ret += "<body><h1>Tweak View</h1>"
                ret += f'<img src="/ui?{int(time.time())}">'
                if path: ret += f"<h2>Path</h2><code>{path!r}</code><p>"
                ret += "</body></html>"
                return render_template_string(ret)


        except Exception as err:
            self._logger.warning(f"webhook err: {err!r}")
            return f"<html><head><title>oops</title></head><body><code>{html.escape(repr(err))}</code></body></html>"

    # called when the plugin is loaded
    def on_loaded(self):
        self._start = time.time()
        self._state = 0
        self._next = 0


    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._agent = agent


    # called before the plugin is unloaded
    def on_unload(self, ui):
        try:
            state = ui._state._state
            # go through list of untweaks
            for tag, value in self._untweak.items():
                vss,element,key = tag.split(".")
                self._logger.debug(f"Reverting: {tag} to {value!r}")
                if key in dir(ui._state._state[element]):
                    if key == "xy":
                        ui._state._state[element].xy = value
                        self._logger.debug(f"Reverted {element} xy to {ui._state._state[element].xy!r}")
                    else:
                        try:
                            self._logger.debug(f"Trying to revert {tag}")
                            if hasattr(state, key):
                                setattr(ui._state._state[element], key, value)
                                self._logger.debug(f"Reverted {element} xy to {getattr(ui._state._state[element], key)!r}")
                        except Exception as err:
                            self._logger.warning(f"revert {tag}: {err!r}, {ui!r}")
        except Exception as err:
            self._logger.warning(f"ui unload: {err!r}, {ui!r}")



    # called to setup the ui elements
    # look at config. Move items around as desired
    def on_ui_setup(self, ui):
        self._ui = ui

        self.myFonts = {"Small": fonts.Small,
                   "BoldSmall": fonts.BoldSmall,
                   "Medium": fonts.Medium,
                   "Bold": fonts.Bold,
                   "BoldBig": fonts.BoldBig,
                   "Huge": fonts.Huge,
        }
        # include lots more sizes
        just_once = True
        for p in [6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 25, 28, 30, 35, 42, 48, 52, 54, 60, 69, 72, 80, 90, 100, 120]:
            try:
                self.myFonts[f"Deja {p}"] = ImageFont.truetype("DejaVuSansMono", p)
                self.myFonts[f"DejaB {p}"] = ImageFont.truetype("DejaVuSansMono-Bold", p)
                self.myFonts[f"DejaO {p}"] = ImageFont.truetype("DejaVuSansMono-Oblique", p)
            except Exception as e:
                if just_once:
                    logging.warning(f"Missing some fonts: {e!r}")
                    just_once = False

        # load a config file... /etc/pwnagotchi/tweak_view.json for default
        self._conf_file = self.options["filename"] if "filename" in self.options else "/etc/pwnagotchi/tweak_view.json"

        try:
            if os.path.isfile(self._conf_file):
                with open(self._conf_file) as f:
                    self._tweaks = json.load(f)
                    for i in self._tweaks:
                        self._logger.debug (f"Ready tweak {i} -> {self._tweaks[i]}")

            self._already_updated = []
            self._logger.info("Tweak view ready.")

        except Exception as err:
            self._logger.warning(f"TweakUI loading failed: {err!r}")

        try:
            self.update_elements(ui)
        except Exception as err:
            self._logger.warning(f"ui setup: {err!r}")

    def on_ui_update(self, ui):
        self.update_elements(ui)

    def update_elements(self, ui):
        # update those elements
        try:
            state = ui._state._state
            # go through list of tweaks
            updated = []
            for tag, value in self._tweaks.items():
                vss,element,key = tag.split(".")
                try:
                    if element not in self._already_updated and element in state and key in dir(state[element]):
                        if tag not in self._untweak:
                            #self._untweak[tag] = eval("ui._state._state[element].%s" % key)
                            self._untweak[tag] = getattr(ui._state._state[element], key)
                            self._logger.debug(f"Saved for unload: {tag} = {self._untweak[tag]}")

                        if key == "xy":
                            new_xy = value.split(",")
                            new_xy = [int(float(x.strip())) for x in new_xy]
                            if new_xy[0] < 0: new_xy[0] = ui.width() + new_xy[0]
                            if new_xy[1] < 0: new_xy[1] = ui.height() + new_xy[1]
                            if ui._state._state[element].xy != new_xy:
                                ui._state._state[element].xy = new_xy
                                self._logger.debug(f"Updated xy to {ui._state._state[element].xy!r}")
                        elif key == "font":
                            if value in self.myFonts:
                                ui._state._state[element].font = self.myFonts[value]
                        elif key == "text_font":
                            if value in self.myFonts:
                                ui._state._state[element].text_font = self.myFonts[value]
                        elif key == "alt_font":
                            if value in self.myFonts:
                                ui._state._state[element].alt_font = self.myFonts[value]
                        elif key == "label_font":
                            if value in self.myFonts:
                                ui._state._state[element].label_font = self.myFonts[value]
                        elif key == "color":
                            logging.debug(f"Color: {element} = {value}")
                            ui._state._state[element].color = value
                        elif key == "label":
                            ui._state._state[element].label = value
                        elif key == "label_spacing":
                            ui._state._state[element].label_spacing = int(value)
                        elif key == "max_length":
                            uie = ui._state._state[element]
                            uie.max_length = int(value)
                            uie.wrapper = TextWrapper(width=int(value), replace_whitespace=False) if uie.wrap else None
                        if element not in updated:
                            updated.append(element)
                    elif element in self._already_updated and element not in state:
                        # like a plugin unloaded
                        self._already_updated.remove(element)
                except Exception as err:
                    self._logger.warning(f"tweak failed for key {tag}: {err!r}")

            for element in updated:
                if element not in self._already_updated:
                    self._already_updated.append(element)
        except Exception as err:
            self._logger.warning(f"ui update: {err!r}, {ui!r}")
