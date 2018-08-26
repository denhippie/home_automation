
import windows_power
import harmony_reactor
import nest_process

import time
import subprocess
import signal
import sys
import timeit
import logging
import zmq
import traceback
import configparser

from phue import Bridge
import datetime
from pyHS100 import SmartPlug
from pprint import pformat


config = configparser.RawConfigParser()
config.read('home_automation.cfg')

logfile = config.get('log', 'file')
loglevel = logging.getLevelName(config.get('log', 'level'))
logging.basicConfig(filename=logfile,level=loglevel, format='%(asctime)s [%(name)s][%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


sys.stdout = open(logfile, 'a')
sys.stderr = open(logfile, 'a')

logger.info("======================================================================================")


def parse_hue_time(hue_time):
    if hue_time == "none":
        return datetime.datetime.min
    return datetime.datetime.strptime(hue_time, '%Y-%m-%dT%H:%M:%S')    


class HueButtonAction(object):
    def __init__(self, hue_bridge, sensor_name, button_handler):
        sensors = hue_bridge.get_sensor_objects(mode='name')
        self.bridge         = hue_bridge
        self.sensor         = sensors[sensor_name]
        self.button_handler = button_handler
        self.button_time    = datetime.datetime.utcnow()
        
    def get_last_updated(self):
        return parse_hue_time(self.sensor.state["lastupdated"])
        
    def get_button_state(self):
        if "buttonevent" in self.sensor.state:
            return self.sensor.state["buttonevent"]
        return "None"

    def check_lights(self):
        logger.debug("Checking Hue Button Action")
        last_updated = self.get_last_updated()
        if last_updated <= self.button_time:
            return
        self.button_time = last_updated
        new_button_state = self.get_button_state()
        logger.info("%s button pressed! Invoking handler." % self.sensor.name)
        self.button_handler(self.sensor.name, new_button_state)

    
    
class HueMotionFixer(object):
    def __init__(self, bridge, sensor_name, timeout_minutes, lights):
        self.bridge      = bridge
        self.sensor_name = sensor_name
        self.timeout     = timeout_minutes
        self.lights      = lights
    
    def check_lights(self):
        logger.debug("Checking Hue Light Timeout")
        sensor = self.bridge.get_sensor(self.sensor_name)
        #2016-12-25T13:35:37
        last_update = parse_hue_time(sensor['state']['lastupdated'])    
        time_since_last_update = datetime.datetime.utcnow() - last_update
        if time_since_last_update > datetime.timedelta(minutes=self.timeout) and self.bridge[self.lights].on:
            logger.info("%s last activity %s ago, switching %s off." % (self.sensor_name, str(time_since_last_update), self.lights))
            self.bridge[self.lights].on = False


class HuePresets(object):
    def __init__(self, ip, button_handler):
        self.bridge  = Bridge(ip)
        self.sensors = []
        self.sensors.append(HueMotionFixer(self.bridge, "Berging sensor", 2, "Berging"))
        self.sensors.append(HueMotionFixer(self.bridge, "Entree sensor", 10, "Entree"))
        self.sensors.append(HueButtonAction(self.bridge, "Entree switch", button_handler))
        self.sensors.append(HueButtonAction(self.bridge, "Slaapkamer switch", button_handler))

    def movie_lights(self):
        logger.info("setting lights to movie mode")
        for group_name in ["Tafel", "Hal", "Keuken", "Huiskamer"]:
            self.bridge.run_scene(group_name, "Film")
        self.check_lights()
    
    def relax_lights(self):
        logger.info("setting lights to relax mode")
        for group_name in ["Tafel", "Hal", "Keuken", "Huiskamer"]:
            self.bridge.run_scene(group_name, "Relax")
        self.check_lights()
        
    def check_lights(self):
        for sensor in self.sensors:
            sensor.check_lights()



class ZmqEvents(object):
    def __init__(self, port, message_handler):
        self.message_handler = message_handler
        self.zmq_context = zmq.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.SUB)
        self.zmq_socket.setsockopt(zmq.SUBSCRIBE, b'')
        self.zmq_socket.connect("tcp://localhost:%d" % port)
        logger.info("ZMQ connected.")
        
    def check_zmq_event(self):
        logger.debug("Checking ZMQ event")
        try:
            message = self.zmq_socket.recv(flags=zmq.NOBLOCK).decode("utf-8")
            logger.info("Received message [%s]" % message)
            self.message_handler(message)
            return True
        except:
            return False



class HomeAutomation(object):
    def __init__(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.pc_power = windows_power.WindowsPower(config.get('windowspc', 'name'), config.get('windowspc', 'ip'), config.get('windowspc', 'mac'), 
                                                   config.get('network', 'broadcast_ip'), config.get('windowspc', 'username'), config.get('windowspc', 'password'))
        self.hue_presets  = HuePresets(config.get('hue', 'bridge_ip'), self.hue_button_event_handler)
        self.nest         = nest_process.NestMultiProcess(config.get('nest', 'username'), config.get('nest', 'password'))
        self.harmony      = harmony_reactor.HarmonyStateMonitor(config.get('harmony', 'ip'), config.getint('harmony', 'port'))
        self.dac_power    = SmartPlug(config.get('dac', 'ip'))
        self.zmq          = ZmqEvents(config.getint('zmq', 'port'), self.zmq_message_handler)
        self.harmony.add_state_change_reactor(harmony_reactor.SimpleHarmonyStateChangeReactor("PcPower",  ["Film", "Listen to Music"], self.pc_power.send_wol,  self.pc_power.shutdown_if_online))
        self.harmony.add_state_change_reactor(harmony_reactor.SimpleHarmonyStateChangeReactor("DacPower", ["PowerOff"],                self.dac_power.turn_off, self.dac_power.turn_on))
        self.harmony.connect()

    def zmq_message_handler(self, message):
        if message[:10] == "RelaxLight":
            self.hue_presets.relax_lights()
        if message[:9] == "FilmLight":
            self.hue_presets.movie_lights()
    
    def hue_button_event_handler(self, sensor, button):
        logger.info("Button event: %s %s" % (sensor, button))
        if sensor == "Entree switch":
            if button == 34:
                logger.info("Leaving the house")
                self.harmony.power_off()
                self.nest.multi_home_and_temp(False, 15)
            elif button in [16, 17, 18]:
                logger.info("Coming home!")
                self.nest.multi_home_and_temp(True, 20)
        elif sensor == "Slaapkamer switch":
            if button == 34:
                logger.info("Going to sleep")
                self.harmony.power_off()
                self.nest.multi_temp(15)
        
    def signal_handler(self, signal, frame):
        logger.info('You pressed Ctrl+C!')
        self.harmony.disconnect()
        sys.exit(0)

    def main_loop(self):
        try:
            counter = 0
            while True:
                logger.debug("Run %d" % counter)
                while self.zmq.check_zmq_event():
                    pass
                if counter % 5 == 0:
                    self.hue_presets.check_lights()
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
