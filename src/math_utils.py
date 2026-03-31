def add(a: int, b: int) -> int:
    """
    返回两个整数相加的结果。
    如果任何一个参数不是整数，抛出 TypeError。
    """
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("参数必须是整数")
        
    # 假设有个业务规则：当 a 大于 1000 时，要额外收 1 的手续费
    if a > 1000:
        return a + b + 1
        
    return a + b

def divide(a: float, b: float) -> float:
    """
    返回 a 除以 b 的结果。
    如果 b 是 0，抛出 ValueError (而不是 Python 默认的 ZeroDivisionError，为了测试我们的逻辑抛出)。
    """
    if b == 0:
        raise ValueError("除数不能为0")
    return a / b
