from plugins import TextPlugin, UtilityMixin
from plugins.decorators import plugin_command

class Stock(TextPlugin, UtilityMixin):

    @plugin_command
    def rtsq(self, irc):
        data = self._get_data(irc.command_args)
        if data[1] != '0.00':
            irc.say('The current price of %s is %s, as of %s EST.  '
                    'A change of %s from the last business day.' %
                    (data[0][1:-1], data[1], data[3][1:-1], data[4]))
        else:
            s = 'I couldn\'t find a listing for %s' % symbol
            irc.say(s)

    @plugin_command
    def howmany(self, irc):
        """<company symbol>  <amount to spend>

        Will tell you how many shares you can purchase for a given amount if
        bought at the current (delayed) price.  Assumes a flat $7 trade cost.
        """
        from math import floor
        symbol, amount = irc.command_args.split()
        tradecosts = 7  # scottrade is $7
        amount = float(amount)
        data = self._get_data(symbol)
        price = float(data[1])
        num =  int(floor( (amount-tradecosts)/price))
        tradecosts = 14.0 / num
        breakevenprice = price + tradecosts
        irc.say("At curr price of %4.2f for %s, "
            "with %4.2f you can purchase %d shares"
            " with a breakeven price of %4.2f." % (
            price, symbol, amount, num,breakevenprice ) )

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
