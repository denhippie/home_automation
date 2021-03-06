
import windows_power
import harmony_reactor
import nest_process
import hue_reactor
import rest_server

import time
import signal
import sys
import logging
import traceback
import configparser


config = configparser.RawConfigParser()
config.read('home_automation.cfg')

logfile = config.get('log', 'file')
loglevel = logging.getLevelName(config.get('log', 'level'))
logging.basicConfig(filename=logfile,level=loglevel, format='%(asctime)s [%(name)s][%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


sys.stdout = open(logfile, 'a')
sys.stderr = open(logfile, 'a')

logger.info("======================================================================================")


class HomeAutomation(object):
    """ This class wires all the stuff in my home together.
        As-is, this will only be useful for you when you have exactly the same components as I do, and named them identically...
        Otherwise, I hope that the other modules I built are useful to you, and this class illustrates how you can tie them together.
    """
    def __init__(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.pc_power     = windows_power.WindowsPower(config.get('windowspc', 'name'), config.get('windowspc', 'ip'), config.get('windowspc', 'mac'), 
                                                       config.get('network', 'broadcast_ip'), config.get('windowspc', 'username'), config.get('windowspc', 'password'))
        self.hue          = hue_reactor.HueReactor(config.get('hue', 'bridge_ip'))
        self.nest         = nest_process.NestMultiProcess(config.get('nest', 'username'), config.get('nest', 'password'))
        self.harmony      = harmony_reactor.HarmonyStateMonitor(config.get('harmony', 'ip'), config.getint('harmony', 'port'))
        self.harmony.connect()
        self.harmony.add_state_change_reactor(harmony_reactor.SimpleHarmonyStateChangeReactor("PcPower",  ["Film"], self.pc_power.send_wol,  self.pc_power.shutdown_if_online))
        self.harmony.add_home_control_reactor(harmony_reactor.HarmonyHomeControlButtonReactor("Movie",  "77d2b682-de20-4f37-a973-d05d8369dcc2", lambda:self.hue.change_scene("Film",   ["Tafel", "Hal", "Keuken", "Huiskamer"])))
        self.harmony.add_home_control_reactor(harmony_reactor.HarmonyHomeControlButtonReactor("Relax",  "37d25dad-9d46-458f-3e4c-983065dde0b9", lambda:self.hue.change_scene("Relax",  ["Tafel", "Hal", "Keuken", "Huiskamer"])))
        self.harmony.add_home_control_reactor(harmony_reactor.HarmonyHomeControlButtonReactor("Bright", "8d4c36b8-2605-4706-aeba-68cdb42b9767", lambda:self.hue.change_scene("Bright", ["Tafel", "Hal", "Keuken", "Huiskamer"])))
        self.harmony.add_home_control_reactor(harmony_reactor.HarmonyHomeControlButtonReactor("Off",    "326573f4-cc82-4101-3e5f-8d38385055be", lambda:self.hue.change_scene("Off",    ["Tafel", "Hal", "Keuken", "Huiskamer"])))
        self.harmony.check_state_change()
        self.hue.add_button_action("Entree switch",     self.hue_button_event_handler_entree)
        self.hue.add_button_action("Slaapkamer switch", self.hue_button_event_handler_bedroom)
        self.rest = rest_server.RESTServer(config.getint('rest_server', 'port'))
        self.rest.set_topic_handler("hue_scene", lambda scene : self.hue.change_scene(scene, ["Tafel", "Hal", "Keuken", "Huiskamer"]))
        self.rest.set_topic_handler("harmony_activity", lambda activity : self.harmony.start_activity(activity))
        self.rest.set_topic_handler("harmony_amp", lambda command : self.harmony.send_command(self.harmony.find_device_id('SimAudio Moon 390'), command))
        logger.debug("Main class initialized.")
    
    def hue_button_event_handler_entree(self, sensor, button):
        logger.info("Button event: %s %s" % (sensor, button))
        assert(sensor == "Entree switch")
        if button == 34:
            logger.info("Leaving the house")
            self.harmony.power_off()
            self.nest.multi_home_and_temp(False, 15)
        elif button in [16, 17, 18]:
            logger.info("Coming home!")
            self.nest.multi_home_and_temp(True, 20)
            
    def hue_button_event_handler_bedroom(self, sensor, button):
        logger.info("Button event: %s %s" % (sensor, button))
        assert(sensor == "Slaapkamer switch")
        if button == 34:
            logger.info("Going to sleep")
            self.harmony.power_off()
            self.nest.multi_temp(15)
        
    def signal_handler(self, signal, frame):
        logger.info('You pressed Ctrl+C!')
        self.harmony.disconnect()
        sys.exit(0)

    def main_loop(self):
        logger.debug("Starting main loop")
        try:
            counter = 0
            while True:
                logger.debug("Run %d" % counter)
                self.rest.handle_till_done()
                if counter % 5 == 0:
                    self.hue.check_sensors()
                if counter % 600 == 0:
                    logger.info("Still alive! Iteration count %d" % counter)
                time.sleep(1)
                logger.debug("Run %d completed" % counter)
                counter = counter + 1
        except:
            logger.info("Caught an exception, shutting down.")
            logger.info(traceback.format_exc())
            self.harmony.disconnect()
            sys.exit(0)    
    


automation = HomeAutomation()
automation.main_loop()
