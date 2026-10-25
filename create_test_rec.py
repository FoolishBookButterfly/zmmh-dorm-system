from app import create_app
from datetime import date
app = create_app()
ctx = app.app_context()
ctx.push()
from app import db
from app.violations.models import ViolationRule, ViolationRecord
from app.roster.models import Semester
sem = Semester.query.filter_by(is_active=True).first()
rule = ViolationRule.query.filter_by(is_active=True).first()
rec = ViolationRecord(rule_id=rule.id, residency_id=2, semester_id=sem.id, reporter_id=1,
                      date=date.today(), status="Logged", offense_count=1, fine_amount=0)
db.session.add(rec)
db.session.commit()
print('created record', rec.id)
ctx.pop()
# save id to file
with open('smoke_rec_id.txt','w') as f:
    f.write(str(rec.id))