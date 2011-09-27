#!/usr/bin/env python

# very simple ircd used for testing

# ORIGINALLY:
# single-server ircd for the da-op3n contest 2008 (C) HC Esperer

# Released unter the new BSD license.


import threading
import socket

from sha import sha
from time import sleep, time
from cPickle import dumps, loads
from pprint import pformat

NETWORKNAME = "iobot testnet"
MOTD = """Welcome to the %s!""" % NETWORKNAME

MAXPINGTIMEOUT = 600.0


class IRCException(Exception):
    def __init__(self, msg, code = 461, channel = None):
        Exception.__init__(self, msg)
        self.code = code
        self.channel = channel
class HELPException(IRCException):
    def __init__(self):
        IRCException.__init__(self, "HELP")
class EOFException(Exception): pass

class SockWrap():
    def __init__(self, socket): self.s = socket
    def sendall(self, s):
        try: self.s.sendall(s.replace("\n", "\r\n"))
        except Exception, e: pass
    def recv(self, n):
        return self.s.recv(n)
    def close(self):
        try: self.s.close()
        except Exception, e: pass

class DBException(Exception): pass
class DBWrapper():
    def __init__(self, db):
        self.db = db
        self.t_lock = threading.Lock()
        self.locked = False
    def fetchall(self):
        if not self.locked: raise DBException()
        return self.db.fetchall()
    def execute(self):
        if not self.locked: raise DBException()
        return self.db.execute()
    def cursor(self):
        if not self.locked: raise DBException()
        return self.db.cursor()
    def commit(self):
        if not self.locked: raise DBException()
        return self.db.commit()
    def lock(self):
        self.t_lock.acquire_lock()
        self.locked = True
    def unlock(self):
        self.locked = False
        self.t_lock.release_lock()

class DummyUser:
    def __init__(self, nick, ID):
        self.data = {'nick': nick}
        self.IRC_ID = ID
    def TranslateMessage(self, msg):
        pts = msg[1:].split(":", 1)
        fp = pts[0].strip().split(" ")
        user = pts[0]
        user = user.split("!")
        fp[0] = user[0]
        if len(pts) > 1: return fp + pts[1:]
        return fp
    def sendto(self, to, msg, IRC_ID = None):
        if IRC_ID == None: IRC_ID = self.IRC_ID
        user = self.s.nicks[to]
        user.send(":%s NOTICE %s :%s\n" % (IRC_ID, to, msg))
    def hasflag(self, user, flag):
        try: user = self.s.nicks[user]
        except: return False
        return flag in user.flags

class LineReader:
    buf = ''
    def __init__(self, socket):
        self.s = socket
    def readline(self):
        while True:
            pos = self.buf.find("\n")
            if pos != -1:
                line, self.buf = self.buf[:pos], self.buf[pos + 1:]
                return line
            frag = self.s.recv(8192)
            if frag == None: raise EOFException()
            if len(frag) == 0: raise EOFException()
            frag = frag.replace("\r", "")
            if len(frag) == 0:
                buf, self.buf = self.buf, ''
                return buf # EOF
            self.buf = self.buf + frag
    def readlineparams(self):
        line = self.readline()
        parts = line.split(":", 1)
        sparts = parts[0].strip().split(" ")
        del parts[0]
        return sparts + parts

