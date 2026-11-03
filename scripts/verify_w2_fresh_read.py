"""D0：隔离数据库验证独立连接的新鲜读取不提交/刷新调用者事务。"""
import json
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import Integer, create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Probe(Base):
    __tablename__ = 'fresh_read_probe'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)


def verify(url):
    engine = create_engine(url)
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(Probe.__table__.insert().values(id=1, revision=0))
        with Session(engine) as caller:
            old = caller.get(Probe, 1)
            assert old.revision == 0
            with engine.begin() as other:
                other.execute(Probe.__table__.update().where(Probe.id == 1).values(revision=1))
            assert caller.get(Probe, 1).revision == 0  # identity map 不是最新事实
            pending = Probe(id=2, revision=5)
            caller.add(pending)
            with engine.connect() as fresh:
                assert fresh.scalar(select(Probe.revision).where(Probe.id == 1)) == 1
                assert fresh.scalar(select(Probe.id).where(Probe.id == 2)) is None
            assert pending in caller.new
            assert caller.in_transaction()
            caller.rollback()
        return {'identity_map_stale': True, 'independent_read_current': True,
                'caller_pending_work_untouched': True}
    finally:
        engine.dispose()


def main():
    result = {}
    with tempfile.TemporaryDirectory(prefix='cronpilot-d0-fresh-') as directory:
        result['sqlite'] = verify('sqlite:///' + str(Path(directory) / 'probe.sqlite'))
    server_url = make_url('mysql+pymysql://root@127.0.0.1:33089/?charset=utf8mb4')
    server = create_engine(server_url)
    name = 'cronpilot_d0_' + uuid.uuid4().hex
    created = False
    try:
        with server.begin() as connection:
            connection.execute(text('CREATE DATABASE `%s`' % name))
            created = True
        result['mysql'] = verify(server_url.set(database=name))
    finally:
        if created:
            with server.begin() as connection:
                connection.execute(text('DROP DATABASE `%s`' % name))
        server.dispose()
    result['isolated_cleanup'] = True
    print(json.dumps(result))


if __name__ == '__main__':
    main()
