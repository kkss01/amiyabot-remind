import time

from amiyabot.database import *
from amiyabot import Message
from core import log
from core.database import config, is_mysql
from core.util import read_yaml

config_path = 'resource/plugins/kkss/timedRemindConfig.yaml'

try:
    config = read_yaml(config_path)
    is_mysql = config.isMysql

except (AttributeError, FileNotFoundError):
    log.warning('定时提醒: 请再次重启bot或重装插件以读取配置文件')
    is_mysql = False

db = connect_database('kkss-remind' if is_mysql else 'database/kkss-remind.db', is_mysql, config)


class UserBaseModel(ModelClass):
    class Meta:
        database = db


@table
class Remind(UserBaseModel):
    user_id: str = CharField()
    group_id: str = CharField()
    remind_time: int = IntegerField()
    content: str = CharField(null=True)
    executed: int = IntegerField(default=0)
    cycle_stamp: int = IntegerField(null=True)
    is_all_members: int = IntegerField(null=True)
    set_time: int = IntegerField()
    belong_id: int = IntegerField()


async def set_remind(data: Message, remind_time: int, content: str = None,
                     cycle_stamp: int = None, is_all_members: int = 0):
    data = {
        'user_id':data.user_id,
        'group_id':data.channel_id,
        'set_time':time.time(),
        'remind_time':remind_time,
        'content':content,
        'cycle_stamp':cycle_stamp,
        'is_all_members':is_all_members,
        'belong_id':data.instance.appid
    }
    Remind.create(**data)


async def get_remind(data: Message):
    results: List[Remind] = Remind.select().where(
        Remind.user_id == data.user_id,
        Remind.group_id == data.channel_id,
        Remind.belong_id == data.instance.appid
    )
    if not results:
        return None

    index = 0
    remind_list = []
    for item in results:
        if item.executed == 1:
            continue

        index += 1

        cycle_name = ''
        if item.cycle_stamp == 60 * 60 * 24: cycle_name = '每天'
        if item.cycle_stamp == 60 * 60 * 24 * 7: cycle_name = '每周'

        remind = {
            'id':item.id,
            'index':index,
            'remind_time':item.remind_time,
            'content':item.content,
            'cycle_name':cycle_name,
            'is_all_members':item.is_all_members,
        }

        remind_list.append(remind)

    return remind_list


'''
            'user_id': item.user_id,
            'group_id': item.group_id,
            'set_time': item.set_time,
            'cycle_stamp': item.cycle_stamp,
            'belong_id': item.belong_id
'''


async def delete_remind(index: int):
    Remind.delete().where(Remind.id == index).execute()
