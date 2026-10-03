from database import init_db, upsert_university
from datetime import datetime, timezone

SEED=[
 {'name':'National University of Singapore','country':'Singapore','country_code':'SG','city':'Singapore','website':'https://www.nus.edu.sg/','description':'A comprehensive research university in Singapore.','ranking':8,'tuition_min':18000,'tuition_max':30000,'tuition_currency':'USD','tuition_period':'year','university_type':'Public','majors':'Computer Science|Information Technology|Engineering|Business|Economics','degree_levels':'Bachelor|Master|Doctorate','source':'Seed','source_id':'nus','last_updated':datetime.now(timezone.utc).isoformat()},
 {'name':'Nanyang Technological University','country':'Singapore','country_code':'SG','city':'Singapore','website':'https://www.ntu.edu.sg/','description':'A research-intensive university with strengths in engineering, technology and business.','ranking':15,'tuition_min':17000,'tuition_max':29000,'tuition_currency':'USD','tuition_period':'year','university_type':'Public','majors':'Computer Science|Information Technology|Engineering|Business|Psychology','degree_levels':'Bachelor|Master|Doctorate','source':'Seed','source_id':'ntu','last_updated':datetime.now(timezone.utc).isoformat()},
 {'name':'University of Toronto','country':'Canada','country_code':'CA','city':'Toronto','website':'https://www.utoronto.ca/','description':'A major public research university in Toronto.','ranking':21,'tuition_min':30000,'tuition_max':55000,'tuition_currency':'USD','tuition_period':'year','university_type':'Public','majors':'Computer Science|Engineering|Business|Economics|Psychology','degree_levels':'Bachelor|Master|Doctorate','source':'Seed','source_id':'utoronto','last_updated':datetime.now(timezone.utc).isoformat()},
 {'name':'University of Melbourne','country':'Australia','country_code':'AU','city':'Melbourne','website':'https://www.unimelb.edu.au/','description':'A public research university in Melbourne, Australia.','ranking':13,'tuition_min':28000,'tuition_max':50000,'tuition_currency':'USD','tuition_period':'year','university_type':'Public','majors':'Computer Science|Information Technology|Engineering|Business|Design','degree_levels':'Bachelor|Master|Doctorate','source':'Seed','source_id':'unimelb','last_updated':datetime.now(timezone.utc).isoformat()},
 {'name':'University of Tokyo','country':'Japan','country_code':'JP','city':'Tokyo','website':'https://www.u-tokyo.ac.jp/en/','description':'Japan’s leading national research university.','ranking':28,'tuition_min':3500,'tuition_max':9000,'tuition_currency':'USD','tuition_period':'year','university_type':'Public','majors':'Computer Science|Engineering|Economics|Law|Medicine','degree_levels':'Bachelor|Master|Doctorate','source':'Seed','source_id':'utokyo','last_updated':datetime.now(timezone.utc).isoformat()},
 {'name':'University of British Columbia','country':'Canada','country_code':'CA','city':'Vancouver','website':'https://www.ubc.ca/','description':'A public research university in Vancouver and Kelowna.','ranking':38,'tuition_min':28000,'tuition_max':52000,'tuition_currency':'USD','tuition_period':'year','university_type':'Public','majors':'Computer Science|Engineering|Business|Psychology|Design','degree_levels':'Bachelor|Master|Doctorate','source':'Seed','source_id':'ubc','last_updated':datetime.now(timezone.utc).isoformat()},
]

def seed():
    init_db()
    for r in SEED: upsert_university(r)
    print('Database initialized and seed data ensured.')

if __name__=='__main__': seed()