class IRCChannel(threading.Thread):
    CHANFLAGS = ['n', 't', 'i', 's', 'p', 'm', 'r']
    CHANMODES = ['l', 'b']
    USERMODES = ['o', 'h', 'v']

    def __init__(self, host, name):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.creationtime = int(time())
        self.host = host
        self.name = name
        self.users = {}
        self.bans = []
        self.invitees = []
        self.topic = None
        self.flags = {name: ['n', 't']}
        self.messages = []
        self.limit = 0
        self.usersjoined = False

    def __del__(self): pass

    def flagset(self, flag):
        return flag in self.flags[self.name]

    def hasflag(self, user, flag):
        if user not in self.flags: return False
        return flag in self.flags[user]

    def isinvited(self, user):
        if not self.flagset('i'): return True
        if user.data['nick'] in self.invitees: return True
        return False

    def isbanned(self, user):
        pass # TBI

    def sendall(self, msg, IRC_except = (), lock = True):
        if lock: self.lock.acquire_lock()
        try:
            for nick in self.users:
                if nick in IRC_except: continue
                user = self.users[nick]
                user.send(msg)
        finally:
            if lock: self.lock.release_lock()

    def settopic(self, user, newtopic, replace = True):
        if (not replace) and (self.topic != None): return
        self.topic = (newtopic, user.IRC_ID, int(time()))
        self.sendall(":%s TOPIC %s :%s\n" % (user.IRC_ID, self.name, newtopic))

    def invite(self, invitor, invitee):
        self.lock.acquire_lock()
        try:
            if invitee.data['nick'] in self.users: raise IRCException("User is already joined")
            self.invitees.append(invitee.data['nick'])
            msg = ":%s INVITE %s %s\n" % (invitor.IRC_ID, invitee.data['nick'], self.name)
            invitee.send(msg)
        finally: self.lock.release_lock()

    def add(self, user):
        self.lock.acquire_lock()
        try:
            if user.data['nick'] in self.users: raise IRCException("You are already on that channel")
            if user.data['nick'] in self.invitees:
                iID = self.invitees.index(user.data['nick'])
                del self.invitees[iID]
            msg = ":%s JOIN :%s\n" % (user.IRC_ID, self.name)
            self.sendall(msg, (), False)
            user.send(msg)
            self.users[user.data['nick']] = user
            self.flags[user.data['nick']] = []
            if not self.usersjoined:
                self.usersjoined = True
                self.flags[user.data['nick']].append('o')
                # self.setmode(CHANSERV, "+o %s" % user.data['nick'], False)
                self.sendall(":%s MODE %s %s\n" % (self.host, self.name, self.getmodes()), (), False)

        finally: self.lock.release_lock()

    def remove(self, user, inform = True, reason = ''):
        self.lock.acquire_lock()
        try:
            if user.data['nick'] not in self.users: raise IRCException("Not joined")
            del self.users[user.data['nick']]
            del self.flags[user.data['nick']]
            if inform:
                msg = ":%s PART %s :%s\n" % (user.IRC_ID, self.name, reason)
                self.sendall(msg, (), False)
                user.send(msg)
        finally: self.lock.release_lock()

    def ison(self, user):
        return user.data['nick'] in self.users

    def who(self):
        return [(user, (user.data['nick'] in self.flags) and ('o' in self.flags[user])) for user in self.users]

    def isempty(self): return len(self.users) == 0

    def getmodes(self):
        modes = "+" + ''.join(self.flags[self.name])
        if self.limit != 0: modes = modes + "l %d" % self.limit
        if len(modes) == 1: modes = ''
        return modes

    def kick(self, user, victim, reason):
        msg = ":%s KICK %s %s :%s\n" % (user.IRC_ID, self.name, victim, reason)
        try: user = self.users[victim]
        except: raise IRCException("Not in channel")
        self.remove(user, False)
        self.sendall(msg)
        user.send(msg)

    def setmode(self, user, mode, lock = True):
        if lock: self.lock.acquire_lock()
        try:
            parms = mode.split(" ")
            mode = parms[0]
            m = None
            ppos = 1
            for char in mode:
                if char in '+-': m = char
                else:
                    if m == None: raise IRCException("Illegal mode")
                    if char in self.CHANFLAGS:
                        if m == '+':
                            if not char in self.flags[self.name]:
                                self.flags[self.name].append(char)
                                self.sendall(":%s MODE %s +%s\n" % (user.IRC_ID, self.name, char), (), False)
                        else:
                            if char in self.flags[self.name]:
                                del self.flags[self.name][self.flags[self.name].index(char)]
                                self.sendall(":%s MODE %s -%s\n" % (user.IRC_ID, self.name, char), (), False)
                    elif char in self.CHANMODES:
                        if char == 'l':
                            if m == '+':
                                if len(parms) < (ppos + 1): raise IRCException("Not enough parameters")
                                try: self.limit = int(parms[ppos])
                                except: raise IRCException("Parameter %d must be an integer" % ppos + 1)
                                self.sendall(":%s MODE %s +%s %d\n" % (user.IRC_ID, self.name, char, self.limit), (), False)
                                ppos = ppos + 1
                            else:
                                self.limit = 0
                                self.sendall(":%s MODE %s -%s\n" % (user.IRC_ID, self.name, char), (), False)
                        elif char == 'b':
                            if len(parms) < (ppos + 1): raise IRCException("Not enough parameters")
                            banhost = parms[ppos]
                            ppos = ppos + 1
                            if m == '+':
                                if banhost not in self.bans:
                                    self.bans.append(banhost)
                                    self.sendall(":%s MODE %s +%s %s\n" % (user.IRC_ID, self.name, char, banhost), (), False)
                            elif m == '-':
                                if banhost in self.bans:
                                    banID = self.bans.index(banhost)
                                    del self.bans[banID]
                                    self.sendall(":%s MODE %s -%s %s\n" % (user.IRC_ID, self.name, char, banhost), (), False)

                    elif char in self.USERMODES:
                        if len(parms) < (ppos + 1): raise IRCException("Not enough parameters")
                        usr = parms[ppos]
                        ppos = ppos + 1
                        if not usr in self.flags: raise IRCException("User not in channel")
                        if m == '+':
                            if not char in self.flags[usr]:
                                self.sendall(":%s MODE %s +%s %s\n" % (user.IRC_ID, self.name, char, usr), (), False)
                                self.flags[usr].append(char)
                        else:
                            if char in self.flags[usr]:
                                del self.flags[usr][self.flags[usr].index(char)]
                                self.sendall(":%s MODE %s -%s %s\n" % (user.IRC_ID, self.name, char, usr), (), False)
        finally:
            if lock: self.lock.release_lock()


