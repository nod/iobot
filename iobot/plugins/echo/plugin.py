from plugins import TextPlugin
from plugins.decorators import plugin_command

class Echo(TextPlugin):

    @plugin_command
    def echo(self, irc):
        irc.say("%s" % irc.command_args)

Plugin = Echo
