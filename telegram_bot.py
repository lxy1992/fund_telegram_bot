from requests import Session

from models import FundDetail, UserFund


def send_notifications():
    session = Session()
    user_funds = session.query(UserFund).all()
    for uf in user_funds:
        fund_detail = session.query(FundDetail).filter_by(code=uf.fund_code).first()
        message = f"基金代码：{uf.fund_code}\n名称：{uf.fund.name}\n净值：{fund_detail.net_worth}\n日涨幅：{fund_detail.day_growth}%"
        # bot.send_message(chat_id=uf.user_id, text=message)
    session.close()