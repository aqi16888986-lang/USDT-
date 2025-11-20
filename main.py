import os
import time
import requests
from collections import defaultdict
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# 从环境变量读取（安全！）
TOKEN = os.getenv("BOT_TOKEN")
MORALIS_KEY = os.getenv("MORALIS_KEY")

# USDT 合约地址
USDT_CONTRACTS = {
    "ethereum": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "bsc": "0x55d398326f99059ff775485a6f3bd0f4e5d4b9f",
    "tron": "TR7NHqjeKQxGTCuuP8qACi7c3iN8UQixL",
}

user_data = defaultdict(dict)

def get_chain(addr: str):
    addr = addr.strip().lower()
    if addr.startswith("t") and len(addr) >= 34: return "tron"
    if addr.startswith("0x") and len(addr) == 42: return "ethereum"
    return None

async def get_usdt_balance(addr: str, chain: str):
    try:
        url = f"https://deep-index.moralis.io/api/v2.2/wallets/{addr}/tokens"
        headers = {"X-API-Key": MORALIS_KEY}
        params = {"chain": chain}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            for token in r.json():
                if token.get("token_address", "").lower() == USDT_CONTRACTS[chain].lower():
                    return round(float(token["balance"]) / 1_000_000, 6)
    except:
        pass
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "USDT 到账监听机器人已启动！\n\n"
        "支持以太坊、BSC、波场地址\n"
        "直接发地址给我 → 24小时监控 ≥1 USDT 到账/转出立刻提醒！"
    )

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip()
    user_id = update.effective_user.id
    chain = get_chain(addr)

    if not chain:
        await update.message.reply_text("只支持 0x...（以太/BSC）或 T...（波场）地址")
        return

    bal = await get_usdt_balance(addr.lower(), chain)
    if bal is None:
        await update.message.reply_text("查询失败，稍后再试")
        return

    user_data[user_id][addr.lower()] = {"bal": bal, "chain": chain}
    await update.message.reply_text(
        f"已开始24小时监听！\n"
        f"地址：{addr}\n"
        f"当前余额：{bal:,} USDT\n"
        f"有 ≥1 USDT 变动立刻通知你！"
    )

async def checker(context: ContextTypes.DEFAULT_TYPE):
    for uid, addrs in list(user_data.items()):
        for addr, info in list(addrs.items()):
            new_bal = await get_usdt_balance(addr, info["chain"])
            if new_bal and abs(new_bal - info["bal"]) >= 1:
                diff = new_bal - info["bal"]
                await context.bot.send_message(
                    uid,
                    f"{'到账啦！！！' if diff > 0 else '转出提醒'}\n"
                    f"金额：{abs(diff):,} USDT\n"
                    f"地址：{addr}\n"
                    f"最新余额：{new_bal:,} USDT\n"
                    f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                info["bal"] = new_bal

def main():
    if not TOKEN or not MORALIS_KEY:
        print("错误：缺少 BOT_TOKEN 或 MORALIS_KEY 环境变量！")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.job_queue.run_repeating(checker, interval=30, first=10)

    print("USDT监听机器人启动成功！正在24小时运行...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
