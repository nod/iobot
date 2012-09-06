from iobot.plugins import TextPlugin
from iobot.plugins.decorators import plugin_command

class Echo(TextPlugin):

    @plugin_command
    def echo(self, irc):
        irc.say("%s" % irc.command_args)

Plugin = Echo
