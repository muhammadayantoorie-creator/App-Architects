"""No routes: importing this module registers the demo seed hook and its model
before the application creates tables and seeds the baseline."""

from backend.modules.demo import models as _demo_models  # noqa: F401
from backend.modules.demo import seed as _demo_seed  # noqa: F401
