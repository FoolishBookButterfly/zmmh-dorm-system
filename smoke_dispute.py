from app import create_app
import re
app = create_app()
c = app.test_client()
# bypass login via session
with c.session_transaction() as sess:
    sess['_user_id'] = '1'
    sess['_fresh'] = True
r = c.get('/violations/mine')
print('mine', r.status_code)
r = c.get('/violations/disputes')
print('disputes', r.status_code)