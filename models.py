import datetime

from sqlalchemy import Column, DateTime, Float, Integer, Numeric, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class FundDetail(Base):
    __tablename__ = 'fund_details'
    code = Column(String(10), primary_key=True)
    name = Column(String(100))
    type = Column(String(20))
    net_worth = Column(Float)
    expect_worth = Column(Float)
    total_worth = Column(Float)
    expect_growth = Column(String(10))
    day_growth = Column(String(10))
    last_week_growth = Column(String(10))
    last_month_growth = Column(String(10))
    last_three_months_growth = Column(String(10))
    last_six_months_growth = Column(String(10))
    last_year_growth = Column(String(10))
    buy_min = Column(Float)
    buy_source_rate = Column(Float)
    buy_rate = Column(Float)
    manager = Column(String(50))
    fund_scale = Column(String(50))
    worth_date = Column(DateTime)
    expect_worth_date = Column(DateTime)
    million_copies_income = Column(Float)
    million_copies_income_date = Column(DateTime)
    seven_days_year_income = Column(Float)
    deleted_at = Column(DateTime, nullable=True, default=None)


class UserFund(Base):
    __tablename__ = 'user_funds'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)  # 添加索引
    fund_code = Column(String(10))
    created_at = Column(DateTime, default=datetime.datetime.now())
    subscribed_at = Column(DateTime, index=True, default=datetime.datetime.now())
    unsubscribed_at = Column(DateTime, nullable=True, default=None)
    shares = Column(Numeric, default=0.00)
    fund_name = Column(String, nullable=True)
