from app.db.controller import dbController
from app.db.models import Namespace, Users, Guest, Claim, Stay

users_controller = dbController(Users)
namespace_controller = dbController(Namespace)
guest_controller = dbController(Guest)
claim_controller = dbController(Claim)
stay_controller = dbController(Stay)
