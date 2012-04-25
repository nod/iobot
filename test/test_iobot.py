
import sys, os.path
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))

from unittest import TestCase

import mock
from tornado.testing import AsyncTestCase

from iobot import IOBot, CommandRegister, TextPlugin

def _patched_connect(self):
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

    @mock.patch('iobot.IOBot._connect', _patched_connect)
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
        class Echo(TextPlugin):
            def on_text(self, irc):
                irc.say(irc.text)
        self.bot.register(Echo())

        # :nod!~nod@crunchy.bueno.land PRIVMSG #xx :hi
        self.ircin("PRIVMSG #xx", "hi")

        self.bot._stream.write.assert_called_with(
                "PRIVMSG {} :{}\r\n".format("#xx", "hi")
                )

class CommandRegisterTests(TestCase):

    def test_instance(self):
        c = CommandRegister()
        assert c is CommandRegister() is not CommandRegister

    def test_register_and_exec(self):

        class Tester(TextPlugin):
            def __init__(self):
                self.register('go', self.go)
            def go(self, irc):
                return 23

        Tester()

        # confirms command registration
        assert 'go' in CommandRegister()
        assert 'went' not in CommandRegister()

        # now text execution
        assert 23 == CommandRegister().cmdexec('go', None)

