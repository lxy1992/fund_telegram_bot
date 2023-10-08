import datetime
import logging

import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from commands import FundApi, get_daily_report, subscribe_user_fund
from config import load_config

config = load_config("config.yml")
# Telegram bot配置
bot_config = config['telegram_bot']
TOKEN = bot_config['token']
BASE_URL = config["fund_api"]["base_url"]

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def daily_report(update_ins: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update_ins.effective_user.id
    message = await get_daily_report(user_id)
    await context.bot.send_message(chat_id=update_ins.effective_chat.id, text=message)


async def subscribe(update_ins: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await context.bot.send_message(chat_id=update_ins.effective_chat.id, text="请提供基金代码和购买份数。")
        return

    fund_code, shares = context.args
    user_id = update_ins.effective_user.id
    message = await subscribe_user_fund(user_id, fund_code, shares)
    await context.bot.send_message(chat_id=update_ins.effective_chat.id, text=message)


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = ' '.join(context.args)
    if not query:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="请提供一个关键词进行搜索。")
        return

    # 使用FundApi类搜索基金
    try:
        funds = FundApi.search_funds(query)
        matching_funds = funds["data"]
        if not matching_funds:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="没有找到匹配的基金。")
            return
        # Get the codes of the matching funds
        matching_codes = [fund[0] for fund in matching_funds]
        today = datetime.datetime.today().strftime("%Y/%m/%d")
        response = FundApi.get_fund_details(matching_codes, start_date=today, end_date=today)
        fund_details = response["data"]
        message = ""
        for fund in fund_details:
            message += f"名称：{fund['name']}\n"
            message += f"代码：{fund['code']}\n"
            message += f"类型：{fund['type']}\n"
            message += f"净值：{fund['netWorth']}\n"
            message += f"预期增长：{fund['expectGrowth']}\n"
            message += "---------------------\n"

        # Send the message to the user
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

        # 处理并发送消息...
    except requests.RequestException as e:
        # 处理API调用中的错误...
        await update.message.reply_text(f"抱歉，搜索基金时出错：{str(e)}")


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    search_handler = CommandHandler('search', search)
    subscribe_handler = CommandHandler('subscribe', subscribe)
    application.add_handler(search_handler)
    application.add_handler(subscribe_handler)
    daily_report_handler = CommandHandler('daily_report', daily_report)
    application.add_handler(daily_report_handler)
    application.run_polling()

