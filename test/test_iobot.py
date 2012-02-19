
import socket, threading, time, unittest
from random import randint

import mock, nose
from tornado.ioloop import IOLoop
from tornado.testing import AsyncTestCase

import sys, os.path
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))

from iobot import IOBot, Plugin

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


def patched_connect(self):
    """
    bypasses _connect on the object since we don't feel like patching all of
    socket.socket and IOStream, we're just going to fake those.
    """
    self._stream = mock.MagicMock()
    self._after_connect()


class BotTestCases(AsyncTestCase):

    """
    i really wrestled with mocking IOStream.read_until and then i could call
    bot._next() and have it do the right thing.  The problem is you end up in a
    weird looping blocking situation.

    It's just easier (not cleaner) to call bot._incoming(...) with the expected
    input from the ircd and then let the parsing take over from there.  It
    reduces code coverage slightly, but the methods not exposed to tests are
    fairly limited and specific in their scope.
    """

    def ircin(self, stat, txt):
        self.bot._incoming(':faker.irc {} :{}\r\n'.format(stat, txt))

    def rawircin(self, txt):
        self.bot._incoming(txt)

    @mock.patch('iobot.IOBot._connect', patched_connect)
    def setUp(self):
        super(BotTestCases, self).setUp()
        self.bot = IOBot(
                    nick = 'testie',
                    host = 'localhost',
                    port = 6667,
                    )
        assert self.bot._stream.write.called

    def test_ping(self):
        # going to fake a PING from the server on this one
        self._was_pinged = False
        self.bot.hook('PING', lambda irc, ln: self.stop(True))
        self.rawircin('PING :12345')
        assert self.wait()
        assert self.bot._stream.write.called

    def test_join(self):
        # testing these together
        chan = '#testchan'
        self.bot.joinchan(chan)
        assert self.bot._stream.write.called_with("JOIN :{}".format(chan))

    def test_parse_join(self):
        chan = '#testchan'
        # fake irc response to our join
        self.rawircin(
            ':{}!~{}@localhost JOIN :{}\r\n'.format(
                self.bot.nick,
                self.bot.nick,
                chan
                )
            )
        assert chan in self.bot.chans

    def test_msg(self):
        chan, msg = "#hi", "i am the walrus"
        self.bot.say(chan, msg)
        assert self.bot._stream.write.called


        self.bot._stream.write.assert_called_with(
                "PRIVMSG {} :{}\r\n".format(chan, msg)
                )

    def test_parse_msg_to_unjoined(self):
        chan = "#hi"
        self.bot.chans.add(chan) # fake join msg
        # :senor.crunchybueno.com 401 nodnc  #xx :No such nick/channel
        self.ircin(
            "401 {} {}".format(self.bot.nick, chan),
            "No such nick/channel"
            )
        assert chan not in self.bot.chans

    def test_plugin_echo(self):

        class Echo(Plugin):
            def on_content(self, irc):
                irc.say(irc.content)
        self.bot.register(Echo())

        # :nod!~nod@crunchy.bueno.land PRIVMSG #xx :hi
        self.ircin("PRIVMSG #xx", "hi")

        print "MOCK", self.bot._stream.write.call_args_list
        self.bot._stream.write.assert_called_with(
                "PRIVMSG {} :{}\r\n".format("#xx", "hi")
                )



