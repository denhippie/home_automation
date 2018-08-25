import pyharmony


class HarmonyStateMonitor(object):
    def __init__(self, ip, port, state_handler, logger):
        self.ip                   = ip
        self.port                 = port
        self.handler_func         = state_handler
        self.logger               = logger
        self.harmony_client       = None
        self.harmony_config_cache = None
        self.last_state           = None
        
    def connect(self):
        self.logger.info("connecting harmony: %s:%s" % (self.ip, self.port))
        self.harmony_client = pyharmony.get_client(self.ip, self.port, self.state_change_callback)
        self.harmony_config_cache = self.harmony_client.get_config()
        self.logger.info("Harmony connected. Connecting to ZMQ")
        self.last_state = self.get_activity()
    
    def disconnect(self):
        if self.harmony_client != None:
            self.harmony_client.disconnect(send_close=True)
            
    def state_change_callback(self, activity_id):
        activity_name = self.get_activity_name(activity_id)
        self.logger.info("State change callback [%s]" % activity_name)
        self.process_new_state(activity_name)
    
    def get_activity_name(self, current_activity_id):
        current_activity = ([x for x in self.harmony_config_cache['activity'] if int(x['id']) == current_activity_id][0])
        if type(current_activity) is dict:
            return current_activity['label'].strip()
        else:
            return None
    
    def get_activity_safe(self):
        for x in range(0, 3):
            try:
                current_activity_id = self.harmony_client.get_current_activity()
                return current_activity_id
            except:
                self.logger.info("Caught error while trying to get Harmony state.")
        # One more try, uncaught errors...
        return self.harmony_client.get_current_activity()
    
    def get_activity(self):
        return self.get_cached_activity_name(self.get_activity_safe())
        
    def get_cached_activity_name(self, activity_id):
        # Use the cached config first, getting the name takes way longer to get than the activity id.
        activity_name = self.get_activity_name(activity_id)
        if activity_name != None:
            return activity_name
        self.logger.info("refreshing config")
        self.harmony_config_cache = self.harmony_client.get_config()
        return self.get_activity_name(activity_id)
    
    def power_off(self):
        self.logger.info("Shutting down Harmony")
        self.harmony_client.power_off()
        
    def check_state_change(self):
        self.process_new_state(self.get_activity())
        
    def process_new_state(self, new_state):
        if new_state != self.last_state:
            self.logger.info("State change: [%s] --> [%s]" % (self.last_state, new_state))
            if self.handler_func != None:
                self.handler_func(self.last_state, new_state)
            self.last_state = new_state
