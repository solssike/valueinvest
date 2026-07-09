import os
import asyncio
from telegram import Bot
from valueinvest import Stock, ValuationEngine

async def run_analysis():
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    bot = Bot(token=token)
    
    target_stocks = ["AAPL", "MSFT", "600887"] 
    results = []

    for ticker in target_stocks:
        try:
            print(f"正在分析: {ticker}...")
            stock = Stock.from_api(ticker)
            
            if not stock.current_price or stock.current_price == 0:
                results.append(f"⚠️ {ticker}: 获取数据失败。")
                continue

            engine = ValuationEngine()
            analysis = engine.run_all(stock)
            
            msg = f"✅ *{stock.name} ({ticker})*\n💰 现价: {stock.current_price}"
            if hasattr(analysis, 'fair_value') and analysis.fair_value:
                msg += f"\n🎯 估值: {analysis.fair_value:.2f}"
            results.append(msg)
            
        except Exception as e:
            results.append(f"❌ {ticker} 分析异常: {str(e)}")

    message = "📊 *每日投资分析简报*\n\n" + "\n\n".join(results)
    await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

if __name__ == "__main__":
    asyncio.run(run_analysis())
