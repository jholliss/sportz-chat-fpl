"""
Shared manager-identity helpers.

FPL entry IDs (manager_id) are NOT a stable join key across this league's
whole history -- the group recreated their FPL entries at some point
(different manager_id before/after), and one manager legally changed
their display name for a stretch of seasons. Manager NAME is the stable
identity used everywhere: historic.json is keyed by it, and the live
pipeline resolves each season's manager_id back to a canonical name via
NAME_ALIASES before joining to historic data.
"""

# Same real person, different name at different times -> canonical name.
NAME_ALIASES = {
    "James Wiles": "James Petrie",
}


def canonical_name(name):
    name = (name or "").strip()
    return NAME_ALIASES.get(name, name)
