import atexit
import datetime
import logging

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from commands import FundApi, get_daily_report, list_subscriptions_for_user, subscribe_user_fund, unsubscribe_user_fund
from config import load_config
from tasks import send_daily_report_to_subscribers, update_fund_details

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
        fund_details = FundApi.get_fund_details(matching_codes, start_date=today, end_date=today)
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


async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = await list_subscriptions_for_user(user_id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="请提供要取消订阅的基金代码。")
        return

    fund_code = context.args[0]
    user_id = update.effective_user.id
    message = await unsubscribe_user_fund(user_id, fund_code)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "/subscribe <fund_code> <shares> - 订阅一个基金并设置购买的份额。\n"
        "/unsubscribe <fund_code> - 取消订阅一个基金。\n"
        "/list - 列出你当前订阅的所有基金。\n"
        "/search <keyword> - 使用关键字搜索基金。\n"
        "/daily_report - 获取你订阅的基金的每日报告。\n"
        "/help - 显示这个帮助消息。"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "欢迎使用我们的基金订阅Bot！🎉\n\n"
        "你可以使用以下命令来与我互动：\n"
        "/subscribe <fund_code> <shares> - 订阅一个基金并设置购买的份额。\n"
        "/unsubscribe <fund_code> - 取消订阅一个基金。\n"
        "/list - 列出你当前订阅的所有基金。\n"
        "/search <keyword> - 使用关键字搜索基金。\n"
        "/daily_report - 获取你订阅的基金的每日报告。\n"
        "/help - 显示帮助消息。\n\n"
        "如果你有任何问题或建议，随时告诉我们！"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_text)


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    search_handler = CommandHandler('search', search)
    subscribe_handler = CommandHandler('subscribe', subscribe)
    daily_report_handler = CommandHandler('daily_report', daily_report)
    list_subscriptions_handler = CommandHandler('list', list_subscriptions)
    unsubscribe_handler = CommandHandler('unsubscribe', unsubscribe)
    help_handler = CommandHandler('help', help_command)
    start_handler = CommandHandler('start', start_command)
    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(search_handler)
    application.add_handler(subscribe_handler)
    application.add_handler(daily_report_handler)
    application.add_handler(list_subscriptions_handler)
    application.add_handler(unsubscribe_handler)

    # 使用APScheduler来运行定时任务
    scheduler = BackgroundScheduler()

    # 添加一个定时任务，从早上9点到下午4点，每小时运行一次update_fund_details函数
    scheduler.add_job(update_fund_details, 'cron', day_of_week='mon-fri', hour='9-16', minute=0)
    # 添加一个定时任务，每天下午2点运行 send_daily_report_to_subscribers 函数
    scheduler.add_job(send_daily_report_to_subscribers, 'cron', hour=14, minute=0)

    # 开始运行调度器
    scheduler.start()

    application.run_polling()
    atexit.register(lambda: scheduler.shutdown())
