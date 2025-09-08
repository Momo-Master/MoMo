import logging
import os
from functools import partial
from threading import Lock

from pwnagotchi import plugins, reboot


def systemd_dropin(name, content):
    if not name.endswith(".service"):
        name = f"{name}.service"

    dropin_dir = f"/etc/systemd/system/{name}.d/"
    os.makedirs(dropin_dir, exist_ok=True)

    with open(os.path.join(dropin_dir, "switcher.conf"), "w") as dropin:
        dropin.write(content)

    systemctl("daemon-reload")


def systemctl(command, unit=None):
    if unit:
        os.system(f"/bin/systemctl {command} {unit}")
    else:
        os.system(f"/bin/systemctl {command}")


def run_task(name, options):
    task_service_name = f"switcher-{name}-task.service"
    # save all the commands to a shell script
    script_dir = "/usr/local/bin/"
    script_path = os.path.join(script_dir, f"switcher-{name}.sh")
    os.makedirs(script_dir, exist_ok=True)

    with open(script_path, "w") as script_file:
        script_file.write("#!/bin/bash\n")
        for cmd in options["commands"]:
            script_file.write(f"{cmd}\n")

    os.system(f"chmod a+x {script_path}")

    # here we create the service which runs the tasks
    with open(f"/etc/systemd/system/{task_service_name}", "w") as task_service:
        task_service.write(f"""
        [Unit]
        Description=Executes the tasks of the pwnagotchi switcher plugin
        After=pwnagotchi.service bettercap.service

        [Service]
        Type=oneshot
        RemainAfterExit=yes
        ExecStart=-/usr/local/bin/switcher-{name}.sh
        ExecStart=-/bin/rm /etc/systemd/system/{task_service_name}
        ExecStart=-/bin/rm /usr/local/bin/switcher-{name}.sh

        [Install]
        WantedBy=multi-user.target
        """)

    if options.get("reboot"):
        # create an indication file!
        # if this file is set, we want the switcher-tasks to run
        open("/root/.switcher", "a").close()

        # add condition
        systemd_dropin("pwnagotchi.service", """
        [Unit]
        ConditionPathExists=!/root/.switcher""")

        systemd_dropin("bettercap.service", """
        [Unit]
        ConditionPathExists=!/root/.switcher""")

        systemd_dropin(task_service_name, """
        [Service]
        ExecStart=-/bin/rm /root/.switcher
        ExecStart=-/bin/rm /etc/systemd/system/switcher-reboot.timer""")

        with open("/etc/systemd/system/switcher-reboot.timer", "w") as reboot_timer:
            reboot_timer.write("""
            [Unit]
            Description=Reboot when time is up
            ConditionPathExists=/root/.switcher

            [Timer]
            OnBootSec={}m
            Unit=reboot.target

            [Install]
            WantedBy=timers.target
            """.format(options["stopwatch"]))

        systemctl("daemon-reload")
        systemctl("enable", "switcher-reboot.timer")
        systemctl("enable", task_service_name)
        reboot()
        return

    systemctl("daemon-reload")
    systemctl("start", task_service_name)


class Switcher(plugins.Plugin):
    __author__ = "33197631+dadav@users.noreply.github.com"
    __version__ = "0.0.1"
    __name__ = "switcher"
    __license__ = "GPL3"
    __description__ = "This plugin is a generic task scheduler."

    def __init__(self):
        self.ready = False
        self.lock = Lock()

    def trigger(self, name, *args, **kwargs):
        with self.lock:
            function_name = name.lstrip("on_")
            if function_name in self.tasks:
                task = self.tasks[function_name]

                # is this task enabled?
                if "enabled" not in task or ("enabled" in task and not task["enabled"]):
                    return

                run_task(function_name, task)

    def on_loaded(self):
        if self.options.get("tasks"):
            self.tasks = self.options["tasks"]
        else:
            logging.debug("[switcher] No tasks found...")
            return

        logging.info("[switcher] is loaded.")

        # create hooks
        logging.debug("[switcher] creating hooks...")
        methods = ["webhook", "internet_available", "ui_setup", "ui_update",
                   "unload", "display_setup", "ready", "ai_ready", "ai_policy",
                   "ai_training_start", "ai_training_step", "ai_training_end",
                   "ai_best_reward", "ai_worst_reward", "free_channel",
                   "bored", "sad", "excited", "lonely", "rebooting", "wait",
                   "sleep", "wifi_update", "unfiltered_ap_list", "association",
                   "deauthentication", "channel_hop", "handshake", "epoch",
                   "peer_detected", "peer_lost", "config_changed"]

        for m in methods:
            setattr(Switcher, f"on_{m}", partial(self.trigger, m))

        logging.debug("[switcher] triggers are ready to fire...")
