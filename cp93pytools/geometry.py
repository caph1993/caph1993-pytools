from math import pi, atan2


def clock(x: float, y: float) -> float:
    'Clock hour for ray (0,0)->(x,y), from 0.0 to 11.5999...'
    return (3 - atan2(y, x) * 6 / pi) % 12.0
