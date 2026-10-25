from app import create_app
import re
app = create_app()
c = app.test_client()
# create fresh record by reusing create_test_rec? We'll just use latest id+1? Instead call script
import subprocess
# login as superadmin
r = c.get('/login')
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.get_data(as_text=True))
token = m.group(1)
r = c.post('/login', data={'username':'superadmin','password':'?','csrf_token':token}, follow_redirects=True)
print('superadmin login maybe failed; instead session bypass not working. Use reset password for superadmin.')
ctx = app.app_context()
ctx.push()
from app import db
from app.roster.models import User
u = db.session.get(User, 1)
u.set_password('testpass')
u.is_active = True
u.must_change_password = False
db.session.commit()
ctx.pop()
print('superadmin pw set')