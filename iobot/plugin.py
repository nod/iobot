class Plugin(object):

    def __call__(self, irc):
        if irc.text: self.on_text(irc)

    def on_text(self, irc):
        pass


