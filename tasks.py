import asyncio
from datetime import datetime

from commands import (
    FundApi, get_all_fund_codes_from_db, get_daily_report, get_subscribers, send_message_to_user,
    update_fund_detail_in_db, update_fund_realtime_in_db)


# 你的数据库更新函数
async def update_fund_details():
    # 获取所有基金代码
    fund_codes = await get_all_fund_codes_from_db()

    # 假设你使用requests库来获取基金数据
    data = FundApi().get_fund_details(fund_codes)
    for fund in data:
        await update_fund_detail_in_db(fund)
    print(f"Updating fund details at {datetime.now()}")


async def update_realtime_fund_details():
    # 获取所有基金代码
    fund_codes = await get_all_fund_codes_from_db()

    data = FundApi().get_real_time_fund(fund_codes)
    for fund in data:
        await update_fund_realtime_in_db(fund)
    print(f"Updating fund details at {datetime.now()}")


def sync_update_realtime_fund_details():
    asyncio.run(update_realtime_fund_details())


def sync_update_fund_details():
    asyncio.run(update_fund_details())


async def send_daily_report_to_subscribers():
    # 获取所有订阅了 daily report 的用户
    subscribers = await get_subscribers()

    # 对每个用户发送 daily report
    for user_id in subscribers:
        message, image_path = await get_daily_report(user_id, True)
        await send_message_to_user(user_id, message, image_path)  # 你可能需要实现这个函数


def sync_send_daily_report_to_subscribers():
    asyncio.run(send_daily_report_to_subscribers())
