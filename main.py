import os
import time
import requests
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 从环境变量读取密钥（Railway 自动注入）
TOKEN = os.getenv("BOT_TOKEN")
MORALIS_API_KEY = os.getenv("MORALIS_KEY")

# USDT 合约地址
USDT_CONTRACTS = {
    "ethereum": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "tron": "TR7NHqjeKQxGTCuuP8qACi7c3iN8UQixL",
    "bsc": "0x55d398326f99059ff775485a6f3bd0f4e5d4b9f",
}

user_data = defaultdict(dict)

def get_chain(addr: str) -> str:
    return "tron" if addr.startswith("T") else "ethereum"

async def get_balance(address: str, chain: str):
    contract = USDT_CONTRACTS.get(chain, USDT_CONTRACTS["ethereum"])
    try:
        # 2025 Moralis v2.2 最新端点
        url = f"https://deep-index.moralis.io/api/v2.2/wallet/{address}/tokens/balances"
        headers = {"X-API-Key": MORALIS_API_KEY}
        params = {"chain": chain}
        r = requests.get(url, headers=headers, params=params, timeout=12)
        if r.status_code == 200:
            data = r.json()
            for token in data:
                if token.get("token_address", "").lower() == contract.lower():
                    return round(float(token["balance"]) / 1_000_000, 6)
    except Exception as e:
        print(f"Moralis API 错误: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "USDT 到账监听机器人已启动！\n\n"
        "直接发 USDT 地址给我（支持以太坊/BSC/波场），\n"
        "我会 24h 监控，≥1 USDT 变动立刻提醒！"
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
        await update.message.reply_text("查询失败，稍后再试～")
        return

    user_data[user_id][addr] = {"bal": bal, "chain": chain}
    await update.message.reply_text(
        f"已开始监听！\n"
        f"地址：{addr}\n"
        f"当前余额：{bal:,} USDT\n"
        f"有变动我马上通知！"
    )

async def checker(context: ContextTypes.DEFAULT_TYPE):
    for uid, addrs in list(user_data.items()):
        for addr, info in list(addrs.items()):
            new_bal = await get_balance(addr, info["chain"])
            if new_bal is not None and abs(new_bal - info["bal"]) >= 1:
                diff = new_bal - info["bal"]
                await context.bot.send_message(
                    uid,
                    f"{'🚨 到账啦！' if diff > 0 else '💸 转出提醒'}\n"
                    f"金额：{abs(diff):,} USDT\n"
                    f"地址：{addr}\n"
                    f"最新余额：{new_bal:,} USDT\n"
                    f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                info["bal"] = new_bal

def main():
    if not TOKEN or not MORALIS_API_KEY:
        print("错误：缺少 BOT_TOKEN 或 MORALIS_KEY！请检查 Railway Variables。")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.job_queue.run_repeating(checker, interval=30, first=10)

    print("USDT监听机器人启动成功！正在24小时运行...")
    app.run_polling()

if __name__ == "__main__":
    main()
