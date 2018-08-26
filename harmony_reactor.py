import pyharmony
import logging

logger = logging.getLogger(__name__)

class HarmonyStateMonitor(object):
    def __init__(self, ip, port):
        self.ip                   = ip
        self.port                 = port
        self.harmony_client       = None
        self.harmony_config_cache = None
        self.last_state           = None
        self.reactors             = []
        
    def connect(self):
        logger.info("connecting harmony: %s:%s" % (self.ip, self.port))
        self.harmony_client = pyharmony.get_client(self.ip, self.port, self.state_change_callback)
        self.harmony_config_cache = self.harmony_client.get_config()
        logger.info("Harmony connected.")
        self.check_state_change()
    
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
        logger.info("Adding reactor")
        self.reactors.append(reactor)
        
    def state_change_callback(self, activity_id):
        activity_name = self.get_activity_name(activity_id)
        logger.info("State change callback [%s]" % activity_name)
        self.process_new_state(activity_name)
        
    def check_state_change(self):
        self.process_new_state(self.get_activity())
        
    def process_new_state(self, new_state):
        if new_state != self.last_state:
            logger.info("State change: [%s] --> [%s]" % (self.last_state, new_state))
            for reactor in self.reactors:
                reactor.harmony_state_change_handler(self, self.last_state, new_state)
            self.last_state = new_state


            
class SimpleHarmonyStateChangeReactor(object):
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
