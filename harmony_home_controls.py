from sleekxmpp.xmlstream.handler.callback import Callback
from sleekxmpp.xmlstream.matcher.base import MatcherBase
from sleekxmpp.xmlstream import ET
import logging

logger = logging.getLogger(__name__)


class MatchHarmonyAutomationStateEvent(MatcherBase):
    def match(self, xml):
        """Check if a stanza matches the Harmony Home Control criteria (the light and socket buttons on the remote)."""
        payload = xml.get_payload()
        return len(payload) == 1 and payload[0].tag == '{connect.logitech.com}event' and payload[0].attrib['type'] == 'automation.state?notify'


class MatchHarmonyControlButtonPressEvent(MatcherBase):
    def match(self, xml):
        payload = xml.get_payload()
        return len(payload) == 1 and payload[0].tag == '{connect.logitech.com}event' and payload[0].attrib['type'] == 'control.button?pressType'


def register_automation_callback(harmony_client, home_control_callback):
    """Register a callback with an existing pyharmony client that is executed on home control events."""
    def hub_automation_state_event(xml):
        payload = xml.get_payload()[0].text
        logger.debug("Harmony State Event: %s" % payload)
        home_control_callback("automation.state", payload)
    
    def hub_automation_button_event(xml):
        payload = xml.get_payload()[0].text
        assert(payload[:5] == "type=" and (payload[5:] == "short" or payload[5:] == "long"))
        logger.debug("Harmony Button Event: %s button press" % payload[5:])
        home_control_callback("control.button", payload[5:])
    
    harmony_client.registerHandler(Callback('Home Control State', MatchHarmonyAutomationStateEvent(''), hub_automation_state_event))
    harmony_client.registerHandler(Callback('Home Control Button', MatchHarmonyControlButtonPressEvent(''), hub_automation_button_event))


