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
            stock = Stock.from_api(code)
            engine = ValuationEngine()
            
            # 运行分析
            # run_all 通常返回一个 AnalysisResult 对象
            analysis = engine.run_all(stock)
            
            # 提取关键数据 (根据库的通用设计，通常包含这些属性)
            # 如果你在运行时发现某些属性不存在，可以尝试打印 dir(analysis) 来查看所有可用属性
            price = stock.current_price
            # 尝试从分析结果中获取 Graham 或 DCF 估值
            # 假设 analysis.details 存储了不同方法的评估结果
            msg = f"✅ *{stock.name} ({code})*\n"
            msg += f"💰 当前价格: ¥{price}\n"
            
            # 尝试提取估值摘要
            if hasattr(analysis, 'fair_value'):
                msg += f"🎯 公允价值: ¥{analysis.fair_value:.2f}\n"
            if hasattr(analysis, 'upside_pct'):
                msg += f"📈 潜在空间: {analysis.upside_pct:+.1%}\n"
            
            results.append(msg)
            
        except Exception as e:
            results.append(f"⚠️ {code} 分析失败: {str(e)}")

    # 发送汇总报告
    message = "📊 *今日价值投资分析简报*\n\n" + "\n".join(results)
    
    # 使用 Markdown 格式发送
    await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

if __name__ == "__main__":
    asyncio.run(run_analysis())
