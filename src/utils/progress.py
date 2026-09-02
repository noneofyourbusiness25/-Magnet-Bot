import time
import math
from pyrogram.types import Message

class ProgressTracker:
    def __init__(self, message: Message, action: str):
        self.message = message
        self.action = action
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.update_interval = 5.0 # Update every 5 seconds to avoid FloodWait

    def _format_bytes(self, size):
        if not size:
            return "0 B"
        power = 2**10
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size > power:
            size /= power
            n += 1
        return f"{round(size, 2)} {power_labels[n]}B"

    def _format_time(self, seconds):
        if seconds == 0:
            return "0s"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        if m > 0:
            return f"{m}m {s}s"
        return f"{s}s"

    async def update(self, current, total):
        now = time.time()

        # Always update if we are done, or if the update interval has elapsed
        if current == total or (now - self.last_update_time >= self.update_interval):
            self.last_update_time = now

            elapsed = now - self.start_time
            speed = current / elapsed if elapsed > 0 else 0

            percentage = (current / total) * 100 if total > 0 else 0

            eta = (total - current) / speed if speed > 0 else 0

            progress_bar = "[{0}{1}]".format(
                ''.join(["●" for i in range(math.floor(percentage / 10))]),
                ''.join(["○" for i in range(10 - math.floor(percentage / 10))])
            )

            text = f"**{self.action}**\n\n"
            text += f"{progress_bar} {percentage:.2f}%\n"
            text += f"**Processed:** {self._format_bytes(current)} / {self._format_bytes(total)}\n"
            text += f"**Speed:** {self._format_bytes(speed)}/s\n"
            text += f"**ETA:** {self._format_time(eta)}\n"

            try:
                await self.message.edit_text(text)
            except Exception:
                # Ignore FloodWait or MessageNotModified errors here
                pass
