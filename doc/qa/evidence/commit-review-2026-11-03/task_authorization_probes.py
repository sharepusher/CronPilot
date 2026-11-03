import sys,json,secrets
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from scripts.user_edit_sqlite_task_probe import probe
if __name__=='__main__':
 with TemporaryDirectory(prefix='cronpilot-user-boundary-') as folder:
  directory=Path(folder);run_id=secrets.token_hex(8);(directory/'.run-id').write_text(run_id)
  results=[probe(directory,mode,run_id,secrets.token_urlsafe(20)) for mode in ('DELETE','WAL')]
  print(json.dumps(results,indent=2))
