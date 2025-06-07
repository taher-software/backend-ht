from src.app.db.controller import dbController
from src.app.db.models import Namespace, Users, Guest, Claim, Stay, NamespaceSettings

users_controller = dbController(Users)
namespace_controller = dbController(Namespace)
guest_controller = dbController(Guest)
claim_controller = dbController(Claim)
stay_controller = dbController(Stay)
settings_controller = dbController(NamespaceSettings)
