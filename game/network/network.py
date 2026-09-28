#!/usr/bin/env python3
"""Zero Tower Battle - Network"""
class Network:
    def __init__(self):
        self.host = os.environ.get("ZTB_SSH_HOST", "127.0.0.1")
        self.port = 5000
        
    def connect(self):
        return True

