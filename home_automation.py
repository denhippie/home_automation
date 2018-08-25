
import time
import os
import subprocess
import harmony_reactor
import signal
import sys
import timeit
import logging
import zmq
import traceback
from phue import Bridge
import datetime
from pyHS100 import SmartPlug
from pprint import pformat
from multiprocessing import Process


logfile = '/var/log/hettiewol/hettiewol.log'
logging.basicConfig(filename=logfile,level=logging.INFO, format='%(asctime)s [%(name)s][%(levelname)s] %(message)s')
#logger.basicConfig(filename=logfile,level=logger.DEBUG, format='%(asctime)s %(message)s')
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
            
            
            
class HueLinkedPlug(object):
    def __init__(self, bridge, plug_ip, hue_light_name):
        self.bridge         = bridge        
        self.plug_ip        = plug_ip
        self.hue_light_name = hue_light_name
        self.reachable      = True
        self.hue_state      = self.get_hue_state()
    
    def check_online(self):
        response = -1
        try:
            response = os.system("ping -c 1 -w 1 %s > /dev/null" % self.plug_ip)
        except:
            logger.info("Failed to ping %s" % self.plug_ip)
        return response == 0
    
    def get_plug_state(self):
        plug = SmartPlug(self.plug_ip)
        return plug.state
        
    def get_plug_alias(self):
        plug = SmartPlug(self.plug_ip)
        return plug.alias
        
    def plug_switch(self, on):
        plug = SmartPlug(self.plug_ip)
        if on:
            plug.turn_on()
        else:
            plug.turn_off()
        
    def get_hue_state(self):
        return self.bridge[self.hue_light_name].on and self.bridge[self.hue_light_name].brightness >= 50
    
    def check_lights(self):
        logger.debug("Checking Hue Linked Plug %s: %s" % (self.hue_light_name, self.plug_ip))
        if not self.check_online():
            logger.debug("Hue Linked Plug %s is NOT online" % self.hue_light_name)
            if self.reachable:
                logger.info("Plug at %s unreachable, not able to link with %s" % (self.plug_ip, self.hue_light_name))
                self.reachable = False
            return
        elif not self.reachable:
            logger.info("Plug at %s came back online, linking with %s" % (self.plug_ip, self.hue_light_name))
            self.reachable = True
        logger.debug("Hue Linked Plug %s is online" % self.hue_light_name)
        plug_state = None
        hue_state  = None
        try:
            plug_state = self.get_plug_state()
            hue_state  = self.get_hue_state()
        except:
            logger.info("Plug at %s did not respond, not able to link with %s" % (self.plug_ip, self.hue_light_name))
            return
        if hue_state != self.hue_state:
            alias = self.get_plug_alias()
            logger.info("%s switched state, checking %s (%s)" % (self.hue_light_name, alias, self.plug_ip))
            self.hue_state = hue_state
            #logger.info("%s = %s | %s = %s" % (plug.alias, plug.state, self.hue_light_name, self.bridge[self.hue_light_name].on))
            if   plug_state == "ON" and not hue_state:
                logger.info("Switching %s OFF to match %s" % (alias, self.hue_light_name))
                self.plug_switch(False)
            elif plug_state == "OFF" and hue_state:
                logger.info("Switching %s ON to match %s" % (alias, self.hue_light_name))
                self.plug_switch(True)
        logger.debug("Finished checking Hue Linked Plug %s" % self.hue_light_name)
        
    
    
class HuePresets(object):
    def __init__(self, ip, button_handler):
        self.bridge  = Bridge(ip)
        self.sensors = []
        self.sensors.append(HueMotionFixer(self.bridge, "Berging sensor", 2, "Berging"))
        self.sensors.append(HueMotionFixer(self.bridge, "Entree sensor", 10, "Entree"))
        #self.sensors.append(HueLinkedPlug(self.bridge, "XXX.XXX.XXX.XXX", "Projectiescherm")) # Glazen Bol
        #self.sensors.append(HueLinkedPlug(self.bridge, "XXX.XXX.XXX.XXX", "Projectiescherm")) # Staande Lamp
        #self.sensors.append(HueLinkedPlug(self.bridge, "XXX.XXX.XXX.XXX", "Projectiescherm")) # Kerstboom
        self.sensors.append(HueButtonAction(self.bridge, "Entree switch", button_handler))
        self.sensors.append(HueButtonAction(self.bridge, "Slaapkamer switch", button_handler))

    def change_scene_if_on(self, group_name, scene_name):
        group = self.bridge.get_group(group_name)
        if group["state"]["any_on"]:
            self.bridge.run_scene(group_name, scene_name)
        else:
            logger.info("%s: not changing to scene %s, all lights are off." % (group_name, scene_name))
        
    def movie_lights(self):
        logger.info("setting lights to movie mode")
        for group_name in ["Tafel", "Hal", "Keuken", "Huiskamer"]:
            #self.change_scene_if_on(group_name, "Film")
            self.bridge.run_scene(group_name, "Film")
        self.check_lights()
    
    def relax_lights(self):
        logger.info("setting lights to relax mode")
        for group_name in ["Tafel", "Hal", "Keuken", "Huiskamer"]:
            #self.change_scene_if_on(group_name, "Relax")
            self.bridge.run_scene(group_name, "Relax")
        self.check_lights()
        
    def check_lights(self):
        for sensor in self.sensors:
            sensor.check_lights()

    

