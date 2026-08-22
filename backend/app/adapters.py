from abc import ABC, abstractmethod
from datetime import datetime, timezone
import random

class SensorSource(ABC):
    @abstractmethod
    def pull(self, asset_id: str): ...
class MockPLC(SensorSource):
    def pull(self, asset_id): return [{"asset_id": asset_id, "tag": "bearing_temp_c", "value": round(60 + random.random() * 8, 2), "unit": "C", "recorded_at": datetime.now(timezone.utc), "source": "mock-plc"}]
class MockIoT(MockPLC):
    pass
class MockERP:
    def health_check(self): return {"status": "ok", "adapter": "mock-erp"}
    def push(self, order): return {"external_id": f"ERP-{order.id[:8]}", "status": "accepted"}
