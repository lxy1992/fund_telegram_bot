import asyncio
import datetime
import decimal
import json
import re
import ssl
from decimal import Decimal, ROUND_DOWN

import requests
from sqlalchemy import NullPool, and_, distinct, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from telegram import Bot

from config import load_config
from models import FundDetail, UserFund

config = load_config("config.yml")
db_config = config['database']
bot_config = config['telegram_bot']
TOKEN = bot_config['token']

DATABASE_URL = db_config['url']
# SSL参数
ssl_args = {
    'ssl': ssl.create_default_context(cafile='cacert.pem')
}
engine = create_async_engine(DATABASE_URL, connect_args=ssl_args, echo=True, poolclass=NullPool)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class FundApi:
    BASE_URL = 'https://api.doctorxiong.club/v1/fund'  # 请替换为实际的API基础URL

    @staticmethod
    def search_funds(keyword):
        """
        使用关键字搜索基金。

        :param keyword: 用于搜索基金的关键字
        :return: API响应的JSON数据
        """
        response = requests.get(f"{FundApi.BASE_URL}/all", params={"keyWord": keyword})
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    @staticmethod
    def get_fund_details(codes, start_date=None, end_date=None):
        """
        获取一个或多个基金的详细信息。

        :param codes: 基金代码列表
        :param start_date: 开始日期（可选）
        :param end_date: 结束日期（可选）
        :return: API响应的JSON数据
        """
        params = {"code": ",".join(codes)}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = requests.get(f"{FundApi.BASE_URL}/detail/list", params=params)
        if response.status_code == 200:
            return response.json()["data"]
        else:
            response.raise_for_status()

    @staticmethod
    def get_real_time_fund(codes):
        res_data = []
        for code in codes:
            url = f"http://fundgz.1234567.com.cn/js/{code}.js"
            # 浏览器头
            headers = {'content-type': 'application/json',
                       'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:22.0) Gecko/20100101 Firefox/22.0'}

            r = requests.get(url, headers=headers)
            # 返回信息
            content = r.text
            # 正则表达式
            pattern = r'^jsonpgz\((.*)\)'
            # 查找结果
            search = re.findall(pattern, content)
            # 遍历结果
            print(search)
            if len(search) > 0:
                data = json.loads(search[0])
                res_data.append(data)
        return res_data


async def subscribe_user_fund(user_id, fund_code, shares):
    async with async_session() as session:
        # 检查用户是否已订阅该基金
        stmt = select(UserFund).where(UserFund.user_id == user_id, UserFund.fund_code == fund_code)
        result = await session.execute(stmt)
        user_fund = result.scalar_one_or_none()

        if user_fund:
            # 如果用户已订阅，更新份数
            await session.execute(
                update(UserFund).
                where(and_(UserFund.user_id == user_id, UserFund.fund_code == fund_code)).
                values(shares=shares, unsubscribed_at=None)
            )
            message = "份数已更新"
        else:
            # 如果用户未订阅，创建新的订阅记录
            new_subscription = UserFund(user_id=user_id, fund_code=fund_code, shares=shares)
            session.add(new_subscription)
            message = "订阅成功"

        await session.commit()

        # 异步获取基金数据并更新FundDetail表
        asyncio.ensure_future(fetch_and_update_fund_data(fund_code))

        return message


