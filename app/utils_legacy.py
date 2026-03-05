import numpy as np

def nan_to_none(v):
    if v is None:
        return None
    try:
        if isinstance(v, float) and np.isnan(v):
            return None
    except:
        pass
    return v


def parse_forward_value(x):

    if x is None:
        return 0

    s = str(x)

    if "/" in s:
        try:
            num, den = s.split("/")
            return float(num) * (10 / float(den))
        except:
            return 0

    try:
        return float(s)
    except:
        return 0
