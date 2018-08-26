import logging

logger = logging.getLogger(__name__)


class HarmonyAtenPatch(object):
    def __init__(self, harmony):
        self.id = self.find_id(harmony.harmony_config_cache)
        
    def find_id(self, config):
        for device in config['device']:
            if device['manufacturer'] == 'Aten' and device['model'] == 'VS-482':
                logging.info("mapping to device id [%s]" % device['id'])
                return device['id']
        logging.warn("No Aten VS-482 found!")
        return None
    
    def harmony_state_change_handler(self, harmony, old_state, new_state):
        logger.info("State change: [%s] --> [%s]" % (old_state, new_state))
        if new_state == "PowerOff":
            harmony.send_command(self.id, "PowerOff", 3)
        elif new_state == "Film" or new_state == "Listen to Music":
            harmony.send_command(self.id, "PowerOn", 3)
            harmony.send_command(self.id, "InputPort1", 3)
        elif new_state == "Watch TV":
            harmony.send_command(self.id, "PowerOn", 3)
            harmony.send_command(self.id, "InputPort2", 3)
