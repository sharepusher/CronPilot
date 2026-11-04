import hashlib,json,os,shutil,sqlite3,tempfile
from pathlib import Path
root=Path(tempfile.mkdtemp(prefix='cronpilot-db-assessment-',dir='/private/tmp')); os.chmod(root,0o700)
source=sqlite3.connect('file:datas/job_log.sqlite?mode=ro',uri=True)
backup=sqlite3.connect(root/'snapshot.sqlite')
source.backup(backup);backup.close();source.close()
shutil.copyfile(root/'snapshot.sqlite',root/'simulation.sqlite')
def audit(path):
 c=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)
 try:
  integrity=[r[0] for r in c.execute('pragma integrity_check')]
  names=[r[0] for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
  digests={}
  for name in names:
   quoted='"'+name.replace('"','""')+'"'
   rows=[hashlib.sha256(repr(tuple(row)).encode()).digest() for row in c.execute('select * from '+quoted+' not indexed')]
   digests[name]=(len(rows),hashlib.sha256(b''.join(sorted(rows))).hexdigest())
  schema=hashlib.sha256(repr(c.execute("select type,name,tbl_name,sql from sqlite_master order by type,name").fetchall()).encode()).hexdigest()
  return integrity,digests,schema
 finally:c.close()
before,rows_before,schema_before=audit(root/'snapshot.sqlite')
c=sqlite3.connect(root/'simulation.sqlite')
try:c.execute('REINDEX ix_apscheduler_jobs_next_run_time');c.commit()
finally:c.close()
after,rows_after,schema_after=audit(root/'simulation.sqlite')
result={'snapshot_directory':str(root),'snapshot_integrity':before,'simulation_integrity':after,'table_count':len(rows_before),'all_table_rows_identical':rows_before==rows_after,'schema_identical':schema_before==schema_after,'source_modified':False,'note':'isolated copy simulation only; no live repair or backup guarantee'}
print(json.dumps(result,ensure_ascii=False,indent=2))
