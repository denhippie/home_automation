import os
import logging

logger = logging.getLogger(__name__)


class WindowsPower(object):
    """ Utility class for turning on and off a windows PC.
        Requires 'wakeonlan' to be installed, as well as net rpc to be working.
    """
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
    
    def send_shutdown(self):
        logger.info("sending shutdown to %s" % self.name)
        shutdown_command = "net rpc shutdown -f -t 1 -I %s -U %s%%%s" % (self.ip, self.username, self.password)
        os.system(shutdown_command)
    
    def shutdown_if_online(self):
        logger.info("Shutting down %s" % self.name)
        if not self.check_online():
            logger.info("%s already down." % self.name)
            return
        self.send_shutdown()
