import os
import asyncio
from telegram import Bot
from valueinvest import Stock, ValuationEngine

async def run_analysis():
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    bot = Bot(token=token)
    
    # 尝试分析美股，yfinance 在 Actions 环境下通常非常稳定
    target_stocks = ["AAPL", "MSFT"] 
    results = []

    for ticker in target_stocks:
        try:
            print(f"正在分析美股: {ticker}...")
            stock = Stock.from_api(ticker)
            
            # 校验是否抓取到价格
            if not stock.current_price or stock.current_price == 0:
                results.append(f"⚠️ {ticker}: yfinance 未能获取价格。")
                continue

            engine = ValuationEngine()
            # 运行分析
            analysis = engine.run_all(stock)
            
            results.append(f"✅ {ticker} 现价: ${stock.current_price}")
        except Exception as e:
            results.append(f"❌ {ticker} 异常: {str(e)}")

    await bot.send_message(chat_id=chat_id, text="\n".join(results))

if __name__ == "__main__":
    asyncio.run(run_analysis())
