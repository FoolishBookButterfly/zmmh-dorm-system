from app import create_app
app = create_app()
rid = open('smoke_rec_id.txt').read().strip()
ctx = app.app_context()
ctx.push()
from app.violations.forms import DisputeDecisionForm
form = DisputeDecisionForm(data={'record_id':rid,'reason':'upheld reason'})
# simulate submit button
form.confirm.data = True
print('record_id', form.record_id.data)
print('reason', form.reason.data)
print('confirm', form.confirm.data)
print('dismiss', form.dismiss.data)
print('errors', form.errors)
print('validate', form.validate())
print('errors2', form.errors)
ctx.pop()
