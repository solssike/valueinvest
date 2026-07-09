import os
import asyncio
from telegram import Bot
from valueinvest import Stock, ValuationEngine

async def run_analysis():
    # 初始化
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    bot = Bot(token=token)
    
    # 待分析列表 (支持 A 股和美股)
    target_stocks = ["600887", "601398"] 
    results = []

    for code in target_stocks:
        try:
            print(f"正在分析: {code}...")
            stock = Stock.from_api(code)
            engine = ValuationEngine()
            
            # 使用 run_all，并转化为字符串
            report = engine.run_all(stock)
            # 简化输出，避免复杂对象导致的格式错误
            results.append(f"✅ {stock.name}({code}) 分析完成。")
        except Exception as e:
            results.append(f"⚠️ {code} 分析失败: {str(e)}")

    # 发送汇总报告
    message = "今日价值投资分析简报:\n\n" + "\n".join(results)
    await bot.send_message(chat_id=chat_id, text=message)

if __name__ == "__main__":
    asyncio.run(run_analysis())
