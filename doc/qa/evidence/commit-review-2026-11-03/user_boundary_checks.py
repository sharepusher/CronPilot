import sys,json,secrets
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from scripts.verify_user_edit_sqlite_boundary import business_case
if __name__=='__main__':
 with TemporaryDirectory(prefix='cronpilot-user-boundary-') as folder:
  directory=Path(folder);run_id=secrets.token_hex(8);(directory/'.run-id').write_text(run_id)
  results=[business_case(directory,mode,case,run_id,secrets.token_urlsafe(20)) for mode in ('DELETE','WAL') for case in ('save_first_role','same_field_before')]
  print(json.dumps(results,indent=2))
