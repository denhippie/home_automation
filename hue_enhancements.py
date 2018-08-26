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

    
    
class HueMotionPatch(object):
    """ The hue motion sensor turns on and off lights when it detects motion.
        However: when another button turns on a light, the motion sensor does nothing.
        Until you walk past it, and it detects a motion, then the light goes finally off.
        Being annoyed with the light being on in the basement, this class patches this behavior.
        It needs to be periodically called, and will switch off all lights that should have been off all along.
    """
    
    def __init__(self, bridge, timeout_minutes):
        self.bridge  = bridge
        self.timeout = timeout_minutes
        self.sensors = self.map_sensors_to_groups()
    
    def find_motion_sensors(self, api):
        sensors = []
        for sensor_id in api['sensors']:
            try:
                if api['sensors'][sensor_id]['productname'] == 'Hue motion sensor':
                    sensors.append(sensor_id)
            except KeyError:
                pass
        return sensors
    
    def find_resource_for_sensor(self, api, sensor_id):
        for resource_id in api['resourcelinks']:
            try:
                if api['resourcelinks'][resource_id]['name'] == "MotionSensor %s" % sensor_id:
                    return resource_id
            except KeyError:
                pass
        return None
    
    def find_groups_for_resource(self, api, resource_id):
        groups = []
        for link in api['resourcelinks'][resource_id]['links']:
            if link[:len('/groups/')] == '/groups/':
                groups.append(link[len('/groups/'):])
        return groups

    def map_sensors_to_groups(self):
        mapping = dict()
        api = self.bridge.get_api()
        sensors = self.find_motion_sensors(api)
        for sensor_id in sensors:
            sensor_name = api['sensors'][sensor_id]['name']
            resource_id = self.find_resource_for_sensor(api, sensor_id)
            groups = self.find_groups_for_resource(api, resource_id)
            for group_id in groups:
                group_name = api['groups'][group_id]['name']
                print("Hue MotionSensor %s [%s] controls group %s [%s]" % (sensor_id, sensor_name, group_id, group_name))
                mapping[sensor_name] = group_name
        return mapping

    def check_lights(self):
        logger.debug("Checking Hue Light Timeout")
        for sensor_name in self.sensors:
            group_name = self.sensors[sensor_name]
            sensor = self.bridge.get_sensor(sensor_name)
            last_update = parse_hue_time(sensor['state']['lastupdated'])    
            time_since_last_update = datetime.datetime.utcnow() - last_update
            if time_since_last_update > datetime.timedelta(minutes=self.timeout) and self.bridge[group_name].on:
                logger.info("%s last activity %s ago, switching %s off." % (sensor_name, str(time_since_last_update), group_name))
                self.bridge[group_name].on = False


class HuePresets(object):
    def __init__(self, ip, button_handler):
        self.bridge  = Bridge(ip)
        self.sensors = []
        self.sensors.append(HueMotionPatch(self.bridge, 5))
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
