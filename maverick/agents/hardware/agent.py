import re

from maverick.agents.hardware import ops
from maverick.core.agent_base import Intent, Result, SubAgent

WORD_RE = re.compile(r"[a-z]+")
DRIVE_RE = re.compile(r"\b([A-Za-z]):")

SLOT_WORDS = {"slot", "slots", "dimm", "stick", "sticks"}
RAM_WORDS = {"ram", "memory"}
BATTERY_WORDS = {"battery", "charge", "charging", "charged", "plugged"}
CPU_WORDS = {"cpu", "processor", "cores", "core"}
DISK_WORDS = {"drives", "disks", "partitions", "free", "left", "remaining"}
# "copy the memory dump", "move it to the drive with space left" are file jobs, not hardware questions.
FILE_VERBS = {"copy", "move", "rename", "cut", "paste", "duplicate", "transfer"}


class HardwareAgent(SubAgent):
    name = "hardware"
    description = "RAM, RAM slots, CPU, battery and free space on drives. e.g. how much RAM do I have  |  space left on D:"

    def parse(self, text: str) -> Intent | None:
        words = set(WORD_RE.findall(text.lower()))
        if words & FILE_VERBS:
            return None
        if words & SLOT_WORDS:
            operation = "slots"
        elif words & RAM_WORDS:
            operation = "ram"
        elif words & BATTERY_WORDS:
            operation = "battery"
        elif words & CPU_WORDS:
            operation = "cpu"
        elif words & DISK_WORDS:
            operation = "disks"
        else:
            return None
        return self.extract(operation, text)

    def extract(self, operation: str, text: str) -> Intent:
        if operation == "disks":
            match = DRIVE_RE.search(text)
            return Intent("disks", {"drive": f"{match.group(1).upper()}:"} if match else {})
        return Intent(operation)  # the other questions need no details

    def handle(self, intent: Intent) -> Result:
        operation = {"ram": ops.ram, "slots": ops.slots, "cpu": ops.cpu,
                     "battery": ops.battery, "disks": ops.disks}[intent.operation]
        return operation(**intent.args)
