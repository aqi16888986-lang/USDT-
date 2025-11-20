import os
import time
import requests
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 从环境变量读取密钥（安全！）
TOKEN = os.getenv("BOT_TOKEN")
MORALIS_API_KEY = os.getenv("MORALIS_KEY")

# 支持的链
CHAINS = {
    "ethereum": {"name": "以太坊 ETH"},
    "bsc": {"name": "BSC BNB"},
    "tron": {"name": "波场 TRX"},
}

USDT_CONTRACTS = {
    "ethereum": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "bsc": "0x55d398326f99059ff775485a6f3bd0f4e5d4b9f",
    "tron": "TR7NHqjeKQxGTCuuP8qACi7c3iN8UQixL"
}

user_data = defaultdict(dict)

def get_chain(addr: str) -> str | None:
    addr = addr.strip().lower()
    if addr.startswith("t"): return "tron"
    if addr.startswith("0x") and len(addr) == 42: return "ethereum"
    return None

async def get_balances(address: str, chain: str):
    usdt = native = None
    try:
        # 2025 Moralis v2.2 正确端点：/wallets/{address}/tokens
        url = f"https://deep-index.moralis.io/api/v2.2/wallets/{address}/tokens"
        headers = {"X-API-Key": MORALIS_API_KEY}
        params = {"chain": chain}
        r = requests.get(url, headers=headers, params=params, timeout=12)
        if r.status_code == 200:
            data = r.json()
            for token in data:
                t_addr = token.get("token_address", "").lower()
                symbol = token.get("symbol", "").lower()
                # USDT
                if chain in USDT_CONTRACTS and t_addr == USDT_CONTRACTS[chain].lower():
                    usdt = round(float(token["balance"]) / 1_000_000, 6)
                # 原生币
                if symbol in ["eth", "bnb", "trx"]:
                    decimals = 18 if symbol != "trx" else 6
                    native = round(float(token["balance"]) / (10 ** decimals), 6)
    except Exception as e:
        print(f"API 错误: {e}")
    return usdt, native

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "USDT + 原生币监听机器人已启动！\n\n"
        "支持以太坊/BSC/波场\n"
        "发地址给我 → 监控 USDT 和 ETH/BNB/TRX\n"
        "≥1 USDT 或 ≥0.02 原生币变动立刻提醒！"
    )

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip()
    user_id = update.effective_user.id
    chain = get_chain(addr)

    if not chain:
        await update.message.reply_text("只支持 0x... (以太/BSC) 或 T... (波场) 地址")
        return

    usdt_bal, native_bal = await get_balances(addr.lower(), chain)
    if usdt_bal is None and native_bal is None:
        await update.message.reply_text("查询失败，稍后再试")
        return

    coin_name = "ETH" if chain == "ethereum" else "BNB" if chain == "bsc" else "TRX"
    user_data[user_id][addr.lower()] = {"usdt": usdt_bal or 0, "native": native_bal or 0, "chain": chain, "coin": coin_name}

    msg = f"已开始监听！\n地址：{addr}\n"
    if usdt_bal: msg += f"USDT：{usdt_bal:,}\n"
    if native_bal: msg += f"{coin_name}：{native_bal:,}"
    await update.message.reply_text(msg.strip())

async def checker(context: ContextTypes.DEFAULT_TYPE):
    for uid, addrs in list(user_data.items()):
        for addr, info in list(addrs.items()):
            new_usdt, new_native = await get_balances(addr, info["chain"])
            if new_usdt is None and new_native is None: continue

            usdt_diff = (new_usdt or 0) - info["usdt"]
            native_diff = (new_native or 0) - info["native"]

            if abs(usdt_diff) >= 1 or abs(native_diff) >= 0.02:
                alert = f"{'到账啦！！！' if usdt_diff + native_diff > 0 else '转出提醒'}\n地址：{addr}\n"
                if abs(usdt_diff) >= 1: alert += f"USDT {usdt_diff:+,}\n"
                if abs(native_diff) >= 0.02: alert += f"{info['coin']} {native_diff:+,}\n"
                alert += time.strftime('%Y-%m-%d %H:%M:%S')
                await context.bot.send_message(uid, alert)

                info["usdt"] = new_usdt or info["usdt"]
                info["native"] = new_native or info["native"]

def main():
    if not TOKEN or not MORALIS_API_KEY:
        print("错误：缺少 BOT_TOKEN 或 MORALIS_KEY 环境变量！")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.job_queue.run_repeating(checker, interval=35, first=10)
    print("USDT+原生币监听机器人启动成功！")
    app.run_polling()

if __name__ == "__main__":
    main()
