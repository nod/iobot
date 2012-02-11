
import nose, socket, threading, time, unittest
from random import randint

from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase

from ..iobot import IOBot


class FakeIrcServer(threading.Thread):

    def __init__(self, host, port):
        super(type(self), self).__init__()
        self.setDaemon(True) # lets us kill this thread when tests end
        self._addr = (host, port)
        self._nick = 'meh'
        self.run_forrest = True
        self.reset_protocol()
        self.reset_msgs()

        self.testing_callback = None

        # setup the socket here.  the init is blocking so we want to do this
        # here and not in the run(...) which isn't blocking in the main thread
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind(self._addr)
        self.s.listen(5)

    def reset_msgs(self):
        self._msgs = dict()

    def reset_protocol(self):
        self._p = dict(
            NICK = self._p_nick,
            USER = self._p_user,
            JOIN = self._p_join,
            PRIVMSG = self._p_msg,
            )

    def _p_join(self, ln):
        toks = ln.split()
        chan = toks[1][1:]

        # :other!~oth@127.0.0.1 JOIN :#223
        join_msg =  ":blah!~blah@127.0.0.1 JOIN :{}".format(chan)
        if chan in self._msgs:
            self._msgs[chan].append(join_msg)
        else:
            self._msgs[chan] = [join_msg]

        print "_msgs", self._msgs

        self.raw_out(
            ':{}!~{}@localhost JOIN :{}\r\n'.format(
                self._nick,
                self._nick,
                chan
                )
            )
        self.out('MODE', '{} +nt'.format(toks[1]))
        self.out(
            '353',
            '{} = {} :@{}'.format(self._nick, toks[1], self._nick)
            )
        self.out(
            '366',
            '{} {} :End of /NAMES list'.format(self._nick,toks[1])
            )

    def _p_msg(self, line):
        # PRIVMSG #dest :blah
        print "p_msg", line
        toks = line.split()
        dest = toks[1]
        msg = line[line.find(':'):]

        if dest not in self._msgs:
            #:iobot.testnet 461 other PRIVMSG :No such channel
            self.out(
                "461 {} PRIVMSG:",
                "No such channel"
                )
        self._msgs[dest].append(msg)

    def _p_nick(self, line):
        self._nick = line.split()[1]

    def _p_user(self, line):
        for s,msg in (
                ('001', 'meh :Howdy!'),
                ('002', 'meh :You are someone!~meh@x.x.x.x'),
                ('372', 'meh :This is testing, fool!'),
                ('376', 'meh :End of /MOTD command.'),
                ):
            self.out(s, msg)

    def raw_out(self, txt):
        self.cs.send(txt)

    def out(self, statusnum, txt):
        self.cs.send(':faker.irc {} {}\r\n'.format(statusnum, txt))

    def add_proto(self, cmd, rtrn):
        """
        adds a command to the protocol.

        cmd: a text token, like 'JOIN'
        rtrn: should be a callable that accepts self and the line of input
            - communication back to the client should call self.out(...)
        """
        self._p[cmd] = rtrn

    def parse_line(self, line):
        print "PARSING", line
        tokens = line.split()
        if tokens and tokens[0].upper() in self._p:
            self._p[tokens[0].upper()](line)
        else:
            self.out('421', 'a meh :Unknown command')

        if self.testing_callback:
            print "calling callback", tokens
            self.testing_callback(tokens[0])

    def stop(self):
        self.run_forrest = False
        del self.s

    def run(self):

        while self.run_forrest:
            s, a = self.s.accept()
            buf = s.recv(1024)
            print "recvd:", buf
            self.cs = s
            self.parse_line(buf)


class BotTestCases(AsyncTestCase):

    @classmethod
    def tearDownClass(cls):
        cls.fakeircd.stop()
        del cls.fakeircd

    @classmethod
    def setUpClass(cls):
        cls.port = randint(4000,59999)
        cls.host = '127.0.0.1'
        cls.nick = 'meh'
        cls.fakeircd = FakeIrcServer(cls.host, cls.port)
        cls.fakeircd.start()
        cls.bot = IOBot(nick=cls.nick, host=cls.host, port=cls.port)

    def setUp(self):
        super(BotTestCases, self).setUp()
        self.fakeircd.reset_msgs()
        self.fakeircd.reset_protocol()

    def test_ping(self):
        # going to fake a PING from the server on this one
        self._was_pinged = False
        self.bot.hook('PING', lambda irc, ln: self.stop(True))
        self.bot.parse_line('PING :12345')
        assert( self.wait() )
        # assert(self.bot._handle_ping('PING :12345'))

    def test_join(self):
        # testing these together
        chan = '#testchan'
        self.fakeircd.testing_callback = self.stop
        self.bot.joinchan(chan)
        self.wait()
        assert( chan in self.fakeircd._msgs )

    def test_msg(self):
        self.fakeircd.testing_callback = self.stop
        msg = 'i am the walrus'
        self.bot.joinchan('#hello')
        self.wait()

        self.bot.sendchan('#hello', msg)
        self.wait()

        print "MSGS", self.fakeircd._msgs
        self.assertEqual(
            msg,
            self.fakeircd._msgs['#hello'][-1]
            )







