from plugins import TextPlugin, UtilityMixin

class Stock(TextPlugin, UtilityMixin):
    def __repr__(self): return 'rtsq'

    def on_text(self, irc):
        data = self._get_data(irc.module_args)
        if data[1] != '0.00':
            irc.say('The current price of %s is %s, as of %s EST.  '
                    'A change of %s from the last business day.' %
                    (data[0][1:-1], data[1], data[3][1:-1], data[4]))
        else:
            s = 'I couldn\'t find a listing for %s' % symbol
            irc.say(s)

    def _get_data(self, symbol):
        url = 'http://finance.yahoo.com/d/quotes.csv?s=%s' \
              '&f=sl1d1t1c1ohgv&e=.csv' % symbol
        try:
            quote = self._requests.get(url)
        except Exception, e:
            irc.error(str(e), Raise=True)

        data = quote.text.split(',')
        return data

Plugin = Stock
