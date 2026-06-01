# Third-Party Notices

CronPilot bundles or depends on the following open source components.
Versions match `requirements.txt` at release time. Regenerate with:

```bash
pip install pip-licenses
pip-licenses --format=markdown --with-urls --order=license
```

## Python dependencies (direct)

| Component | Version (pinned) | License (SPDX / PyPI) |
|-----------|------------------|------------------------|
| APScheduler | 3.6.3 | MIT |
| Flask | 1.1.2 | BSD-3-Clause |
| Flask-APScheduler | 1.11.0 | Apache-2.0 |
| Flask-Migrate | 2.5.3 | MIT |
| Flask-Script | 2.0.6 | BSD-3-Clause |
| Flask-SQLAlchemy | 2.4.4 | BSD-3-Clause |
| Jinja2 | 2.11.2 | BSD-3-Clause |
| SQLAlchemy | 1.3.19 | MIT |
| Werkzeug | 1.0.1 | BSD-3-Clause |
| gevent | 20.9.0 | MIT |
| gunicorn | 20.0.4 | MIT |
| requests | 2.24.0 | Apache-2.0 |
| urllib3 | 1.25.10 | MIT |
| redis | 3.5.3 | MIT |
| PyMySQL | 0.10.1 | MIT |
| alembic | 1.4.3 | MIT |
| click | 7.1.2 | BSD-3-Clause |
| itsdangerous | 1.1.0 | BSD-3-Clause |
| MarkupSafe | 1.1.1 | BSD-3-Clause |
| python-dateutil | 2.8.1 | Apache-2.0 / BSD |
| pytz | 2020.1 | MIT |
| certifi | 2020.6.20 | MPL-2.0 |
| chardet | 3.0.4 | LGPL-2.1+ (see note) |
| zope.interface | 5.1.0 | ZPL-2.1 |
| zope.event | 4.5.0 | ZPL-2.1 |
| portalocker | 2.6.0 | BSD-3-Clause |
| openpyxl | 2.4.11 | MIT |
| records | 0.5.3 | ISC |
| docopt | 0.6.2 | MIT |
| six | 1.15.0 | MIT |
| tablib | 2.0.0 | MIT |
| tzlocal | 2.1 | MIT |
| cffi | 1.15.1 | MIT |
| pycparser | 2.21 | BSD-3-Clause |
| greenlet | 0.4.17 | MIT |
| idna | 2.10 | BSD-3-Clause (Unicode) |
| Mako | 1.1.3 | MIT |
| et-xmlfile | 1.0.1 | MIT |
| jdcal | 1.4.1 | BSD |
| python-editor | 1.0.4 | Apache-2.0 |

**Note on chardet:** Transitive dependency of `requests`. LGPL-2.1+ may impose
additional obligations if you distribute modified versions or embed statically;
consult legal counsel for commercial redistribution.

**Note on certifi (MPL-2.0):** Mozilla Public License 2.0 applies to certifi
files; modifications to those files must be shared under MPL-2.0.

## Bundled frontend assets (`app/static/`)

| Component | Location | Typical license |
|-----------|----------|-----------------|
| jQuery | `js/jquery.js` | MIT |
| Vue.js | `vue.js` | MIT |
| Bootstrap | `js/bootstrap.min.js`, CSS | MIT |
| Font Awesome | `js/simpleboot/font-awesome/` | SIL OFL 1.1 / MIT (icons) |
| artDialog | `js/artDialog/` | Check upstream (legacy) |
| noty | `js/noty/` | MIT |

A full attribution file for vendored JS/CSS is recommended in a future release
(copy license headers from each vendor into `app/static/NOTICE-frontend.txt`).

## Documentation references (not shipped as code)

| Project | License | Use |
|---------|---------|-----|
| Plombery (lucafaggianelli/plombery) | MIT | Comparative analysis in `doc/` only |

## Container base image

`Dockerfile` uses `ubuntu:16.04`, subject to Ubuntu/Canonical terms. Image is
EOL; upgrade to a supported LTS for security and compliance.
