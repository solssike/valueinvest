from valueinvest import Stock, ValuationEngine
import sys

def safe_analyze(ticker):
    try:
        stock = Stock.from_api(ticker)
        engine = ValuationEngine()
        # 只运行不会报错的特定方法，或者手动处理空结果
        result = engine.run_all(stock)
        
        # 手动检查结果是否为空
        if not hasattr(result, 'fair_values') or not result.fair_values:
            return f"股票 {ticker} 未能计算出估值数据（可能是数据缺失）"
            
        return str(result)
    except Exception as e:
        return f"分析 {ticker} 时出错: {str(e)}"

# 你的 Telegram 发送逻辑...
