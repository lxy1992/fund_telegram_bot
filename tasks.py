import requests
from apscheduler.schedulers.background import BackgroundScheduler

def fetch_fund_data():
    session = Session()
    user_funds = session.query(UserFund).all()
    fund_codes = [uf.fund_code for uf in user_funds]

    for code in fund_codes:
        response = requests.get(f"/v1/fund/detail/list?code={code}")
        data = response.json()["data"][0]
        fund_detail = FundDetail(**data)
        session.merge(fund_detail)
    session.commit()
    session.close()


