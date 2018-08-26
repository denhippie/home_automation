from phue import Bridge
import datetime
import logging

logger = logging.getLogger(__name__)


def parse_hue_time(hue_time):
    if hue_time == "none":
        return datetime.datetime.min
    #2016-12-25T13:35:37
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
        self.change_scene("Film")
    
    def relax_lights(self):
        logger.info("setting lights to relax mode")
        self.change_scene("Relax")
        
    def bright_lights(self):
        logger.info("setting lights to bright mode")
        self.change_scene("Bright")
        
    def lights_off(self):
        logger.info("switching lights off")
        self.change_scene("Off")
        
    def change_scene(self, scene):
        logger.info("setting lights to [%s] mode" % scene)
        for group_name in ["Tafel", "Hal", "Keuken", "Huiskamer"]:
            self.bridge.run_scene(group_name, scene)
        self.check_lights()    
        
    def check_lights(self):
        for sensor in self.sensors:
            sensor.check_lights()
