import os
import asyncio
from telegram import Bot
# 正确导入核心模块
from valueinvest import Stock, ValuationEngine

async def run_analysis():
    # 1. 初始化引擎
    engine = ValuationEngine()
    target_stocks = ["600519", "000001", "300059"] 
    
    results = []
    for code in target_stocks:
        try:
            # 2. 获取股票对象 (支持 A 股/美股自动识别)
            stock = Stock.from_api(code)
            
            # 3. 使用引擎运行分析
            # run_all 返回一个结果对象，你需要根据该库的实现格式化它
            report = engine.run_all(stock)
            results.append(f"✅ 股票 {code} ({stock.name}):\n{report}")
        except Exception as e:
            results.append(f"❌ 股票 {code} 分析失败: {str(e)}")
    
    # 4. 拼接内容
    report_content = "\n\n".join(results)
    
    # 5. 发送到 Telegram (代码保持不变)
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    bot = Bot(token=token)
    
    # 分段发送以防超长
    chunks = [report_content[i:i+4000] for i in range(0, len(report_content), 4000)]
    for chunk in chunks:
        await bot.send_message(chat_id=chat_id, text=chunk)

if __name__ == "__main__":
    asyncio.run(run_analysis())
