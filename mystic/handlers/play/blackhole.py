from mystic import handlers
from mystic.handlers import XTPacket


@handlers.handler(XTPacket('bh', 'lnbhg'))
async def handle_leave_non_blackhole_game(p):
    if p.room.blackhole:
        await p.room.leave_blackhole(p)
