import os
import time
import requests
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
MORALIS_KEY = os.getenv("MORALIS_KEY")

USDT_CONTRACTS = {
    "ethereum": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "bsc": "0x55d398326f99059ff775485a6f3bd0f4e5d4b9f",
    "tron": "TR7NHqjeKQxGTCuuP8qACi7c3iN8UQixL",
}

user_data = defaultdict(dict)

def get_chain(addr: str):
    a = addr.strip().lower()
    if a.startswith("t"): return "tron"
    if a.startswith("0x") and len(a) == 42: return "ethereum"
    return None

async def get_usdt(addr: str, chain: str):
    try:
        url = f"https://deep-index.moralis.io/api/v2.2/wallets/{addr}/tokens"
        r = requests.get(url, headers={"X-API-Key": MORALIS_KEY}, params={"chain": chain}, timeout=10)
        if r.status_code == 200:
            for t in r.json():
                if t.get("token_address", "").lower() == USDT_CONTRACTS[chain].lower():
                    return round(float(t["balance"]) / 1_000_000, 6)
    except:
        pass
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("USDT监听已启动！\n发地址给我就24h监控到账")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip()
    chain = get_chain(addr)
    if not chain:
        await update.message.reply_text("只支持 0x... 或 T... 地址")
        return
    bal = await get_usdt(addr.lower(), chain)
    if bal is None:
        await update.message.reply_text("查不到，稍后再试")
        return
    user_data[update.effective_user.id][addr.lower()] = {"bal": bal, "chain": chain}
    await update.message.reply_text(f"已监听\n{addr}\n当前 {bal:,} USDT")

async def check_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    for uid, addrs in list(user_data.items()):
        for addr, info in list(addrs.items()):
            new = await get_usdt(addr, info["chain"])
            if new and abs(new - info["bal"]) >= 1:
                diff = new - info["bal"]
                await context.bot.send_message(uid,
                    f"{'到账啦！！！' if diff>0 else '转出'}\n{abs(diff):,} USDT\n{addr}\n余额 {new:,}")
                info["bal"] = new

def main():
    if not TOKEN or not MORALIS_KEY:
        print("缺少 BOT_TOKEN 或 MORALIS_KEY")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    # 关键：v21.6 必须这样写定时任务
    app.job_queue.run_repeating(callback=check_job, interval=30, first=10)

    print("=== USDT监听机器人启动成功！===")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
