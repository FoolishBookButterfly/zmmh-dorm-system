from app import create_app
app = create_app()
ctx = app.app_context()
ctx.push()
from app.roster.models import User, Residency, SchoolYear
y = SchoolYear.query.filter_by(is_active=True).first()
print('year', y.id, y.label)
for u in User.query.all():
    rs = Residency.query.filter_by(person_id=u.person_id, school_year_id=y.id).all()
    print(u.id, u.username, 'residencies', [r.id for r in rs])
ctx.pop()