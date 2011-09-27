
import nose, threading, time
from random import randint

from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase

from .ircd import IRCServer
from ..iobot import IOBot


class FakeIrcServer(threading.Thread):

    def __init__(self, host, port):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port

    def run(self):
        self.ircd = IRCServer((self.host, self.port), 'test.example.com')
        self.ircd.run()


class BotTestCases(AsyncTestCase):

    def get_new_ioloop(self):
        if not hasattr(self, 'io_loop'):
            self.io_loop = IOLoop.instance()
        return self.io_loop

    @classmethod
    def setUpClass(cls):
        cls.port = randint(4000,9999)
        cls.host = '127.0.0.1'
        cls.nick = 'testbot'
        cls.fakeircd = FakeIrcServer(cls.host, cls.port)
        cls.fakeircd.start()
        cls.bot = IOBot(nick=cls.nick, host=cls.host, port=cls.port)

    def setUp(self):
        # the ioloop needs time to spin for other tasks.  it's lame but we're
        # going to add a callback in a couple of secs to let things go
        self._spin_count = 0
        self.spin_till_connect(True)

    def spin_till_connect(self, first=False):
        # we need the ircbot to be connected to the stupid server
        self._spin_count += 1
        if self._spin_count > 1000: raise Exception('spun out of control')
        if not first:
            self.wait()
        if not self.bot._connected:
            self.get_new_ioloop().add_timeout(time.time()+1.5, self.stop)


    def test_ping(self):
        # going to fake a PING from the server on this one
        assert(self.bot._handle_ping('PING :12345'))

    def test_join(self):
        chan = '#testchan'
        self.bot.joinchan(chan, callback=self.stop)
        self.wait()

        assert(chan in self.fakeircd.ircd.channels)
        assert(self.nick in self.fakeircd.ircd.channels[chan].users)


