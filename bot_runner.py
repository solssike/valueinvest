import os
import asyncio
from telegram import Bot
from valueinvest import Stock, ValuationEngine

async def run_analysis():
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    bot = Bot(token=token)
    
    target_stocks = ["600887", "601398"] 
    results = []

    for code in target_stocks:
        try:
            print(f"正在分析: {code}...")
            # 尝试通过 API 获取
            stock = Stock.from_api(code)
            
            # 调试：查看股票是否抓取到了价格
            print(f"DEBUG - {code} 价格属性: {stock.current_price}")
            
            if stock.current_price is None or stock.current_price == 0:
                results.append(f"⚠️ {code}: 未能获取实时价格，请检查网络数据源。")
                continue

            engine = ValuationEngine()
            analysis = engine.run_all(stock)
            
            msg = f"✅ *{stock.name} ({code})*\n"
            msg += f"💰 当前价格: ¥{stock.current_price}\n"
            results.append(msg)
            
        except Exception as e:
            results.append(f"❌ {code} 异常: {str(e)}")

    message = "📊 *今日价值投资分析简报*\n\n" + "\n".join(results)
    await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

if __name__ == "__main__":
    asyncio.run(run_analysis())
