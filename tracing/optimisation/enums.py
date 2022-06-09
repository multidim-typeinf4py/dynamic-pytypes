import enum

class TriggerStatus(enum.Enum):
    INACTIVE = 0
    ENTRY = 1
    ONGOING = 2
    EXITED = 3
