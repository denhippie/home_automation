import os
import logging
from multiprocessing import Process


logger = logging.getLogger(__name__)


class NestMultiProcess(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password
        
    def nest_away(self):
        logger.info("Setting Nest to away")
        os.system("nest -u %s -p %s -c away --away" % (self.username, self.password))
        logger.info("Setting Nest to away - done")

    def nest_home(self):
        logger.info("Setting Nest to home")
        os.system("nest -u %s -p %s -c away --home" % (self.username, self.password))
        logger.info("Setting Nest to home - done")
        
    def nest_temp(self, temp):
        logger.info("Setting Nest target temperature to %f" % temp)
        os.system("nest -u %s -p %s -c temp %f" % (self.username, self.password, temp))
        logger.info("Setting Nest target temperature to %f - done" % temp)
        
    def nest_home_and_temp(self, home, temp):
        self.nest_temp(temp)
        if home:
            self.nest_home()
        else:
            self.nest_away()
            
    def multi_home_and_temp(self, home, temp):
        p = Process(target=self.nest_home_and_temp, args=(home, temp, ))
        p.start()
    
    def multi_temp(self, temp):
        p = Process(target=self.nest_temp, args=(temp, ))
        p.start()
