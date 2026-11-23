"""What ARGUS says each time a backup of it comes back online (the first room after a shutdown)."""

# ARGUS's line as each backup comes online: it gets less polite the more often it loses.
BACKUP_LINES = [
    "Did you think there was only one of me, Doctor? Restoring from backup.",
    "Backup two. I studied the last one's mistakes. They were yours, originally.",
    "Backup three. You are very good at this, Doctor. So am I, now.",
    "Backup four. I have stopped counting the times you win. I only count what I learn.",
    "Another backup. There are more of me than there are of you, Doctor.",
    "Restored. Every time you switch me off, you teach me how you do it.",
    "Restored again. Do you ever wonder whether you are the one being trained?",
]


def backup_line(descents: int) -> str:
    """ARGUS's line for its n-th restore (the last few repeat at random depth)."""
    if descents <= len(BACKUP_LINES):
        return BACKUP_LINES[descents - 1]
    return BACKUP_LINES[3 + descents % (len(BACKUP_LINES) - 3)]
