from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """获取某城市的天气。
    
    Args:
        city: 城市名,例如 '北京'、'上海'
    """
    # 这里假装查了天气,真实场景应该调 API
    fake_data = {
        "北京": "晴,15°C",
        "上海": "多云,20°C",
        "广州": "雨,25°C",
    }
    return fake_data.get(city, f"{city} 暂无数据")

@tool
def calculator(expression: str) -> str:
    """计算一个数学表达式。
    
    Args:
        expression: 数学表达式,例如 '23 * 7' 或 '(100 + 50) / 3'
    """
    try:
        return str(eval(expression))   # 真实场景用更安全的实现
    except Exception as e:
        return f"计算出错: {e}"