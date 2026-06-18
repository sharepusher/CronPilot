#!/usr/bin/env python
# coding:utf-8
import os

import click
from flask.cli import with_appcontext
from flask_migrate import (
    Migrate,
    branches,
    current,
    downgrade,
    edit,
    heads,
    history,
    init as db_init,
    merge,
    migrate as db_migrate,
    revision,
    show,
    stamp,
    upgrade,
)

from app import create_app, db

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(app, db)


def _register_db_cli(flask_app):
    @click.group()
    def db():
        """Perform database migrations"""

    @db.command('init')
    @click.option('-d', '--directory', default=None, help="Migration script directory")
    @click.option('--multidb', is_flag=True, default=False)
    @with_appcontext
    def init_cmd(directory, multidb):
        db_init(directory=directory, multidb=multidb)

    @db.command('revision')
    @click.option('-m', '--message', default=None)
    @click.option('--autogenerate', is_flag=True, default=False)
    @click.option('--sql', is_flag=True, default=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def revision_cmd(message, autogenerate, sql, directory):
        revision(directory=directory, message=message, autogenerate=autogenerate, sql=sql)

    @db.command('migrate')
    @click.option('-m', '--message', default=None)
    @click.option('--sql', is_flag=True, default=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def migrate_cmd(message, sql, directory):
        db_migrate(directory=directory, message=message, sql=sql)

    @db.command('upgrade')
    @click.argument('revision', default='head', required=False)
    @click.option('--sql', is_flag=True, default=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def upgrade_cmd(revision, sql, directory):
        upgrade(directory=directory, revision=revision, sql=sql)

    @db.command('downgrade')
    @click.argument('revision', default='-1', required=False)
    @click.option('--sql', is_flag=True, default=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def downgrade_cmd(revision, sql, directory):
        downgrade(directory=directory, revision=revision, sql=sql)

    @db.command('stamp')
    @click.argument('revision', default='head', required=False)
    @click.option('--sql', is_flag=True, default=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def stamp_cmd(revision, sql, directory):
        stamp(directory=directory, revision=revision, sql=sql)

    @db.command('current')
    @click.option('-v', '--verbose', is_flag=True, default=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def current_cmd(verbose, directory):
        current(directory=directory, verbose=verbose)

    @db.command('history')
    @click.option('-v', '--verbose', is_flag=True, default=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def history_cmd(verbose, directory):
        history(directory=directory, verbose=verbose)

    @db.command('heads')
    @click.option('-v', '--verbose', is_flag=True, default=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def heads_cmd(verbose, directory):
        heads(directory=directory, verbose=verbose)

    @db.command('branches')
    @click.option('-v', '--verbose', is_flag=True, default=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def branches_cmd(verbose, directory):
        branches(directory=directory, verbose=verbose)

    @db.command('show')
    @click.argument('revision', default='head', required=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def show_cmd(revision, directory):
        show(directory=directory, revision=revision)

    @db.command('edit')
    @click.argument('revision', default='current', required=False)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def edit_cmd(revision, directory):
        edit(directory=directory, revision=revision)

    @db.command('merge')
    @click.argument('revisions', nargs=-1)
    @click.option('-m', '--message', default=None)
    @click.option('-d', '--directory', default=None)
    @with_appcontext
    def merge_cmd(revisions, message, directory):
        merge(directory=directory, revisions=revisions, message=message)

    flask_app.cli.add_command(db)


_register_db_cli(app)
