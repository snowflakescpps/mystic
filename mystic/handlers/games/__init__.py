import random
import time

from sqlalchemy.dialects.postgresql import insert

from mystic import handlers
from mystic.constants import ClientType
from mystic.converters import OptionalConverter
from mystic.data.game import PenguinGameData
from mystic.data.room import Room
from mystic.handlers import XTPacket
from mystic.handlers.play.moderation import cheat_ban
from mystic.handlers.play.navigation import handle_join_room

default_score_games = {904, 905, 906, 912, 916, 917, 918, 919, 950, 952}


def determine_coins_earned(p, score):
    return score if p.room.id in default_score_games else score // 10


async def determine_coins_overdose(p, coins):
    overdose_key = f'{p.id}.overdose'
    last_overdose = await p.server.redis.get(overdose_key)

    if last_overdose is None:
        return True

    minutes_since_last_dose = ((time.time() - float(last_overdose)) // 60) + 1
    max_game_coins = p.server.config.max_coins_per_min * minutes_since_last_dose

    if coins > max_game_coins:
        return True
    return False


@handlers.handler(XTPacket('j', 'jr'), before=handle_join_room)
async def handle_overdose_key(p, room: Room):
    if p.room.game and not room.game:
        overdose_key = f'{p.id}.overdose'
        await p.server.redis.delete(overdose_key)
    elif room.game:
        overdose_key = f'{p.id}.overdose'
        await p.server.redis.set(overdose_key, time.time())


@handlers.disconnected
@handlers.player_attribute(joined_world=True)
async def disconnect_overdose_key(p):
    if p.room is not None and p.room.game:
        overdose_key = f'{p.id}.overdose'
        await p.server.redis.delete(overdose_key)


async def game_over_cooling(p):
    await p.send_xt('zo', p.coins, '', 0, 0, 0)


@handlers.handler(XTPacket('m', ext='z'))
@handlers.player_in_room(802)
async def handle_send_move_puck(p, _, x: int, y: int, speed_x: int, speed_y: int):
    p.server.puck = (x, y)
    await p.room.send_xt('zm', p.id, x, y, speed_x, speed_y)


@handlers.handler(XTPacket('gz', ext='z'))
@handlers.player_in_room(802)
async def handle_get_puck(p):
    await p.send_xt('gz', *p.server.puck)


@handlers.handler(XTPacket('zo', ext='z'))
@handlers.cooldown(10, callback=game_over_cooling)
async def handle_get_game_over(p, score: int):
    if p.room.game and not p.waddle and not p.table:
        coins_earned = determine_coins_earned(p, score)
        if await determine_coins_overdose(p, coins_earned):
            return await cheat_ban(p, p.id, comment='Coins overdose')

        collected_stamps_string, total_collected_stamps, total_game_stamps, total_stamps = '', 0, 0, 0
        if p.room.stamp_group:
            game_stamps = [stamp for stamp in p.server.stamps.values() if stamp.group_id == p.room.stamp_group]
            collected_stamps = [stamp for stamp in game_stamps if stamp.id in p.stamps]

            total_stamps = len([stamp for stamp in p.stamps.values() if p.server.stamps[stamp.stamp_id].group_id])
            total_collected_stamps = len(collected_stamps)
            total_game_stamps = len(game_stamps)
            collected_stamps_string = '|'.join(str(stamp.id) for stamp in collected_stamps)

            if total_collected_stamps == total_game_stamps:
                coins_earned *= 2

        await p.update(coins=min(p.coins + coins_earned, p.server.config.max_coins)).apply()
        await p.send_xt('zo', p.coins,
                        collected_stamps_string,
                        total_collected_stamps,
                        total_game_stamps,
                        total_stamps)


@handlers.handler(XTPacket('ggd', ext='z'), client=ClientType.Vanilla)
async def handle_get_game_data(p, index: int = 0):
    game_data = await PenguinGameData.select('data').where((PenguinGameData.penguin_id == p.id) &
                                                           (PenguinGameData.room_id == p.room.id) &
                                                           (PenguinGameData.index == index)).gino.scalar()
    await p.send_xt('ggd', game_data or '')


@handlers.handler(XTPacket('sgd', ext='z'), client=ClientType.Vanilla)
@handlers.cooldown(5)
async def handle_set_game_data(p, index: OptionalConverter(int) = 0, *, game_data: str):
    if p.room.game:
        data_insert = insert(PenguinGameData).values(penguin_id=p.id, room_id=p.room.id, index=index, data=game_data)
        data_insert = data_insert.on_conflict_do_update(
            constraint='penguin_game_data_pkey',
            set_=dict(data=game_data),
            where=((PenguinGameData.penguin_id == p.id)
                   & (PenguinGameData.room_id == p.room.id)
                   & (PenguinGameData.index == index))
        )

        await data_insert.gino.scalar()


@handlers.handler(XTPacket('zr', ext='z'), client=ClientType.Vanilla)
@handlers.player_attribute(agent_status=True)
async def handle_get_game_again(p):
    games = list(range(1, 11))

    games_string = f'{games.pop(random.randrange(len(games)))},' \
                   f'{games.pop(random.randrange(len(games)))},' \
                   f'{games.pop(random.randrange(len(games)))}'
    await p.send_xt('zr', games_string, random.randint(1, 6))


@handlers.handler(XTPacket('zc', ext='z'), client=ClientType.Vanilla)
@handlers.player_attribute(agent_status=True)
@handlers.cooldown(5)
async def handle_game_complete(p, medals: int):
    medals = min(6, medals)
    await p.update(career_medals=p.career_medals + medals,
                   agent_medals=p.agent_medals + medals).apply()
