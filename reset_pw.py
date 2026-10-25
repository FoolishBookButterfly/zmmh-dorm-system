from app import create_app
app = create_app()
ctx = app.app_context()
ctx.push()
from app import db
from app.roster.models import User
u = db.session.get(User, 2)
u.set_password('testpass')
u.must_change_password = False
u.is_active = True
db.session.commit()
print('updated user 2 active')
ctx.pop()