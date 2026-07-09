import os
import asyncio
from telegram import Bot
from valueinvest import Stock, ValuationEngine

# 强制设置 Token (从 GitHub Secrets 获取)
os.environ["TUSHARE_TOKEN"] = os.getenv("TUSHARE_TOKEN", "")

async def run_analysis():
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    bot = Bot(token=token)
    
    target_stocks = ["600887", "601398"] 
    results = []

    for code in target_stocks:
        try:
            # 此时 Stock.from_api 会优先使用 Tushare
            stock = Stock.from_api(code)
            
            if not stock.current_price:
                results.append(f"⚠️ {code}: 无法通过 Tushare 获取数据，请检查 Token 积分是否充足。")
                continue

            engine = ValuationEngine()
            analysis = engine.run_all(stock)
            
            results.append(f"✅ {stock.name}({code}) 现价: {stock.current_price}")
        except Exception as e:
            results.append(f"❌ {code} 分析异常: {str(e)}")

    await bot.send_message(chat_id=chat_id, text="\n".join(results))

if __name__ == "__main__":
    asyncio.run(run_analysis())
