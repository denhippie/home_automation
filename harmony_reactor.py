import pyharmony
import logging
import time
import harmony_home_controls
import json 


logger = logging.getLogger(__name__)


class HarmonyStateMonitor(object):
    """ Warpper class for the pyharmony client class.
        Adds some caching, utility functions, and multi-plexes the callback functions.
    """
    def __init__(self, ip, port):
        self.ip                   = ip
        self.port                 = port
        self.harmony_client       = None
        self.harmony_config_cache = None
        self.last_state           = None
        self.state_reactors       = []
        self.control_reactors     = []
        
    def connect(self):
        logger.info("connecting harmony: %s:%s" % (self.ip, self.port))
        self.harmony_client = pyharmony.get_client(self.ip, self.port, self.state_change_callback)
        self.harmony_config_cache = self.harmony_client.get_config()
        harmony_home_controls.register_automation_callback(self.harmony_client, self.home_control_callback)
        logger.info("Harmony connected.")
    
    def disconnect(self):
        if self.harmony_client != None:
            self.harmony_client.disconnect(send_close=True)
    
    def get_activity(self):
        return self.get_cached_activity_name(self.get_current_activity_id())
        
    def get_current_activity_id(self):
        for x in range(0, 3):
            try:
                current_activity_id = self.harmony_client.get_current_activity()
                return current_activity_id
            except:
                logger.info("Caught error while trying to get Harmony state.")
        # One more try, uncaught errors...
        return self.harmony_client.get_current_activity()
    
    def get_cached_activity_name(self, activity_id):
        # Use the cached config first, getting the name takes way longer to get than the activity id.
        activity_name = self.get_activity_name(activity_id)
        if activity_name != None:
            return activity_name
        logger.info("refreshing config")
        self.harmony_config_cache = self.harmony_client.get_config()
        return self.get_activity_name(activity_id)
    
    def get_activity_name(self, current_activity_id):
        current_activity = ([x for x in self.harmony_config_cache['activity'] if int(x['id']) == current_activity_id][0])
        if type(current_activity) is dict:
            return current_activity['label'].strip()
        else:
            return None
            
    def power_off(self):
        logger.info("Shutting down Harmony")
        self.harmony_client.power_off()
        
    def add_state_change_reactor(self, reactor):
        self.state_reactors.append(reactor)
        
    def state_change_callback(self, activity_id):
        activity_name = self.get_activity_name(activity_id)
        logger.info("State change callback [%s]" % activity_name)
        self.process_new_state(activity_name)
        
    def check_state_change(self):
        self.process_new_state(self.get_activity())
        
    def process_new_state(self, new_state):
        if new_state != self.last_state:
            logger.info("State change: [%s] --> [%s]" % (self.last_state, new_state))
            for reactor in self.state_reactors:
                reactor.harmony_state_change_handler(self, self.last_state, new_state)
            self.last_state = new_state
            
    def send_command(self, device_id, command, repeat=0, delay=0.1):
        logger.info("[%s] send command [%s]" % (device_id, command))
        self.harmony_client.send_command(device_id, command)
        for i in range(repeat):
            time.sleep(delay)
            logger.info("[%s] re-send command [%s]" % (device_id, command))
            
    def add_home_control_reactor(self, reactor):
        self.control_reactors.append(reactor)
        
    def home_control_callback(self, event, payload):
        logger.debug("Home Control callback [%s][%s]" % (event, payload))
        for reactor in self.control_reactors:
            reactor.harmony_home_control_handler(event, payload)


class SimpleHarmonyStateChangeReactor(object):
    """ Basic reactor to a harmony activity state change. 
        For a collection of states, callbacks will be invoked for when the activity is one of the states,
        and for when the activity is no longer in that collection of states.
    """
    def __init__(self, name, states, reaction, inverse_reaction):
        self.name     = name
        self.states   = states
        self.reaction = reaction
        self.inverse  = inverse_reaction
        
    def harmony_state_change_handler(self, harmony, old_state, new_state):
        logger.info("[%s] State change: [%s] --> [%s]" % (self.name, old_state, new_state))
        if new_state in self.states:
            logger.info("[%s] reacting on positive state change to [%s]" % (self.name, new_state))
            self.reaction()
        else:
            logger.info("[%s] reacting on inverse state change to [%s]" % (self.name, new_state))
            self.inverse()


class HarmonyHomeControlButtonReactor(object):
    """ Very simple reactor to harmony home control automation (the light and socket buttons on the remote). """
    # TODO: The control id is a UUID, that I can't match to anything in the Harmony conifguration.
    #       I use Philips Hue lights, and I can also not find this UUID in the Hue Bridge config.
    #       So for now: I hope that these UUIDs are stable, but hopefully I can figure out how to match them to human readable names...
    def __init__(self, name, home_control_id, reaction):
        self.name           = name
        self.id             = home_control_id
        self.reaction       = reaction
        self.button_pressed = False
        
    def harmony_home_control_handler(self, event, payload):
        if event == "control.button":
            logger.debug("Button pressed! Waiting for state message.")
            self.button_pressed = True
            return
        if self.button_pressed and event == "automation.state":
            parsed_xml = json.loads(payload)
            key, value = parsed_xml.popitem()
            logger.debug("Atomation state event %s" % key)
            if self.id == key:
                logger.info("[%s] home control invoked" % self.name)
                self.reaction()
        self.button_pressed = False

