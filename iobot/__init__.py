#!/usr/bin/env python
import re
import socket

from tornado.ioloop import IOLoop
from tornado.iostream import IOStream

from plugin import CommandRegister, TextPlugin

class IrcProtoCmd(object):

    def __init__(self, actn):
        self.hooks = set()
        self.actn = actn

    def __call__(self, irc, ln):
        self.actn(irc, ln)
        for h in self.hooks:
            h(irc, ln)


renick = re.compile("^(\w*?)!")


class IrcObj(object):
    """
    tries to guess and populate something from an ircd statement
    """

    def __init__(self, line, bot):
        self.text = self.server_cmd = self.chan = self.nick = None
        self._bot = bot
        self.line = line
        self._parse_line(line)

    def _parse_line(self, line):

        if not line.startswith(":"):
            # PING most likely
            stoks = line.split()
            self.server_cmd = stoks[0].upper()
            return

        # :senor.crunchybueno.com 401 nodnc  #xx :No such nick/channel
        # :nod!~nod@crunchy.bueno.land PRIVMSG xyz :hi

        tokens = line[1:].split(":")
        if not tokens: return

        stoks = tokens[0].split()

        # find originator
        nick = renick.findall(stoks[0])
        if len(nick) == 1:
            self.nick = nick[0]
        stoks = stoks[1:] # strip off server tok

        self.server_cmd = stoks[0].upper()
        stoks = stoks[1:]

        # save off remaining tokens
        self.stoks = stoks

    def say(self, text, dest=None):
        self._bot.say(dest or self.chan, text)


class IOBot(object):

    def __init__(
            self,
            host,
            nick = 'hircules',
            port = 6667,
            owner = 'human',
            initial_chans = None,
            on_ready = None,
            ):
        """
        create an irc bot instance.
        @params
        initial_chans: None or list of strings representing channels to join
        """
        self.nick = nick
        self.chans = set() # chans we're a member of
        self.owner = owner
        self.host = host
        self.port = port
        self._plugins = dict()
        self._connected = False
        # used for parsing out nicks later, just wanted to compile it once
        # server protocol gorp
        self._irc_proto = {
            'PRIVMSG' : IrcProtoCmd(self._p_privmsg),
            'PING'    : IrcProtoCmd(self._p_ping),
            'JOIN'    : IrcProtoCmd(self._p_afterjoin),
            '401'     : IrcProtoCmd(self._p_nochan),
            }
        # build our user command list
        self.cmds = dict()

        self._initial_chans = initial_chans
        self._on_ready = on_ready

        # finally, connect.
        self._connect()

    def hook(self, cmd, hook_f):
        """
        allows easy hooking of any raw irc protocol statement.  These will be
        executed after the initial protocol parsing occurs.  Plugins can use this
        to extend their reach lower into the protocol.
        """
        assert( cmd in self._irc_proto )
        self._irc_proto[cmd].hooks.add(hook_f)

    def joinchan(self, chan):
        self._stream.write("JOIN :%s\r\n" % chan)

    def say(self, chan, msg):
        """
        sends a message to a chan or user
        """
        self._stream.write("PRIVMSG {} :{}\r\n".format(chan, msg))

    def register(self, plugin):
        """
        accepts an instance of Plugin to add to the callback chain
        """
        self._plugins[plugin.__class__] = plugin

    def _connect(self):
        _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self._stream = IOStream(_sock)
        self._stream.connect((self.host, self.port), self._after_connect)

    def _after_connect(self):
        self._stream.write("NICK %s\r\n" % self.nick)
        self._stream.write("USER %s 0 * :%s\r\n" % ("iobot", "iobot"))

        if self._initial_chans:
            for c in self._initial_chans: self.joinchan(c)
            del self._initial_chans
        if self._on_ready:
            self._on_ready()
        self._next()

    def _parse_line(self, line):
        irc = IrcObj(line, self)
        if irc.server_cmd in self._irc_proto:
            self._irc_proto[irc.server_cmd](irc, line)
        return irc

    def _p_ping(self, irc, line):
        self._stream.write("PONG %s\r\n" % line[1])

    def _p_privmsg(self, irc, line):
        # :nod!~nod@crunchy.bueno.land PRIVMSG #xx :hi
        toks = line[1:].split(':')[0].split()
        irc.chan = toks[-1] # should be last token after last :
        irc.text = line[line.find(':',1)+1:].strip()

    def _p_afterjoin(self, irc, line):
        toks = line.strip().split(':')
        if irc.nick != self.nick:
            return # we don't care right now if others join
        irc.chan = toks[-1] # should be last token after last :
        self.chans.add(irc.chan)

    def _p_nochan(self, irc, line):
        # :senor.crunchybueno.com 401 nodnc  #xx :No such nick/channel
        toks = line.strip().split(':')
        irc.chan = toks[1].strip().split()[-1]
        if irc.chan in self.chans: self.chans.remove(irc.chan)

    def _process_plugins(self, irc):
        """ parses a completed ircObj for module hooks """
        for name,plug in self._plugins.iteritems():
            plug(irc)

    def _next(self):
        # go back on the loop looking for the next line of input
        self._stream.read_until('\r\n', self._incoming)

    def _incoming(self, line):
        self._process_plugins(self._parse_line(line))
        self._next()


def main():
    ib = IOBot(
        host = 'senor.crunchybueno.com',
        nick = 'iobot',
        port = 6667,
        initial_chans = ['#33ad'],
        )

    class Echo(TextPlugin):
        def on_text(self, irc):
            irc.say(irc.text)

    ib.register(Echo())

    IOLoop.instance().start()


if __name__ == '__main__':
    main()

