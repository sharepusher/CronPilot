"""Request-owned SQLite write admission; never commits business work."""
import logging

logger = logging.getLogger(__name__)


class SQLiteBoundaryError(RuntimeError):
    """Fixed internal phases, never DB exception text for a client."""


def rollback_or_invalidate(session):
    """Keep a cleanup failure from hiding the operation's original exception."""
    try:
        session.rollback()
        return True
    except Exception:
        logger.exception('user_edit rollback failed; discarding session connections')
        try:
            session.invalidate()
        except Exception:
            logger.exception('user_edit session invalidation failed')
        return False


def begin_sqlite_write_boundary(session, models):
    """Use the business Session's connection, after its disposable read rollback.

    MySQL retains existing FOR UPDATE semantics. No SQL is sent on that path.
    The caller owns every commit/rollback and must not carry pending writes.
    """
    if not models:
        raise SQLiteBoundaryError('missing_business_models')
    engine = session.get_bind(mapper=models[0])
    if any(session.get_bind(mapper=model) is not engine for model in models[1:]):
        raise SQLiteBoundaryError('multiple_business_binds')
    if engine.dialect.name == 'mysql':
        return False
    if engine.dialect.name != 'sqlite':
        raise SQLiteBoundaryError('unsupported_business_backend')
    connection = session.connection(bind_arguments={'mapper': models[0]})
    driver = connection.connection.driver_connection
    if driver.in_transaction:
        raise SQLiteBoundaryError('physical_transaction_already_started')
    old_timeout = connection.exec_driver_sql('PRAGMA busy_timeout').scalar_one()
    if type(old_timeout) is not int or not 0 <= old_timeout <= 2147483647:
        raise SQLiteBoundaryError('invalid_busy_timeout')
    try:
        # Mark the restore obligation before executing a possibly failing SET.
        connection.exec_driver_sql('PRAGMA busy_timeout=0')
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    finally:
        try:
            # An integer read from this connection, never external SQL input.
            connection.exec_driver_sql('PRAGMA busy_timeout=%d' % old_timeout)
        except Exception:
            logger.exception('user_edit busy_timeout restore failed; discarding connection')
            try:
                session.invalidate()
            except Exception:
                logger.exception('user_edit invalidation after restore failure failed')
                try:
                    connection.invalidate()
                except Exception:
                    logger.exception('user_edit connection invalidation fallback failed')
            raise SQLiteBoundaryError('busy_timeout_restore_failed') from None
    if not driver.in_transaction:
        raise SQLiteBoundaryError('physical_write_transaction_not_started')
    return True
