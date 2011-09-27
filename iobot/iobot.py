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


class IOBot(object):

    def __init__(self, nick, host, port=6667, owner='iobot'):

        self.nick = nick
        self.chans = set()
        self.owner = owner
        self.host = host
        self.port = port

        self._connected = False

        self._connect()

        # used for parsing out nicks later, just wanted to compile it once
        self._rnick = re.compile("^:(\w*?)!")
        # build our command list
        self.cmds = { }

    def joinchan(self, chan, callback=None):
        self._stream.write("JOIN :%s\r\n" % chan, callback=callback)
        self.chans.add(chan)

    def sendchan(self, chan, msg):
        if self._connected:
            self._stream.write("PRIVMSG %s :%s\r\n" % (chan, msg))

    def _connect(self):
        _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        stream = self._stream = IOStream(_sock)
        stream.connect((self.host, self.port), self._initial_connect)

    def _initial_connect(self):
        # send our initial mess
        self._connected = True
        self._stream.write("NICK %s\r\n" % self.nick)
        self._stream.write("USER %s %s bla :%s\r\n" % (IDENT, HOST, REALNAME))
        self._next()

    def parse_line(self,line):
        tokens = line.split(":")
        if ( len(tokens) < 3 or
                "PRIVMSG" not in tokens[1] ):
            return None, None, None
        # try to get the nick
        nick = self._rnick.findall(line)
        if len(nick) == 1: return tokens[1], nick[0], ' '.join(tokens[2:])
        else: return None, None, ' '.join(tokens[2:])


    def _handle_ping(self,line):
        if line.startswith("PING"):
            self._stream.write("PONG %s\r\n" % line[1])
            return True
        else: return False


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


    def _next(self):
        # go back on the loop looking for the next line of input
        self._stream.read_until('\r\n', self._incoming)


    def _incoming(self, line):
        print line,
        if self._handle_ping(line): return self._next()
        mask,nick,msg = self.parse_line(line)
        toks = msg.split() if msg else False
        if toks:
            cmd = toks[0].strip()
            c = self.getcmd(cmd)
            print "cmd", nick, msg, c
            if c: c(nick, toks[1:])
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
        host='127.0.0.1',
        port=(int(sys.argv[3] if len(sys.argv)==4 else PORT))
        )
    ib.joinchan(cc)
    IOLoop.instance().start()


if __name__ == '__main__':
    main()

