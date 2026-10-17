# app/roster/default_rooms.py -- SINGLE SOURCE OF TRUTH for the 20-room catalog (spec facts: 20 rooms, 120 beds).
# Capacities per hall records (Oct 2026): 10x4 + 4x6 + 3x8 + 2x10 + 12 = 120.
# Imported by BOTH seed_rooms.py (local shell workflow) and the /seed-rooms route (Render, no shell).
ROOMS = {
    "Cairo": 4,
    "Sydney": 4,
    "Concord": 4,
    "Boston": 4,
    "Bangkok": 4,
    "Athens": 4,
    "Beijing": 10,
    "Taipei": 6,
    "Brussels": 6,
    "Havana": 6,
    "Riyadh": 10,
    "Jakarta": 8,
    "Hongkong": 4,
    "Atlanta": 4,
    "Tokyo": 4,
    "Singapore": 8,
    "Madrid": 6,
    "Paris": 8,
    "Melbourne": 12,
    "London": 4,
}
