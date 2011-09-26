
import nose, threading, time
from random import randint

from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase

from ircd import IRCServer
from src import IOBot


class FakeIrcServer(threading.Thread):

    def __init__(self, host, port):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port

    def run(self):
        self.ircd = IRCServer((self.host, self.port), 'test.example.com')


class BotTestCases(AsyncTestCase):

    def get_new_ioloop(self):
        return IOLoop.instance()

    @classmethod
    def setUpClass(cls):
        cls.port = randint(4000,9999)
        cls.host = '127.0.0.1'
        cls.fakeircd = FakeIrcServer(cls.host, cls.port)
        cls.fakeircd.start()
        cls.bot = IOBot(nick='testbot', host=cls.host, port=cls.port)

    def test_ping(self):
        # going to fake a PING from the server on this one
        assert(self.bot._is_ping('PING :12345'))

    def test_join(self):
        chan = '#testchan'
        print "before joinchan"
        self.bot.joinchan(chan, callback=self.stop)
        print "after joinchan"
        self.wait()
        print "after wait"

        assert(nick in self.fakeircd.ircd.chans[chan].users)