async def fetch_and_update_fund_data(fund_code):
    fund_api = FundApi()
    fund_data = fund_api.get_fund_details([fund_code])  # 假设get_fund_data是异步的并返回基金数据
    data = fund_data[0]
    async with async_session() as session:
        # 更新或插入基金数据到FundDetail表
        # 你可能需要根据实际的API响应调整字段映射
        fund_detail = FundDetail(
            code=data["code"],
            name=data["name"],
            type=data["type"],
            net_worth=data["netWorth"],
            expect_worth=data["expectWorth"],
            total_worth=data["totalWorth"],
            expect_growth=data["expectGrowth"],
            day_growth=data["dayGrowth"],
            last_week_growth=data["lastWeekGrowth"],
            last_month_growth=data["lastMonthGrowth"],
            last_three_months_growth=data["lastThreeMonthsGrowth"],
            last_six_months_growth=data["lastSixMonthsGrowth"],
            last_year_growth=data["lastYearGrowth"],
            buy_min=float(data.get("buyMin", "0")) if data.get("buyMin") else None,
            buy_source_rate=float(data.get("buySourceRate", "0")) if data.get("buySourceRate") else None,
            buy_rate=float(data.get("buyRate", "0")) if data.get("buyRate") else None,
            manager=data["manager"],
            fund_scale=data["fundScale"],
            worth_date=datetime.datetime.strptime(data["netWorthDate"], "%Y-%m-%d"),
            # 如果API返回其他日期字段，也按照上面的方式处理
        )

        # 在这里你可能需要一个更复杂的逻辑来处理数据更新
        # 例如，如果数据已存在，你可能想更新它而不是插入一个新的记录
        await session.merge(fund_detail)  # 使用merge来处理可能的更新
        # 更新UserFund表中的fund_name字段
        await session.execute(
            update(UserFund).
            where(UserFund.fund_code == fund_code).
            where(or_(UserFund.fund_name == None, UserFund.fund_name == '')).
            values(fund_name=data["name"])
        )
        await session.commit()


async def get_daily_report(user_id):
    async with async_session() as session:
        # 获取用户订阅的基金
        subscribed_funds = await session.execute(
            select(UserFund.fund_code, UserFund.shares).where(
                UserFund.user_id == user_id, UserFund.unsubscribed_at.is_(None))
        )
        subscribed_funds_list = subscribed_funds.all()

        report = []
        total_amount = 0
        total_expect_change_amount = 0
        if len(subscribed_funds_list) == 0:
            return "您当前没有订阅任何基金。"

        # 获取基金详情并计算涨跌金额
        for fund in subscribed_funds_list:
            fund_code, shares = fund
            fund_detail = await session.execute(
                select(FundDetail).where(FundDetail.code == fund_code)
            )
            fund_detail = fund_detail.scalar_one()
            data = FundApi().get_real_time_fund([fund_code])

            # 计算估计的涨跌金额
            if len(data) > 0:
                expect_worth = Decimal(str(data[0]["gsz"]))
                expect_growth = Decimal(str(data[0]["gszzl"])) / 100
                expect_growth_str = str(data[0]["gszzl"])
            else:
                expect_worth = Decimal(str(fund_detail.expect_worth))
                expect_growth = Decimal(str(fund_detail.expect_growth)) / 100
                expect_growth_str = str(fund_detail.expect_growth)

            expect_yesterday_worth = (expect_worth / (1 + expect_growth)).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            expect_growth_value = (expect_yesterday_worth * expect_growth).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            expect_change_amount = (shares * expect_growth_value).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            # 计算实际的涨跌金额
            net_worth = Decimal(str(fund_detail.net_worth))
            day_growth = Decimal(str(fund_detail.day_growth)) / decimal.Decimal(100)
            yesterday_worth = (net_worth / (1 + day_growth)).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            real_growth_value = (yesterday_worth * day_growth).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            change_amount = (shares * real_growth_value).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)

            # 添加到报告中
            report.append({
                "fund_code": fund.fund_code,
                "fund_name": fund_detail.name,
                "change_amount": change_amount,
                "expect_change_amount": expect_change_amount,
                "shares": shares,
                "expect_growth": fund_detail.expect_growth,
                "expect_worth": expect_growth_str,
                "net_worth": fund_detail.net_worth,
            })

            # 计算总金额
            total_amount += change_amount
            total_expect_change_amount += expect_change_amount
        # 格式化报告并返回给用户
        message = "日报：\n---------------------\n"
        for item in report:
            message += (
                f"{item['fund_name']}({item['fund_code']}): \n"
                f"实际涨跌金额={item['change_amount']}元, \n"
                f"预估涨跌金额={item['expect_change_amount']}元, \n"
                f"预估涨跌百分比={item['expect_growth']}%, \n"
                f"持有份数={item['shares']}, \n"
                f"预估净值={item['expect_worth']}, \n"
                f"实际净值={item['net_worth']}\n"
                "---------------------\n"
            )
        message += f"总金额：{total_amount}元\n"
        message += f"预估总金额：{total_expect_change_amount}元\n"

        return message


