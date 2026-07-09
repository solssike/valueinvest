import os
import asyncio
from telegram import Bot
from valueinvest import Stock, ValuationEngine

async def run_analysis():
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    bot = Bot(token=token)
    
    # 这里定义你的股票代码
    target_stocks = ["600519", "000001"] 
    results = []

    for code in target_stocks:
        try:
            print(f"正在分析: {code}...")
            # 1. 尝试获取股票
            stock = Stock.from_api(code)
            
            # 2. 尝试运行引擎
            engine = ValuationEngine()
            result = engine.run_all(stock)
            
            # 3. 检查结果是否包含有效数据
            results.append(f"✅ {code} 分析成功")
        except Exception as e:
            # 即使报错，也不会中断整个流程
            results.append(f"⚠️ {code} 分析跳过: {str(e)}")

    # 4. 发送汇总消息
    report = "\n".join(results)
    await bot.send_message(chat_id=chat_id, text=f"今日分析简报:\n{report}")

if __name__ == "__main__":
    asyncio.run(run_analysis())
