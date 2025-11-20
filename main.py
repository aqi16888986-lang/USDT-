import os
import time
import requests
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 从 Railway 环境变量读取（安全！千万不要写死在代码里）
TOKEN = os.getenv("BOT_TOKEN")
MORALIS_API_KEY = os.getenv("MORALIS_KEY")

# USDT 合约地址（支持以太、波场、BSC）
USDT_CONTRACTS = {
    "ethereum": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "tron":     "TR7NHqjeKQxGTCuuP8qACi7c3iN8UQixL",
    "bsc":      "0x55d398326f99059ff775485a6f3bd0f4e5d4b9f",
}

user_data = defaultdict(dict)   # {user_id: {address: {"bal": xxx, "chain": "tron"}}}

def get_chain(addr: str) -> str:
    return "tron" if addr.startswith("T") else "ethereum"

async def get_balance(address: str, chain: str):
    contract = USDT_CONTRACTS.get(chain, USDT_CONTRACTS["ethereum"])
    try:
        url = f"https://deep-index.moralis.io/api/v2.2/wallets/{address}/erc20"
        headers = {"X-API-Key": MORALIS_API_KEY}
        params = {"chain": chain, "token_addresses": [contract]}
        r = requests.get(url, headers=headers, params=params, timeout=12)
        data = r.json()
        if data and len(data) > 0:
            return round(float(data[0]["balance"]) / 1_000_000, 6)
    except Exception as e:
        print(f"Moralis 查询出错: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "USDT 到账监听机器人已启动！\n\n"
        "直接发任意 USDT 地址（支持以太坊、BSC、波场）给我，\n"
        "我就会 24 小时监控，有 ≥1 USDT 到账或转出立刻提醒你！"
    )

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip().lower()
    user_id = update.effective_user.id

    if len(addr) < 30:
        await update.message.reply_text("这不像钱包地址哦～")
        return

    chain = get_chain(addr)
    bal = await get_balance(addr, chain)
    if bal is None:
        await update.message.reply_text("查询失败，网络繁忙或地址不支持，稍后再试～")
        return

    user_data[user_id][addr] = {"bal": bal, "chain": chain}
    await update.message.reply_text(
        f"已开始 24h 监听！\n"
        f"地址：{addr}\n"
        f"当前余额：{bal:,} USDT\n"
        f"有 ≥1 USDT 变动立刻提醒你！"
    )

async def checker(context: ContextTypes.DEFAULT_TYPE):
    for uid, addrs in list(user_data.items()):
        for addr, info in list(addrs.items()):
            new_bal = await get_balance(addr, info["chain"])
            if new_bal is not None and abs(new_bal - info["bal"]) >= 1:
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
    if not TOKEN or not MORALIS_API_KEY:
        print("错误：缺少 BOT_TOKEN 或 MORALIS_KEY 环境变量！")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.job_queue.run_repeating(checker, interval=30, first=10)

    print("USDT监听机器人启动成功！正在24小时运行...")
    app.run_polling()

if __name__ == "__main__":
    main()
