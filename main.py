import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
from collections import defaultdict
import time
import os

# ===== 直接把你的两个东西粘下面 =====
TOKEN = 8281468920:AAFWL19Xu7sqksA2amh8E_Q5V9_PzGofvGM 会自动读取
MORALIS_API_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6IjU5NjM5ZTI1LWY0NTItNGFmZi04OWNlLWI1OWUyYTcyYTA0MCIsIm9yZ0lkIjoiNDgyMjgzIiwidXNlcklkIjoiNDk2MTc3IiwidHlwZUlkIjoiZTk5MDQ0NzItMzVmNS00YmEzLTgxZTMtYTBiZDFkZTJmMmFkIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE3NjM2Mjc4MzIsImV4cCI6NDkxOTM4NzgzMn0.RthpevketkJhTRQlMSGykTl7QjBARyCDhLTJA05SeQ0)
# =====================================

USDT_CONTRACTS = {
    "ethereum": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "tron": "TR7NHqjeKQxGTCuuP8qACi7c3iN8UQixL",
    "bsc": "0x55d398326f99059ff775485a6f3bd0f4e5d4b9f",
}

user_data = defaultdict(dict)

def get_chain(addr):
    return "tron" if addr.startswith('T') else "ethereum"

async def get_balance(address, chain):
    contract = USDT_CONTRACTS.get(chain, USDT_CONTRACTS["ethereum"])
    try:
        url = f"https://deep-index.moralis.io/api/v2.2/wallets/{address}/erc20"
        headers = {"X-API-Key": MORALIS_API_KEY}
        params = {"chain": chain, "token_addresses": [contract]}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        if data and len(data) > 0:
            return round(float(data[0]["balance"]) / 1000000, 6)
    except:
        pass
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("USDT到账监听机器人已启动！\n发地址给我就行")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip()
    user_id = update.effective_user.id
    if len(addr) < 30:
        await update.message.reply_text("这不像地址")
        return
    chain = get_chain(addr)
    bal = await get_balance(addr.lower(), chain)
    if bal is None:
        await update.message.reply_text("添加失败")
        return
    user_data[user_id][addr.lower()] = {"bal": bal, "chain": chain}
    await update.message.reply_text(f"已监听：{addr}\n余额：{bal:,} USDT")

async def checker(context: ContextTypes.DEFAULT_TYPE):
    for uid, addrs in list(user_data.items()):
        for addr, info in list(addrs.items()):
            new_bal = await get_balance(addr, info["chain"])
            if new_bal and abs(new_bal - info["bal"]) >= 1:
                diff = new_bal - info["bal"]
                await context.bot.send_message(uid, 
                    f"{'到账' if diff>0 else '转出'} {abs(diff):,} USDT！\n地址：{addr}\n现余额：{new_bal:,}")
                info["bal"] = new_bal

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.job_queue.run_repeating(checker, interval=30, first=10)
    print("USDT监听机器人启动成功！")
    app.run_polling()

if __name__ == "__main__":
    main()
