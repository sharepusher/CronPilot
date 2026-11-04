import importlib.util,json,subprocess,tarfile
from pathlib import Path
from collections import Counter
from jinja2 import Environment,TemplateSyntaxError
root=Path.cwd()
spec=importlib.util.spec_from_file_location('builder',root/'scripts/build_release_asset.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
spec2=importlib.util.spec_from_file_location('checker',root/'scripts/check_release_asset.py');c=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(c)
p=Path('/private/tmp/cronpilot-v420-blocked-07dddb3/cronpilot-4.2.0.tar.gz')
r=json.loads(p.with_suffix(p.suffix+'.build.json').read_text())
rewrites=Counter(x['source_path'] for x in r['link_rewrites'])
summary={'archive_commit':r['source_commit'],'rewrite_total':len(r['link_rewrites']),'rewrite_counts':dict(sorted(rewrites.items())),'protected_files_changed':[],'source_template_parse_errors':[],'archive_template_parse_errors':[],'templates_checked':0,'protected_count':0}
e=Environment()
with tarfile.open(p) as t:
 for f in r['files']:
  name=f['path'];packed=t.extractfile(r['top_level_directory']+'/'+name).read();raw=subprocess.check_output(['git','cat-file','blob',f['source_object']])
  is_doc=(name.startswith('doc/') or ('/' not in name and name.lower().endswith('.md')))
  if not is_doc:
   summary['protected_count']+=1
   if packed!=raw:summary['protected_files_changed'].append(name)
  if name.startswith('app/templates/') and name.endswith('.html'):
   summary['templates_checked']+=1
   for data,key in ((raw,'source_template_parse_errors'),(packed,'archive_template_parse_errors')):
    try:e.parse(data.decode())
    except TemplateSyntaxError as err:summary[key].append({'path':name,'error':str(err),'line':err.lineno})
print(json.dumps(summary,ensure_ascii=False,indent=2))
selected={'README.md','doc/index.html','doc/retained.html'};tree=selected|{'doc/hidden.html','doc/a\'b.html','app/templates/redesign/sample.html'}
probes=[]
for source,text in [('app/templates/redesign/sample.html','<a href="?page={{ p }}&outcome={{ outcome }}{% if keywords.get(\'task_name\') %}&task_name={{ keywords.task_name }}{% endif %}">x</a>'),('doc/index.html','<a href="?page=2">x</a>'),('doc/index.html','<a href="#here">x</a>'),('doc/index.html','<a href="hidden.html#here">x</a>'),('doc/index.html','<a href="retained.html">x</a>'),('doc/index.html','<a href="a\'b.html">x</a>')]:
 out,rew=m.rewrite_links(source,text.encode(),selected,tree,'https://example.test/repo','testref')
 probes.append({'source':source,'input':text,'output':out.decode(),'rewrite_count':len(rew),'checker_target':c.normalize_target(source,text.split('href="')[1].split('"')[0])})
print('PROBES',json.dumps(probes,ensure_ascii=False,indent=2))
Path('/private/tmp/cronpilot-template-analysis-results.json').write_text(json.dumps({'archive':summary,'probes':probes},ensure_ascii=False,indent=2)+'\n')