class WindowsPcPower(object):
    def __init__(self, name, ip, mac, broadcast_ip, username, password):
        self.name         = name
        self.ip           = ip
        self.mac          = mac
        self.broadcast_ip = broadcast_ip
        self.username     = username
        self.password     = password
        
    def check_online(self):
        response = os.system("ping -c 1 -w 1 %s > /dev/null" % self.ip)
        if response == 0:
            logger.info('%s is up!' % self.name)
            return True
        else:
            logger.info('%s is down!' % self.name)
            return False
    
    def send_wol(self):
        logger.info("seding wol packet to %s" % self.name)
        os.system("wakeonlan -i %s %s" % (self.broadcast_ip, self.mac))
    
    def wake_hettie(self):
        logger.info("Waking %s" % self.name)
        if self.check_online():
            logger.info("%s already awake." % self.name)
            return
        self.send_wol()
    
    def send_shutdown(self):
        logger.info("sending shutdown to %s" % self.name)
        shutdown_command = "net rpc shutdown -f -t 1 -I %s -U %s%%%s" % (self.ip, self.username, self.password)
        os.system(shutdown_command)
    
    def shutdown_hettie(self):
        logger.info("Shutting down %s" % self.name)
        if not self.check_online():
            logger.info("%s already down." % self.name)
            return
        self.send_shutdown()


class ZmqEvents(object):
    def __init__(self, port, message_handler):
        self.message_handler = message_handler
        self.zmq_context = zmq.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.SUB)
        self.zmq_socket.setsockopt(zmq.SUBSCRIBE, '')
        self.zmq_socket.connect("tcp://localhost:%d" % port)
        logger.info("ZMQ connected.")
        
    def check_zmq_event(self):
        logger.debug("Checking ZMQ event")
        try:
            message = self.zmq_socket.recv(flags=zmq.NOBLOCK)
            logger.info("Received message [%s]" % message)
            #self.check_state_change()
            self.message_handler(message)
            return True
        except:
            return False
    


class NestMultiProcess(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password
        
    def nest_away(self):
        logger.info("Setting Nest to away")
        os.system("nest -u %s -p %s -c away --away" % (self.username, self.password))
        logger.info("Setting Nest to away - done")

    def nest_home(self):
        logger.info("Setting Nest to home")
        os.system("nest -u %s -p %s -c away --home" % (self.username, self.password))
        logger.info("Setting Nest to home - done")
        
    def nest_temp(self, temp):
        logger.info("Setting Nest target temperature to %f" % temp)
        os.system("nest -u %s -p %s -c temp %f" % (self.username, self.password, temp))
        logger.info("Setting Nest target temperature to %f - done" % temp)
        
    def nest_home_and_temp(self, home, temp):
        self.nest_temp(temp)
        if home:
            self.nest_home()
        else:
            self.nest_away()
            
    def multi_home_and_temp(self, home, temp):
        p = Process(target=self.nest_home_and_temp, args=(home, temp, ))
        p.start()
    
    def multi_temp(self, temp):
        p = Process(target=self.nest_temp, args=(temp, ))
        p.start()

    
        
class HomeAutomation(object):
    def __init__(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.hettie_power = WindowsPcPower("<PCNAME>", "<PC-IP>", "<PC-MAC>", "<BROADCAST_IP>", "<LOGIN>", "<PASSWORD>")
        self.hue_presets  = HuePresets("<HUE-BRIDGE-IP>", self.hue_button_event_handler)
        self.nest         = NestMultiProcess("<NEST-USERNAME>", "<NEST-PASSWORD>")
        self.harmony      = harmony_reactor.HarmonyStateMonitor("<HARMONY-HUB-IP>", 5222, self.harmony_state_change_handler, logging)
        self.dac_power    = SmartPlug("<WIFI-SOCKET-IP>")
        self.zmq          = ZmqEvents(<ZMQ-PORT>, self.zmq_message_handler)
        self.harmony.connect()
        
    def harmony_state_change_handler(self, old_state, new_state):
        #if old_state == "Film":
        #    self.hue_presets.relax_lights()
        #if new_state == "Film":
        #    self.hue_presets.movie_lights()
        logger.info("Harmony state change: [%s] --> [%s]" % (old_state, new_state))
        if self.hettie_should_be_on(old_state) and not self.hettie_should_be_on(new_state):
            self.hettie_power.shutdown_hettie()
        elif not self.hettie_should_be_on(old_state) and self.hettie_should_be_on(new_state):
            self.hettie_power.send_wol()
        self.check_dac_state(new_state)

    def check_dac_state(self, new_state):
        dac_cur = self.dac_power.state
        logger.debug("Checking DAC state: current[%s] activity[%s]" % (dac_cur, new_state))
        if new_state == "PowerOff" and dac_cur == "ON":
            logger.info("Switching DAC OFF")
            self.dac_power.turn_off()
        elif new_state != "PowerOff" and dac_cur == "OFF":
            logger.info("Switching DAC ON")
            self.dac_power.turn_on()
    
    def zmq_message_handler(self, message):
        if message[:10] == "RelaxLight":
            self.hue_presets.relax_lights()
        if message[:9] == "FilmLight":
            self.hue_presets.movie_lights()
    
    def hettie_should_be_on(self, state):
        return state == "Film" or state == "Listen to Music"

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

    def check_state(self):
        self.harmony.check_state_change()
        self.check_dac_state(self.harmony.get_activity())

    def main_loop(self):
        try:
            counter = 0
            while True:
                logger.debug("Run %d" % counter)
                while self.zmq.check_zmq_event():
                    pass
                if counter % 5 == 0:
                    self.hue_presets.check_lights()
                if counter % 60 == 0:
                    self.check_state()
                if counter % 600 == 0:
                    logger.info("Still alive! Iteration count %d" % counter)
                time.sleep(1)
                logger.debug("Run %d completed" % counter)
                counter = counter + 1
        except:
            logger.info("Caught an exception, shutting down.")
            logger.info(traceback.format_exc())
            logger.info("bla")
            self.harmony.disconnect()
            sys.exit(0)    
    


automation = HomeAutomation()
automation.main_loop()
