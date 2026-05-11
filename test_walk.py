from core.config import PetConfig
from core.behavior import BehaviorController
from core.engine import PetEngine

engine = PetEngine()
bc = BehaviorController(engine)
bc._idle_since = 0
print("can_walk:", bc.can_walk())

weights = []
for i in range(100):
    weights.append(bc.choose_weighted_action())

print("walk count:", weights.count("walk_around"))
