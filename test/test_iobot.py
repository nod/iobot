import unittest
from random import randint

class BotTestCases(unittest.TestCase):

    def setUp(self):
        self.port = randint(4000,9999)
        self.host = '127.0.0.1'
        self.ircd = IRCServer(('0.0.0.0', self.port), 'tester.example.com')



    def test_ping(self):



