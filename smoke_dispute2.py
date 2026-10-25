from app import create_app
import re
app = create_app()
c = app.test_client()
rid = open('smoke_rec_id.txt').read().strip()
# login as user 2
r = c.get('/login')
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.get_data(as_text=True))
token = m.group(1)
r = c.post('/login', data={'username':'johanthefool01','password':'testpass','csrf_token':token}, follow_redirects=True)
# GET dispute page
r = c.get(f'/violations/dispute/{rid}')
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.get_data(as_text=True))
token = m.group(1)
# POST dispute
r = c.post(f'/violations/dispute/{rid}', data={'reason':'test dispute reason','csrf_token':token,'file_dispute':'File dispute'}, follow_redirects=True)
body = r.get_data(as_text=True)
alerts = re.findall(r'<div class="alert[^>]*>(.*?)</div>', body, re.S)
print('alerts:', alerts)
print('path:', r.request.path)
# check DB status
ctx = app.app_context()
ctx.push()
from app.violations.models import ViolationRecord, Dispute
rec = ViolationRecord.query.get(int(rid))
print('record status:', rec.status)
print('disputes:', Dispute.query.filter_by(violation_id=rec.id).count())
ctx.pop()