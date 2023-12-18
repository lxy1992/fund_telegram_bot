import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, Numeric, String
from sqlalchemy.types import JSON
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
    history_data = Column(JSON)
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


class BuyRecord(Base):
    __tablename__ = 'buy_records'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)  # 添加索引
    fund_code = Column(String(10))
    created_at = Column(DateTime, default=datetime.datetime.now())
    shares = Column(Numeric, default=0.00)
    price = Column(Numeric, default=0.00)
    fund_name = Column(String, nullable=True)
    deleted_at = Column(DateTime, nullable=True, default=None)


class AlertSettings(Base):
    __tablename__ = 'alert_settings'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)  # 添加索引
    fund_code = Column(String(10))
    created_at = Column(DateTime, default=datetime.datetime.now())
    alert_number = Column(Numeric, default=0.00)
    alert_type = Column(String(10), default='price_percentage')
    fund_name = Column(String, nullable=True)
    deleted_at = Column(DateTime, nullable=True, default=None)


class UserConfig(Base):
    __tablename__ = 'user_configs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)  # 添加索引
    daily_report = Column(Boolean, default=0)
