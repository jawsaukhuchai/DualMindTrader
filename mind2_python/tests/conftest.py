# mind2_python/tests/conftest.py
import inspect
from datetime import datetime
import pytest
from mind2_python.schema import TradeEntry

def make_entry(**overrides):
    """
    Universal factory for TradeEntry:
    - Inspects dataclass fields dynamically
    - Fills sensible defaults if not provided
    - Allows override via kwargs
    """
    fields = TradeEntry.__dataclass_fields__

    defaults = {}
    for name, field in fields.items():
        if name in overrides:
            defaults[name] = overrides[name]
            continue

        if field.default is not inspect._empty:
            defaults[name] = field.default
        elif field.default_factory is not inspect._empty:  # type: ignore
            defaults[name] = field.default_factory()
        else:
            if name == "symbol":
                defaults[name] = "XAUUSDc"
            elif name == "bid":
                defaults[name] = 2000.0
            elif name == "ask":
                defaults[name] = 2001.0
            elif name == "spread":
                defaults[name] = 1.0
            elif name == "filters":
                defaults[name] = {}
            elif name == "timeframes":
                defaults[name] = {}
            elif name == "timestamp":
                defaults[name] = datetime.utcnow().isoformat()
            else:
                defaults[name] = None

    return TradeEntry(**defaults)

# fixture เดิมของคุณก็ยังอยู่
from mind2_python.position_manager import PositionManager

@pytest.fixture
def pmgr():
    inst = PositionManager._instance()
    inst.state = {"positions": {}, "orders_count": {}, "last_order_time": {}}
    return inst
