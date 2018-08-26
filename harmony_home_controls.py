import json 
from sleekxmpp.xmlstream.handler.callback import Callback
from sleekxmpp.xmlstream.matcher.base import MatcherBase
from sleekxmpp.xmlstream import ET



class MatchHarmonyHomeControlEvent(MatcherBase):
    def match(self, xml):
        """Check if a stanza matches the Harmony Home Control criteria (the light and socket buttons on the remote)."""
        payload = xml.get_payload()
        if len(payload) == 1:
            msg = payload[0]
            return msg.tag == '{connect.logitech.com}event' and msg.attrib['type'] == 'automation.state?notify'
        return False


def register_automation_callback(harmony_client, home_control_callback):
    """Register a callback with an existing pyharmony client that is executed on home control events."""
    def hub_event(xml):
        parsed_xml = json.loads(xml.get_payload()[0].text)
        # TODO: The control id is a UUID, that I can't match to anything in the Harmony conifguration.
        #       I use Philips Hue lights, and I can also not find this UUID in the Hue Bridge config.
        #       So for now: I hope that these UUIDs are stable, but hopefully I can figure out how to match them to human readable names...
        for home_control_id in parsed_xml:
            home_control_callback(home_control_id, parsed_xml[home_control_id])
        
    harmony_client.registerHandler(Callback('Home Control', MatchHarmonyHomeControlEvent(''), hub_event))