class IRCHandler(threading.Thread):
    def __init__(self, socket, addrinfo, server, host, channels, nicks):
        threading.Thread.__init__(self)
        self.server = server
        self.s = socket
        self.reader = LineReader(socket)
        self.addrinfo = addrinfo
        self.host = host
        self.IRC_hasquit = False
        self.data = {}
        self.flags = ['i']
        self.channels = channels
        self.nicks = nicks

    def __del__(self):
        try: self.s.close()
        except Exception, e: pass

    def IRC_nick(self, (nick,)):
        """1"""
        self.server.lock.acquire_lock()
        try:
            if 'initialized' in self.data:
                raise IRCException("Already registered; can't change nick")
            nick = nick.replace(" ", "_")
            if nick.lower() in self.nicks:
                self.data['wanted_nick'] = nick
                raise IRCException("That nick is already in use", 433)
            self.data['nick'] = nick
        finally: self.server.lock.release_lock()

    def IRC_user(self, (user, host, server, real)):
        """4"""
        if 'data' in self.data: return
        self.data['user'] = (user, host, server, real)

    def IRC_ping(self, (host,)):
        """1"""
        self.s.sendall(':%s PONG %s :%s\n' % (self.host, self.host, host))

    def IRC_pong(self, (host,)):
        """a"""
        pass

    def IRC_quit(self, (reason,)):
        """0-1"""
        if reason == None: reason = ''
        self.do_quit(reason)

    def IRC_whois(self, (who,)):
        """1"""
        self.s.sendall(':%s 318 %s %s :End of /WHOIS list\n' % (self.host, self.data['nick'], who))

    def IRC_away(self, (reason,)):
        """0-1"""
        if reason != None and reason.strip() == '': reason = None # hack
        if reason == None:
            try: del self.data['away']
            except: pass
            self.s.sendall(":%s 305 %s :OK, you're back. Did you get laid while you were gone?\n" % (self.host, self.data['nick']))
        else:
            self.data['away'] = reason
            self.s.sendall(":%s 306 %s :OK, you're /away now. Hurry the fuck back!\n" % (self.host, self.data['nick']))

    def IRC_list(self, (mask,)):
        """0-1"""
        self.s.sendall(':%s 321 %s Channel :Users Name\n' % (self.host, self.data['nick']))
        for cn in self.channels:
            channel = self.channels[cn]
            if 's' not in channel.flags[cn]: self.s.sendall(':%s 322 %s %s %d :%s\n' % (self.host, self.data['nick'], cn, len(channel.users), channel.topic[0] if channel.topic != None else ''))
        self.s.sendall(':%s 323 %s :End of /LIST\n' % (self.host, self.data['nick']))

    def do_quit(self, reason):
        self.server.lock.acquire_lock()
        try:
            self.s.sendall("ERROR :Closing link: %s (%s)\n" % (self.addrinfo[0], reason))
            self.IRC_hasquit = True
            self.s.close()
            for chan in self.channels:
                try: channel = self.channels[chan]
                except: continue
                try: channel.remove(self, True, reason)
                except: pass
                self.server.chanserv.event_part(self, channel)
                if channel.isempty(): del self.channels[chan]
        finally: self.server.lock.release_lock()

    def IRC_pass(self, (passwd,)):
        """1"""
        if 'initialized' in self.data: self.s.sendall(":%s 462 %s :You may not reregister\n" % (self.host, self.data['nick']))

    def IRC_oper(self, (nick, passwd)):
        """2"""
        if nick == 'root' and passwd == 'reindeerflotilla':
            self.setmode('o')

    def IRC_who(self, (chan,)):
        """1"""
        if chan not in self.channels: raise IRCException("No such channel")
        chan = self.channels[chan]
        uoc = chan.ison(self)
        for nick in chan.users:
            if not uoc:
                if 'i' in self.flags:
                    continue
            user = chan.users[nick]
            u_user, u_host, u_server, u_real = user.data['user']
            if chan.hasflag(nick, 'o'): u_type = '@'
            elif chan.hasflag(nick, 'h'): u_type = '%'
            elif chan.hasflag(nick, 'v'): u_type = 'v'
            else: u_type = ''
            u_type = 'H' + u_type # avail
            self.s.sendall(":%s 352 %s %s ~%s %s %s %s %s :0 %s\n" % (self.host, self.data['nick'], chan.name, u_user, u_host, self.host, nick, u_type, u_real))
        self.s.sendall(":%s 315 %s %s :End of /WHO list\n" % (self.host, self.data['nick'], chan.name))

    def IRC_join(self, (chans,), force=False):
        """1--1"""
        if chans == None: chans = ''
        for chan in chans.split(","):
            chan = chan.strip()
            if len(chan) < 1: chan = '_' # hack
            if (chan[0] != '#') or (len(chan.split(" ")) != 1):
                chan = chan.split(' ')[0]
                if not self.hasmode('e'): raise IRCException("I don't think so, dude", 480, chan)
            try:
                self.server.lock.acquire_lock()
                try: c = self.channels[chan]
                except:
                    c = IRCChannel(self.host, chan)
                    self.channels[chan] = c
                    c.start()
            finally: self.server.lock.release_lock()
            if not force:
                if not c.isinvited(self): raise IRCException("You must be invited to join", 480, chan)
                if c.isbanned(self): raise IRCException("You have been banned from this channel", 480, chan)
                if c.flagset('r'):
                    if not self.hasmode('e'): raise IRCException("You must be identified with nickserv to join", 480, chan)
            c.add(self)
            nicklist = []
            for nick in c.users:
                if c.hasflag(nick, 'o'): status = '@'
                elif c.hasflag(nick, 'h'): status = '%'
                elif c.hasflag(nick, 'v'): status = '+'
                else: status = ''
                nicklist.append(status + nick)
            nicklist = " ".join(nicklist)
            if c.topic != None:
                topic, topicsetter, topicset = c.topic
                self.s.sendall(":%s 332 %s %s :%s\n" % (self.host, self.data['nick'], chan, topic))
                self.s.sendall(":%s 333 %s %s %s %s\n" % (self.host, self.data['nick'], chan, topicsetter, topicset))
            self.s.sendall(":%s 353 %s = %s :%s\n" % (self.host, self.data['nick'], chan, nicklist))
            self.s.sendall(":%s 366 %s %s :%s\n" % (self.host, self.data['nick'], chan, "End of /NAMES list"))
            self.server.chanserv.event_join(self, c)

    def IRC_topic(self, (chan, topic)):
        """2"""
        try: c = self.channels[chan]
        except: raise IRCException("No such channel")
        if not c.ison(self): raise IRCException("You're not on that channel")
        if (not c.hasflag(self.data['nick'], 'o')) and (not c.hasflag(self.data['nick'], 'h')):
            raise IRCException("Hey, who do you think you are?", 482, chan)
        c.settopic(self, topic)

    def IRC_kick(self, (chan, user, reason)):
        """3"""
        try: c = self.channels[chan]
        except: raise IRCException("No such channel")
        if not c.ison(self): raise IRCException("You're not on that channel")
        if (not c.hasflag(self.data['nick'], 'o')) and (not c.hasflag(self.data['nick'], 'h')):
            raise IRCException("You behave like a professional. That's an order.", 482, chan)
        if self.data['nick'] == user: raise IRCException("I will not allow you to kick yourself", 482, chan)
        c.kick(self, user, reason)
        self.server.chanserv.event_part(self.nicks[user], c)

    def IRC_part(self, (chans, reason)):
        """1-2"""
        if reason == None: reason = ''
        for chan in chans.split(","):
            chan = chan.strip()
            try: c = self.channels[chan]
            except: continue
            c.remove(self, True, reason)
            self.server.chanserv.event_part(self, c)
            try:
                self.server.lock.acquire_lock()
                if c.isempty(): del self.channels[chan]
            finally: self.server.lock.release_lock()

    def IRC_invite(self, (user, chan)):
        """2"""
        try: c = self.channels[chan]
        except: raise IRCException("No such channel")
        if not c.ison(self): raise IRCException("You're not on that channel")
        if (not c.hasflag(self.data['nick'], 'o')) and (not c.hasflag(self.data['nick'], 'h')):
            raise IRCException("You can't do that thing, when you don't have that swing")
        try: user = self.nicks[user]
        except: raise IRCException("No such user")
        c.invite(self, user)

    def IRC_mode(self, (mode,)):
        """a"""
        parms = mode.split(" ")
        mode = parms[0]
        if len(parms) > 1: parms = " ".join(parms[1:])
        else: parms = None
        if mode[0] == '#':
            try: c = self.channels[mode]
            except: raise IRCException("No such channel")
            if not c.ison(self): raise IRCException("You're not on that channel")
            if parms == None:
                self.s.sendall(":%s 324 %s %s %s\n" % (self.host, self.data['nick'], mode, c.getmodes()))
                self.s.sendall(":%s 329 %s %s %d\n" % (self.host, self.data['nick'], mode, c.creationtime))
            elif parms == 'b': # hack
                self.s.sendall(":%s 368 %s %s :End of Channel Ban List\n" % (self.host, self.data['nick'], mode))
            else:
                if not c.hasflag(self.data['nick'], 'o'): raise IRCException("You can't do that think when you don't have that swing (you're not channel operator)", 482, mode)
                try: c.setmode(self, parms)
                except IRCException, e: self.s.sendall(":%s 403 %s %s :%s\n" % (self.host, self.data['nick'], mode, e))

    def IRC_privmsg(self, (dest, msg), type="PRIVMSG"):
        """2"""
        if dest[0] == '#':
            try: c = self.channels[dest]
            except: raise IRCException("No such channel")
            if not c.ison(self):
                if c.flagset('n'): raise IRCException("You're not on that channel and +n is set")
            if c.flagset('m'):
                if (not c.hasflag(self.data['nick'], 'o')) and (not c.hasflag(self.data['nick'], 'h')) and (not c.hasflag(self.data['nick'], 'v')):
                    return
            c.sendall(":%s %s %s :%s\n" % (self.IRC_ID, type, c.name, msg), (self.data['nick'],))
        elif dest[0].isalpha():
            try: c = self.nicks[dest.lower()]
            except: raise IRCException("No such user")
            c.send(":%s %s %s :%s\n" % (self.IRC_ID, type, dest, msg))

    def IRC_notice(self, parms):
        """2"""
        self.IRC_privmsg(parms, 'NOTICE')

    def hasmode(self, mode): return mode in self.flags
    def setmode(self, mode, remove = False, instigator = None):
        if remove:
            try: fID = self.flags.index(mode)
            except: return
            del self.flags[fID]
        else:
            try:
                self.flags.index(mode)
                return
            except: pass
            self.flags.append(mode)
        if instigator == None: instigator = self.host
        else: instigator = instigator.IRC_ID
        self.s.sendall(":%s MODE %s %s%s\n" % (instigator, self.data['nick'], {False: '-', True: '+'}[not remove], mode))

    def send(self, msg):
        self.s.sendall(msg)

    def run(self):
        s = self.s
        s.sendall(":%s NOTICE AUTH :***Welcome to HC's IRC server; please wait...\n" % self.host)
        s.sendall(":%s NOTICE AUTH :***Please register now.\n" % self.host)
        s.sendall("PING :12345\n")
        functions = self.__class__.__dict__
        lastrecv = 0
        while True:
            try:
                line = self.reader.readlineparams()
                lastrecv = int(time())
            except socket.timeout, t:
                if (int(time()) - lastrecv) > int(MAXPINGTIMEOUT):
                    self.do_quit('Ping timeout')
                    break
                self.s.sendall('PING :%d\n' % int(time()))
                continue
            except Exception, e:
                try: self.do_quit('Read error')
                except Exception, e: pass
                break
            if len(line[0]) < 1: continue
            cmd = "IRC_" + line[0].lower()
            if not cmd in functions:
                if 'nick' in self.data:
                    user = self.data['nick']
                    s.sendall(":%s 421 a %s :Unknown command\n" % (self.host, user))
                continue

            if 'initialized' not in self.data:
                if not cmd[4:] in ['user', 'pass', 'nick', 'ping', 'pong']:
                    s.sendall(":%s 421 a %s :Unknown command\n" % (self.host, '*'))
                    continue
            command = functions[cmd]
            parmtypes = command.__doc__.split("\n")[0]
            try:
                if parmtypes == 'a':
                    command.__call__(self, (" ".join(line[1:]),))
                else:
                    parmtypes = parmtypes.split("-", 1)
                    parms = int(parmtypes[0])
                    if len(parmtypes) == 1: maxparms = parms
                    else: maxparms = int(parmtypes[1])
                    if (len(line) < (parms + 1)) or ((maxparms != -1) and (len(line) > (maxparms + 1))):
                        if 'nick' in self.data:
                            user = self.data['nick']
                            what = {True: 'Not enough', False: 'Too many'}[len(line) < (parms + 1)]
                            s.sendall(":%s 461 %s %s :%s parameters\n" % (self.host, user, cmd[4:].upper(), what))
                        continue
                    if maxparms != -1:
                        for i in range(maxparms - len(line) + 1): line.append(None)
                    else: line = line[0:parms + 1]
                    command.__call__(self, tuple(line[1:]))
            except IRCException, e:
                if 'nick' in self.data:
                    if e.code in [482, 433, 480]:
                        s.sendall(":%s %d %s %s :%s\n" % (self.host, e.code, self.data['nick'], e.channel, e))
                    else:
                        s.sendall(":%s 461 %s %s :%s\n" % (self.host, self.data['nick'], cmd[4:].upper(), e))
                else: s.sendall(":%s %d * %s :%s\n" % (self.host, e.code, self.data['wanted_nick'], e))


            if self.IRC_hasquit: break
            if 'initialized' not in self.data:
                if ('user' in self.data) and ('nick' in self.data):
                    self.nicks[self.data['nick'].lower()] = self
                    self.IRC_ID = "%s!~%s@%s" % (self.data['nick'], self.data['user'][0], self.addrinfo[0])
                    s.sendall(":%s 001 %s :Hiho und Guten Tag! Welcome!\n" % (self.host, self.data['nick']))
                    s.sendall(":%s 002 %s :You are %s\n" % (self.host, self.data['nick'], self.IRC_ID))
                    for line in MOTD.split("\n"): s.sendall(":%s 372 %s :%s \n" % (self.host, self.data['nick'], line))
                    s.sendall(":%s 376 %s :End of /MOTD command.\n" % (self.host, self.data['nick']))
                    s.sendall(":%s MODE %s +i\n" % (self.host, self.data['nick']))
                    self.data['mode'] = ['i']
                    self.data['initialized'] = True
        if not self.IRC_hasquit: self.do_quit("Timeout")
        try: del self.server.nicks[self.data['nick']]
        except Exception, e: pass
        print "Connection to %s closed." % self.addrinfo[0]

class IRCServer:
    backlog = 5
    def __init__(self, address, host):
        self.lock = threading.Lock()
        self.clients = {}
        self.channels = {}
        self.nicks = {}
        self.host = host
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind(address)

    def __del__(self):
        try: self.s.close()
        except Exception, e: pass

    def run(self):
        self.s.listen(self.backlog)
        try:
            while True:
                s, a = self.s.accept()
                s.settimeout(MAXPINGTIMEOUT / 3.0)
                addr = a[0]
                if addr in self.clients: t = self.clients[addr]
                else:
                    t = []
                    self.clients[addr] = t
                handler = IRCHandler(SockWrap(s), a, self, self.host, self.channels, self.nicks)
                self.lock.acquire_lock()
                t.append(handler)
                self.lock.release_lock()
                handler.start()
        except KeyboardInterrupt: print "KeybordInterrupt"
        finally:
            print "Closing server socket..."
            self.s.close()

if __name__ == '__main__':
    port = 6667
    host = "iobot.testnet"
    while True:
        print "Trying port %d\r" % port
        try:
            s = IRCServer(('0.0.0.0', port), host)
            break
        except Exception, e:
            print e
            from time import sleep
            sleep(10)
    print "\nListening on port %d" % port
    s.run()
