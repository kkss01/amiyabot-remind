import os
import re
import time
import shutil
from typing import Optional, Union

from core import log, bot as main_bot
from core.util import create_dir, read_yaml, any_match
from amiyabot import Message, Chain, PluginInstance
from amiyabot.adapters.cqhttp import CQHttpBotInstance
from amiyabot.adapters.mirai import MiraiBotInstance

from .sql import *
from .extract_time import *

curr_dir = os.path.dirname(__file__)

config_path = 'resource/plugins/kkss/timedRemindConfig.yaml'
week_day_name = {0:'一', 1:'二', 2:'三', 3:'四', 4:'五', 5:'六', 6:'日'}


class TimedRemindInstance(PluginInstance):
    def install(self):
        try:
            config = read_yaml(config_path)
            _ = config.defaultReply
            _ = config.deleteExecuted
            _ = config.isMysql

        except (AttributeError, FileNotFoundError):
            log.info('定时提醒: 已重新生成配置文件')
            create_dir(config_path, is_file=True)
            shutil.copy(f'{curr_dir}/timedRemindConfig.yaml', config_path)


bot = TimedRemindInstance(
    name='定时提醒',
    version='1.8.1',
    plugin_id='kkss-timed-remind',
    plugin_type='',
    description='让兔兔当一个闹钟',
    document=f'{curr_dir}/README.md'
)


def get_prefix_name():
    prefix: list = read_yaml('config/prefix.yaml').prefix_keywords
    return '兔兔' if '兔兔' in prefix else prefix[0]


def replace_items_to_same(text: str, target: list, after: str = '') -> str:
    for item in target:
        text = text.replace(item, after, 1)

    return text


def time_replace(text: str):
    now = time.strftime('%H:%M', time.localtime())
    replace_words = ['现在', '当前', '这个时候', '这个点', '相同时间']
    text = replace_items_to_same(text, replace_words, now)
    text = text.replace('每', '')
    return text


def analysis_remind_time(text: str):
    time_arrays = extract_time(text)
    if not time_arrays:
        return None

    time_text = time.strftime('%Y-%m-%d %H:%M', time_arrays[0])
    stamp1 = time.mktime(time_arrays[0])

    if len(time_arrays) < 2:
        return time_text, stamp1

    stamp2 = time.mktime(time_arrays[1])
    if stamp2 - stamp1 < 3600:
        return time_text, stamp1

    stamp1 += 43200
    time_text = time.strftime('%Y-%m-%d %H:%M', time.localtime(stamp1))

    return time_text, stamp1


def analysis_remind_cycle(text: str):
    if r := re.search(r'每(天|周)', text):

        if '天' in r.group(1):
            return 60 * 60 * 24, '每天'

        elif '周' in r.group(1):
            return 60 * 60 * 24 * 7, '每周'

    return 0, ''


async def set_remind_verify(data: Message):
    text = data.text

    if key := any_match(text, ['提醒', 'tx']):

        if any_match(text, ['理智', '查看', '删除']):
            return False

        if any_match(text, [':', '分钟', '点', '小时', '天', '周', '月']):
            return True, 4, key

        return True, 2, key


@bot.on_message(verify=set_remind_verify)
async def _(data: Message):
    sentence = None
    if '::' in data.text:
        sentence = data.text.split('::', 1)
    elif '：：' in data.text:
        sentence = data.text.split('：：', 1)

    if sentence and len(sentence) > 1:
        timing = sentence[0]
        content = sentence[1]

    else:
        sentence = data.text.split(data.verify.keypoint, 1)
        timing = sentence[0]
        content = replace_items_to_same(sentence[1], ['全员', '全体成员', '我'])

    is_all_members = bool(any_match(data.text, ['全员', '全体成员']))

    if not data.is_admin and is_all_members:
        return Chain(data).text('全体提醒只能由管理员设置哦')

    cycle_stamp, cycle_name = analysis_remind_cycle(timing)
    timing = time_replace(timing)

    remind_time = analysis_remind_time(timing)

    if not remind_time:
        pk = get_prefix_name()
        return Chain(data).text(f'请指定准确的时间 如:\n{pk}明天晚上8点提醒我上号')

    if cycle_name:
        tm_wday = time.localtime(remind_time[1])[6]
        week_day = week_day_name.get(tm_wday)
        strf = f'{week_day} %H:%M'
    else:
        strf = '%Y年%m月%d日 %H:%M'

    remind_time_text = time.strftime(strf, time.localtime(remind_time[1]))

    if not content:
        content = ''

    not_content = ' (没有设置提醒内容)'
    wait = await data.wait(Chain(data, at=False).text(
        f'要在{cycle_name} {remind_time_text} 提醒'
        f'{"全体成员" if is_all_members else "博士"}{content}吗?'
        f'{not_content if not content else ""}'), force=False)

    if wait:
        if any_match(wait.text, ['好', '是', '要', '确定', 'ok', 'OK']):
            await set_remind(
                data=data,
                remind_time=int(remind_time[1]),
                content=content,
                cycle_stamp=cycle_stamp,
                is_all_members=is_all_members
            )
            return Chain(data).text('好的, 兔兔记住了')


