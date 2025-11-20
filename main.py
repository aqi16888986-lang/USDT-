import os
import time
import requests
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = 8281468920:AAFWL19Xu7sqksA2amh8E_Q5V9_PzGofvGM
MORALIS_API_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6IjU5NjM5ZTI1LWY0NTItNGFmZi04OWNlLWI1OWUyYTcyYTA0MCIsIm9yZ0lkIjoiNDgyMjgzIiwidXNlcklkIjoiNDk2MTc3IiwidHlwZUlkIjoiZTk5MDQ0NzItMzVmNS00YmEzLTgxZTMtYTBiZDFkZTJmMmFkIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE3NjM2Mjc4MzIsImV4cCI6NDkxOTM4NzgzMn0.RthpevketkJhTRQlMSGykTl7QjBARyCDhLTJA05SeQ0

# 支持的链和原生币
CHAINS = {
    "ethereum": {"name": "以太坊 ETH", "native": "ethereum"},
    "bsc":      {"name": "币安链 BNB", "native": "binancecoin"},
    "tron":     {"name": "波场 TRX", "native": "tron"},
    "bitcoin":  {"name": "比特币 BTC", "native": "bitcoin"}
}

# USDT 合约地址（只有这三种链有 USDT）
USDT_CONTRACTS = {
    "ethereum": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "bsc":      "0x55d398326f99059ff775485a6f3bd0f4e5d4b9f",
    "tron":     "TR7NHqjeKQxGTCuuP8qACi7c3iN8UQixL"
}

user_data = defaultdict(dict)   # {user_id: {addr: {bal_usdt, bal_native, chain}}}

def get_chain(addr: str) -> str:
    if addr.startswith("T"): return "tron"
    if addr.startswith("0x"): return "ethereum" if len(addr) == 42 else None
    if addr.startswith(("1", "3", "bc1")): return "bitcoin"
    return None

async def get_balances(address: str, chain: str):
    usdt_bal = native_bal = None
    try:
        # Moralis 获取所有代币余额（包含 USDT 和原生币）
        url = f"https://deep-index.moralis.io/api/v2.2/wallet/{address}/tokens/balances"
        headers = {"X-API-Key": MORALIS_API_KEY}
        params = {"chain": chain if chain != "bitcoin" else "bitcoin"}
        r = requests.get(url, headers=headers, params=params, timeout=12)
        if r.status_code == 200:
            data = r.json()
            for token in data:
                addr_lower = token.get("token_address_address", "").lower()
                if chain in USDT_CONTRACTS and addr_lower == USDT_CONTRACTS[chain].lower():
                    usdt_bal = round(float(token["balance"]) / 1_000_000, 6)
                if token.get("symbol", "").lower() in ["eth", "bnb", "trx"]:
                    native_bal = round(float(token["balance"]) / 1e18 if chain != "tron" else float(token["balance"]) / 1e6, 6)
    except: pass
    return usdt_bal, native_bal

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "三币监听机器人已启动！\n\n"
        "支持同时监控：USDT + ETH/BNB/TRX + BTC\n"
        "直接发任意地址给我（支持以太/波场/BSC/比特币地址），\n"
        "有 ≥1 USDT 或 ≥0.02 ETH 或 ≥0.001 BTC 变动立刻提醒！"
    )

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip()
    user_id = update.effective_user.id
    chain = get_chain(addr)
    
    if not chain:
        await update.message.reply_text("不支持的地址格式～")
        return

    usdt_bal, native_bal = await get_balances(addr.lower(), chain)
    if usdt_bal is None and native_bal is None:
        await update.message.reply_text("查询失败，稍后再试")
        return

    user_data[user_id][addr.lower()] = {
        "usdt": usdt_bal or 0,
        "native": native_bal or 0,
        "chain": chain,
        "name": CHAINS[chain]["name"]
    }

    msg = f"已开始监听 {CHAINS[chain]['name']} 地址！\n{addr}\n"
    if usdt_bal: msg += f"USDT 余额：{usdt_bal:,} \n"
    if native_bal: msg += f"{CHAINS[chain]['name'].split()[1]} 余额：{native_bal:,}"
    await update.message.reply_text(msg.strip())

async def checker(context: ContextTypes.DEFAULT_TYPE):
    for uid, addrs in list(user_data.items()):
        for addr, info in list(addrs.items()):
            new_usdt, new_native = await get_balances(addr, info["chain"])
            if new_usdt is None and new_native is None: continue

            usdt_diff = (new_usdt or 0) - info["usdt"] if new_usdt else 0
            native_diff = (new_native or 0) - info["native"] if new_native else 0

            if abs(usdt_diff) >= 1 or abs(native_diff) >= (0.02 if info["chain"] != "bitcoin" else 0.001):
                alert = f"{'到账啦！！！' if usdt_diff + native_diff > 0 else '转出提醒'}\n地址：{addr}\n"
                if abs(usdt_diff) >= 1:
                    alert += f"USDT 变动：{usdt_diff:+,} \n"
                if abs(native_diff) >= 0.001:
                    coin = "BTC" if info["chain"] == "bitcoin" else info["name"].split()[1]
                    alert += f"{coin} 变动：{native_diff:+,} \n"
                alert += f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
                await context.bot.send_message(uid, alert)
                
                info["usdt"] = new_usdt or info["usdt"]
                info["native"] = new_native or info["native"]

def main():
    if not TOKEN or not MORALIS_API_KEY:
        print("缺少密钥！")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.job_queue.run_repeating(checker, interval=35, first=10)
    print("USDT+ETH+BTC三币监听机器人启动成功！")
    app.run_polling()

if __name__ == "__main__":
    main()
