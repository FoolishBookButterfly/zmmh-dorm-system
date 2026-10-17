# seed_rooms.py -- Phase 1.4 Step 1: seed all 20 rooms (idempotent).
# Capacities live in app/roster/default_rooms.py -- edit THERE, both shell and /seed-rooms stay in sync.
# Run once in flask shell:  exec(open("seed_rooms.py").read())
from app import db  # commit rows (ORM handle from factory)
from app.roster.models import Room  # exact 1.1 model name -- DO NOT rename
from app.roster.default_rooms import ROOMS  # single source of truth

for name, cap in ROOMS.items():
    room = Room.query.filter_by(name=name).first()
    if room is None:
        db.session.add(Room(name=name, capacity=cap))
        print("Created:", name, cap)
    else:
        print("Exists:", name, room.capacity)

db.session.commit()
print("DONE. Rooms:", Room.query.count(), "| beds:", sum(r.capacity for r in Room.query.all()))