async def get_all_fund_codes_from_db():
    async with async_session() as session:
        stmt = select(FundDetail.code).where(FundDetail.deleted_at.is_(None))
        result = await session.execute(stmt)
        # 将结果转换为列表
        fund_codes = [row[0] for row in result.fetchall()]
    return fund_codes


async def update_fund_detail_in_db(fund_data):
    async with async_session() as session:
        # 构建更新语句
        stmt = (
            update(FundDetail).
            where(FundDetail.code == fund_data["code"]).
            values(
                name=fund_data["name"],
                type=fund_data["type"],
                net_worth=fund_data["netWorth"],
                total_worth=fund_data["totalWorth"],
                day_growth=fund_data["dayGrowth"],
                last_week_growth=fund_data["lastWeekGrowth"],
                last_month_growth=fund_data["lastMonthGrowth"],
                last_three_months_growth=fund_data["lastThreeMonthsGrowth"],
                last_six_months_growth=fund_data["lastSixMonthsGrowth"],
                last_year_growth=fund_data["lastYearGrowth"],
                buy_min=float(fund_data.get("buyMin", "0")) if fund_data.get("buyMin") else None,
                buy_source_rate=float(fund_data.get("buySourceRate", "0")) if fund_data.get("buySourceRate") else None,
                buy_rate=float(fund_data.get("buyRate", "0")) if fund_data.get("buyRate") else None,
                manager=fund_data["manager"],
                fund_scale=fund_data["fundScale"],
                worth_date=datetime.datetime.strptime(fund_data["netWorthDate"], "%Y-%m-%d"),
                # 如果API返回其他日期字段，也按照上面的方式处理
            )
        )
        # 执行更新语句
        await session.execute(stmt)
        # 提交事务
        await session.commit()


async def update_fund_realtime_in_db(fund_data):
    async with async_session() as session:
        # 构建更新语句
        stmt = (
            update(FundDetail).
            where(FundDetail.code == fund_data["fundcode"]).
            values(
                expect_worth=fund_data["gsz"],
                expect_growth=fund_data["gszzl"],
            )
        )
        # 执行更新语句
        await session.execute(stmt)
        # 提交事务
        await session.commit()


async def get_subscribers():
    async with async_session() as session:
        # 查询所有不同的用户ID
        result = await session.execute(select(distinct(UserFund.user_id)))
        subscribers = [row[0] for row in result]
        return subscribers


async def send_message_to_user(user_id, message):
    bot = Bot(token=TOKEN)  # 使用你的 Telegram bot token

    await bot.send_message(chat_id=user_id, text=message)


async def list_subscriptions_for_user(user_id):
    async with async_session() as session:
        # 查询用户订阅的所有基金
        stmt = select(UserFund).where(UserFund.user_id == user_id, UserFund.unsubscribed_at.is_(None))
        result = await session.execute(stmt)
        subscriptions = result.scalars().all()

        if not subscriptions:
            return "您当前没有订阅任何基金。"

        message = "您当前订阅的基金：\n"
        for sub in subscriptions:
            message += f"基金代码：{sub.fund_code}, 基金名称：{sub.fund_name}, 份额：{sub.shares}\n"

        return message


async def unsubscribe_user_fund(user_id, fund_code):
    async with async_session() as session:
        # 查询并删除用户订阅的基金
        stmt = (
            update(UserFund)
            .where(UserFund.user_id == user_id)
            .where(UserFund.fund_code == fund_code)
            .values(unsubscribed_at=datetime.datetime.now())
        )
        result = await session.execute(stmt)

        if result.rowcount == 0:
            return f"未找到代码为 {fund_code} 的订阅。"

        await session.commit()
        return f"已取消订阅代码为 {fund_code} 的基金。"
