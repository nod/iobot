
import nose, threading, time
from random import randint

from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase

from ircd import IRCServer
from iobot import IOBot


class FakeIrcServer(threading.Thread):

    def __init__(self, host, port):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port

    def run(self):
        self.ircd = IRCServer((self.host, self.port), 'test.example.com')


class BotTestCases(AsyncTestCase):

    def get_new_ioloop(self):
        if not hasattr(self, 'io_loop'):
            self.io_loop = IOLoop.instance()
        return self.io_loop

    @classmethod
    def setUpClass(cls):
        cls.port = randint(4000,9999)
        cls.host = '127.0.0.1'
        cls.fakeircd = FakeIrcServer(cls.host, cls.port)
        cls.fakeircd.start()
        cls.bot = IOBot(nick='testbot', host=cls.host, port=cls.port)

    def setUp(self):
        # the ioloop needs time to spin for other tasks.  it's lame but we're
        # going to add a callback in a couple of secs to let things go
        io_loop = self.get_new_ioloop()
        io_loop.add_timeout(time.time()+1, self.stop)
        self.wait()

    def test_ping(self):
        # going to fake a PING from the server on this one
        assert(self.bot._handle_ping('PING :12345'))

    def test_join(self):
        chan = '#testchan'
        print "before joinchan"
        self.bot.joinchan(chan, callback=self.stop)
        print "after joinchan"
        self.wait()
        print "after wait"

        assert(nick in self.fakeircd.ircd.chans[chan].users)

