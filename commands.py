import asyncio
import datetime
import decimal
import ssl
from decimal import Decimal, ROUND_DOWN

import requests
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import load_config
from models import FundDetail, UserFund

config = load_config("config.yml")
db_config = config['database']

DATABASE_URL = db_config['url']
# SSL参数
ssl_args = {
    'ssl': ssl.create_default_context(cafile='cacert.pem')
}
engine = create_async_engine(DATABASE_URL, connect_args=ssl_args, echo=True)
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
            return response.json()
        else:
            response.raise_for_status()


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
                values(shares=shares)
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
    if fund_data["code"] != 200:
        # 处理API调用中的错误...
        return
    print(fund_data)
    data = fund_data["data"][0]
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
            buy_min=float(data["buyMin"]),
            buy_source_rate=float(data["buySourceRate"]),
            buy_rate=float(data["buyRate"]),
            manager=data["manager"],
            fund_scale=data["fundScale"],
            worth_date=datetime.datetime.strptime(data["netWorthDate"], "%Y-%m-%d"),
            # 如果API返回其他日期字段，也按照上面的方式处理
        )

        # 在这里你可能需要一个更复杂的逻辑来处理数据更新
        # 例如，如果数据已存在，你可能想更新它而不是插入一个新的记录
        await session.merge(fund_detail)  # 使用merge来处理可能的更新
        await session.commit()


async def get_daily_report(user_id):
    async with async_session() as session:
        # 获取用户订阅的基金
        subscribed_funds = await session.execute(
            select(UserFund.fund_code, UserFund.shares).where(UserFund.user_id == user_id)
        )
        # subscribed_funds = subscribed_funds.scalars().all()

        report = []
        total_amount = 0

        # 获取基金详情并计算涨跌金额
        for fund in subscribed_funds:
            fund_detail = await session.execute(
                select(FundDetail).where(FundDetail.code == fund.fund_code)
            )
            fund_detail = fund_detail.scalar_one()

            # 计算估计的涨跌金额
            expect_worth = Decimal(str(fund_detail.expect_worth))
            expect_growth = Decimal(str(fund_detail.expect_growth)) / 100
            expect_yesterday_worth = (expect_worth / (1 + expect_growth)).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            expect_growth_value = (expect_yesterday_worth * expect_growth).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            expect_change_amount = (fund.shares * expect_growth_value).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            # 计算实际的涨跌金额
            net_worth = Decimal(str(fund_detail.net_worth))
            day_growth = Decimal(str(fund_detail.day_growth)) / decimal.Decimal(100)
            yesterday_worth = (net_worth / (1 + day_growth)).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            real_growth_value = (yesterday_worth * day_growth).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            change_amount = (fund.shares * real_growth_value).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)

            # 添加到报告中
            report.append({
                "fund_code": fund.fund_code,
                "fund_name": fund_detail.name,
                "change_amount": change_amount,
                "expect_change_amount": expect_change_amount,
                "shares": fund.shares,
                "expect_worth": fund_detail.expect_worth,
                "net_worth": fund_detail.net_worth,
            })

            # 计算总金额
            total_amount += change_amount
        # 格式化报告并返回给用户
        message = "日报：\n---------------------\n"
        for item in report:
            message += (
                f"{item['fund_name']}({item['fund_code']}): \n"
                f"实际涨跌金额={item['change_amount']}元, \n"
                f"预估涨跌金额={item['expect_change_amount']}元, \n"
                f"持有份数={item['shares']}, \n"
                f"预估净值={item['expect_worth']}, \n"
                f"实际净值={item['net_worth']}\n"
                "---------------------\n"
            )
        message += f"总金额：{total_amount}元"

        return message
