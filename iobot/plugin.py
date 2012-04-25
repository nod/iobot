
class IrcCommandException(Exception):
    """ base class for irc commands """


class CommandRegister(object):
    """ singleton providing directory of, and access to, all irc commands """

    _instance = None
    _cmds = dict()

    def __new__(cls, *args, **kwargs):
        """ gaurantees a singleton instance of the register """
        if not cls._instance:
            cls._instance = super(CommandRegister, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __contains__(self, cmd):
        return cmd.lower() in self._cmds

    def register(self, name, f):
        """
        register a new irc command

        FIXME: ??? right now, commands can overwrite other commands depending on
               order added
        """
        self._cmds[name.lower()] = f

    def cmdexec(self, cmd, irc):
        c = self._cmds.get(cmd.lower(), None)
        if not c:
            raise CommandException('not implemented: {}'.format(cmd))
        return c(irc)


class BasePlugin(object):

    def register(self, cmd, f):
        CommandRegister().register(cmd, f)


class TextPlugin(BasePlugin):

    def __call__(self, irc):
        if irc.text: self.on_text(irc)

    def on_text(self, irc):
        pass





