from plugins import TextPlugin

class Echo(TextPlugin):
    def __repr__(self): return 'echo'

    def on_text(self, irc):
        irc.say("%s" % irc.module_args)


Plugin = Echo
