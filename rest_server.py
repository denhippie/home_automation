
import http.server
import json
import logging


logger = logging.getLogger(__name__)


class RESTRequestHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        return http.server.BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def get_payload(self):
        payload_len = int(self.headers.get('content-length', 0))
        payload = self.rfile.read(payload_len)
        payload = json.loads(payload.decode())
        return payload
        
    def do_PUT(self):
        payload = self.get_payload()
        self.send_response(200)
        self.end_headers()
        self.server.handle_payload(payload)

        
class RESTServer(http.server.HTTPServer):
    def __init__(self, port):
        super().__init__(('', port), RESTRequestHandler)
        self.handlers = dict()
        self.timeout = 0.01
        self.got_message = False
        
    def set_topic_handler(self, topic, handler):
        self.handlers[topic] = handler
        
    def handle_till_done(self):
        self.got_message = False
        self.handle_request()
        while self.got_message:
            self.got_message = False
            self.handle_request()
    

    def handle_payload(self, payload):
        self.got_message = True
        for k,v in payload.items():
            logger.info("[%s]=[%s]" % (k,v))
            if k in self.handlers:
                self.handlers[k](v)
