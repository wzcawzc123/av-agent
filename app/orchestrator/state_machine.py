class InvalidTransition(Exception):
    pass


ALLOWED = {
    "IDLE": {"COLLECTING"},
    "COLLECTING": {"COLLECTING", "CONFIRMING"},
    "CONFIRMING": {"COLLECTING", "GENERATING"},
    "GENERATING": {"DELIVERED", "CONFIRMING"},
    "DELIVERED": {"IDLE", "COLLECTING"},
}


class ConversationState:
    def __init__(self, status: str = "IDLE"):
        self.status = status

    def transition(self, target: str):
        if target not in ALLOWED.get(self.status, set()):
            raise InvalidTransition(f"{self.status} -> {target} 不允许")
        self.status = target