async def view_remind_verify(data: Message):
    text = data.text
    if '提醒' not in text and 'tx' not in text:
        return False

    if '查看' in text:
        return True, 5


@bot.on_message(verify=view_remind_verify)
async def _(data: Message):
    print('onm')
    remind_list: list = await get_remind(data=data)
    if not remind_list:
        return Chain(data).text('没有已设置的提醒')

    remind_list_str = ''
    for item in remind_list:
        index = item.get('index')
        content = item.get('content')
        cycle_name = item.get('cycle_name')

        if cycle_name:
            tm_wday = time.localtime(item.get('remind_time'))[6]
            week_day = week_day_name.get(tm_wday)
            strf = f'{week_day} %H:%M'
        else:
            strf = '%Y年%m月%d日 %H:%M'

        remind_time_str = time.strftime(strf, time.localtime(item.get('remind_time')))
        content_str = f'内容: {content}' if content else ''
        remind_list_str += f'[{index}] {cycle_name}{remind_time_str} {content_str}\n'

    return Chain(data).text(remind_list_str)


async def delete_remind_verify(data: Message):
    text = data.text
    if '提醒' not in text and 'tx' not in text:
        return False

    if '删除' in text:
        return True, 4


@bot.on_message(verify=delete_remind_verify)
async def _(data: Message):
    remind_list: list = await get_remind(data=data)
    if not remind_list:
        return Chain(data).text('没有已设置的提醒')

    sub = data.text.split()
    print(f'{sub[0] = }')
    selected_index = list(map(int,re.findall(r'\d+', sub[0])))
    selected_index += [int(item) for item in sub if item.isdigit()]
    print(selected_index)
    if not selected_index:
        pk = get_prefix_name()
        return Chain(data).text(f'请指定要删除的编号 如:\n{pk}删除提醒 1')

    tag = 0
    success_del = ''
    for index_del in selected_index:
        for remind in remind_list:
            index = remind.get('index')
            if index == index_del:
                success_del += f'{index_del} '
                await delete_remind(index=remind.get('id'))
                tag += 1
    if tag:
        return Chain(data).text(f'删除成功: {success_del}')

    return Chain(data).text('删除失败: 没有对应的编号')


@bot.timed_task(each=10)
async def remind_(*_, **__):
    try:
        config = read_yaml(config_path)
        default_reply: str = config.defaultReply
        delete_executed: bool = config.deleteExecuted

    except (AttributeError, FileNotFoundError):
        log.warning('定时提醒: 配置文件读取错误, 请检查')
        default_reply = '博士, 你设置的时间已经到啦'

    now = int(time.time())
    conditions = (Remind.remind_time <= now, Remind.executed == 0)
    results: List[Remind] = Remind.select().where(*conditions)
    if results:
        for item in results:
            if item.cycle_stamp:
                next_time = item.remind_time + item.cycle_stamp
                Remind.update(remind_time=next_time).where(*conditions).execute()
            else:
                if delete_executed:
                    Remind.delete().where(Remind.id == item.id).execute()
                else:
                    Remind.update(executed=1).where(*conditions).execute()

            if item.remind_time < now - 3600:  # 过期的不提醒
                continue

            text = item.content if item.content else default_reply

            instance = main_bot[item.belong_id].instance

            if type(instance) is CQHttpBotInstance:
                atAll = {
                    'type':'at',
                    'data':{
                        'qq':'all'
                    }}

            if type(instance) is MiraiBotInstance:
                atAll = {
                    'type':'AtAll'
                }

            if item.is_all_members:
                chain = Chain().text(text).extend(atAll)

            else:
                chain = Chain().text(text).at(item.user_id)

            await main_bot[item.belong_id].send_message(chain, channel_id=item.group_id)
