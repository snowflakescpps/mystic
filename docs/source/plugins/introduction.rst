Plugins: An introduction
========================

Plugins provide a neat way to extend Mystic's functionality. Here is an example!


.. code-block:: python

    from mystic import handlers
    from mystic.handlers import XTPacket

    from mystic.plugins import IPlugin
    from mystic import commands

    from mystic import permissions

    class Example(IPlugin):
        author = "Ben"
        description = "Example plugin for developers"
        version = "1.0.0"

        def __init__(self, server):
            super().__init__(server)

        async def ready(self):
            self.server.logger.info('Example.ready()')
            await self.server.permissions.insert(name='mystic.ping')

        async def message_cooling(self, p):
            print(f'{p}, Message was sent during cooldown')

        @handlers.handler(XTPacket('m', 'sm'))
        @handlers.cooldown(1, callback=message_cooling)
        async def handle_send_message(self, p, penguin_id: int, message: str):
            print(f'Do stuff with {message}')

        @commands.command('ping')
        @permissions.has('mystic.ping')
        async def ping(self, p):
            await p.send_xt('cprompt', 'Pong')

        @commands.command('ac')
        async def add_coins(self, p, amount: int = 100):
            await p.add_coins(amount, stay=True)

This page is a WIP!