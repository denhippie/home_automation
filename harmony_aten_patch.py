import logging

logger = logging.getLogger(__name__)


class HarmonyAtenPatch(object):
    """ The standard Aten VS-482 controls in the harmony database are not very reliable.
        By just blasting the controls a couple of times, I no longer have any issues.
    """
    def __init__(self, harmony):
        self.id = harmony.find_device_id('Aten AV Switch')
        if self.id == None:
            logging.warn("No Aten VS-482 found!")
    
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
