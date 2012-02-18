#!/usr/bin/env python
import re
import socket
import string
import StringIO
import sys
from random import shuffle, randint, sample
from os import uname

from tornado.ioloop import IOLoop
from tornado.iostream import IOStream


HOST,PORT = "127.0.0.1", 6667
NICK,IDENT,REALNAME = "b0t", "b0ttle", "b0ttle"
CHAN = "#b0t"
CMDCHAR = "."
OWNER = "nod"


def irc_cmd(func, cmd=None):
    """
    decorator for methods to be exposed as irc commands

    The following:
        class Plugin(BotPlugin):
            @irc_cmd
            def blah(self):
                pass
    will result in a new irc commend of 'blah'.

    Can also be used to decorate an existing method and rename the command.
        class Plugin(BotPlugin):
            def blah(self):
                pass
            irc_cmd(blah, 'foo')
    The above would result in a new irc command, 'foo'.
    """
    if not hasattr(func, 'irc_cmd'): func.irc_cmd = set()
    func.irc_cmd.add(cmd or func.func_name)
    return func


class BotPlugin(object):

    def __init__(self, bot):
        self.bot = bot


class IrcProtoCmd(object):
    def __init__(self, actn):
        self.hooks = set()
        self.actn = actn

    def __call__(self, irc, ln):
        self.actn(irc, ln)
        for h in self.hooks: h(irc, ln)


renick = re.compile("^(\w*?)!")

class IrcObj(object):
    """
    tries to guess and populate something from an ircd statement
    """

    __slots__ = ('stoks', 'server_cmd', 'nick', 'line', 'chan',)

    def __init__(self, line):
        # seed our members with None
        for s in self.__slots__: setattr(self, s, None)

        # save off the raw line
        self.line = line

        if not line.startswith(":"):
            # PING probably
            stoks = line.split()
            self.server_cmd = stoks[0].upper()
        else:
            tokens = line[1:].split(":")
            if not tokens: return
            stoks = tokens[0].split()

            # find originator
            nick = renick.findall(stoks[0])
            if len(nick) == 1:
                self.nick = nick[0]
                stoks = stoks[1:]

            self.server_cmd = stoks[0].upper()
            stoks = stoks[1:]

            # save off remaining tokens
            self.stoks = stoks

    def __unicode__(self):
        return ' :: '.join(
            '{}:{}'.format(s,getattr(self,s)) for s in self.__slots__
            )

    def __repr__(self):
        return self.__unicode__()


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
        self._connected = False
        # used for parsing out nicks later, just wanted to compile it once
        # server protocol gorp
        self._irc_proto = dict(
            PRIVMSG = IrcProtoCmd(self._p_privmsg),
            PING = IrcProtoCmd(self._p_ping),
            JOIN = IrcProtoCmd(self._p_afterjoin),
            )
        # build our user command list
        self.cmds = dict()

        self._initial_chans = initial_chans
        self._on_ready = on_ready

        # finally, connect.
        self._connect()

    def hook(self, cmd, hook_f):
        assert( cmd in self._irc_proto )
        self._irc_proto[cmd].hooks.add(hook_f)

    def joinchan(self, chan):
        self._stream.write("JOIN :%s\r\n" % chan)

    def sendchan(self, chan, msg):
        s =  "PRIVMSG {} :{}\r\n".format(chan, msg)
        print "sendchan", s
        self._stream.write(s)

    def _connect(self):
        _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self._stream = IOStream(_sock)
        self._stream.connect((self.host, self.port), self._after_connect)
        print "_stream.connect"

    def _after_connect(self):
        print "_after_connect"
        self._stream.write("NICK %s\r\n" % self.nick)
        self._stream.write("USER %s 0 * :%s\r\n" % (IDENT, REALNAME))

        if self._initial_chans:
            for c in self._initial_chans: self.joinchan(c)
            del self._initial_chans
        if self._on_ready:
            print "calling _on_ready"
            self._on_ready()
        self._next()

    def parse_line(self, line):
        irc = IrcObj(line)
        if irc.server_cmd in self._irc_proto:
            self._irc_proto[irc.server_cmd](irc, line)
        return irc

    def _p_ping(self, irc, line):
        self._stream.write("PONG %s\r\n" % line[1])

    def _p_privmsg(self, irc, line):
        nick = renick.findall(line)
        print "privmsg recvd:", line
        if len(nick) == 1: return tokens[1], nick[0], ' '.join(tokens[2:])

    def _p_afterjoin(self, irc, line):
        toks = line.strip().split(':')
        if irc.nick != self.nick:
            return # we don't care right now if others join
        irc.chan = toks[-1] # should be last token after last :
        self.chans.add(irc.chan)

    def getcmd(self,cmd):
        if CMDCHAR and not cmd.startswith(CMDCHAR): return None
        c = cmd[len(CMDCHAR):]
        # first look for the exact command
        if self.cmds.has_key(c): return self.cmds[c]
        # then look for any uniq commands
        tmpcmds = [k for k in self.cmds.keys() if k.startswith(c)]
        if len(tmpcmds) == 1: return self.cmds[tmpcmds[0]]
        # finally, just fail
        return None

    def _hooks(self, irco):
        """
        parses a completed ircObj for module hooks
        """

    def _next(self):
        # go back on the loop looking for the next line of input
        self._stream.read_until('\r\n', self._incoming)

    def _incoming(self, line):
        print "_incoming:", line
        self._hooks(self.parse_line(line))
        self._next()


def main():
    import sys
    if len(sys.argv) < 3:
        print "usage: bot <nick> <chan>"
        raise SystemExit
    nn = sys.argv[1]
    cc = sys.argv[2]
    ib = IOBot(
        nn,
        host = '127.0.0.1',
        port = (int(sys.argv[3] if len(sys.argv)==4 else PORT)),
        initial_chans = [cc],
        )
    IOLoop.instance().start()


if __name__ == '__main__':
    main()
