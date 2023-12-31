import sqlite3

from .setup import LOGGER
from .constants import TASK_KEYS, SCAN_MODE_KEYS


def migrate_schedule(ver: str, table, cs: sqlite3.Cursor) -> None:
    migrations = {
        '1': migrate_schedule_v2,
        '2': migrate_schedule_v3,
        '3': migrate_schedule_v4,
        '4': migrate_schedule_v5,
        '5': migrate_schedule_v6,
        '6': migrate_schedule_v7,
    }
    migrations.get(ver, migrate_schedule_v1)(cs, table)

def migrate_setting(ver: str, table, cs: sqlite3.Cursor) -> None:
    migrations = {
        '1': migrate_setting_v2,
        '2': migrate_setting_v3,
    }
    migrations.get(ver, migrate_setting_v1)(cs, table)


def migrate_schedule_v1(cs: sqlite3.Cursor, table: str) -> None:
    LOGGER.warning(f'DB 버전 확인 필요')


def migrate_schedule_v2(cs: sqlite3.Cursor, table: str) -> None:
    LOGGER.debug('DB 버전 2 로 마이그레이션')
    # check old table
    old_table_rows = cs.execute(f"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='job'").fetchall()
    if old_table_rows[0]['count(*)']:
        LOGGER.debug('old table exists!')
        cs.execute(f'ALTER TABLE "job" RENAME TO "job_OLD_TABLE"')
        new_table_rows = cs.execute(f"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='{table}'").fetchall()
        if new_table_rows[0]['count(*)']:
            # drop new blank table
            LOGGER.debug('new blank table exists!')
            cs.execute(f'DROP TABLE {table}')
        # rename table
        cs.execute(f'ALTER TABLE "job_OLD_TABLE" RENAME TO "{table}"')

        # add/drop columns
        rows = cs.execute(f'SELECT name FROM pragma_table_info("{table}")').fetchall()
        cols = [row['name'] for row in rows]
        if 'commands' in cols:
            cs.execute(f'ALTER TABLE "{table}" DROP COLUMN "commands"')
        if 'scan_mode' not in cols:
            cs.execute(f'ALTER TABLE "{table}" ADD COLUMN "scan_mode" VARCHAR')
        if 'periodic_id' not in cols:
            cs.execute(f'ALTER TABLE "{table}" ADD COLUMN "periodic_id" INTEGER')

        # check before seting values
        rows = cs.execute(f'SELECT name FROM pragma_table_info("{table}")').fetchall()
        cols = [row['name'] for row in rows]
        LOGGER.debug(f'table cols: {cols}')
        rows = cs.execute(f'SELECT * FROM "{table}"').fetchall()
        for row in rows:
            LOGGER.debug(f"{row['id']} | {row['ctime']} | {row['task']} | {row['desc']} | {row['target']} | {row['scan_mode']} | {row['periodic_id']}")

        LOGGER.debug('========== set values ==========')

        # set values
        rows = cs.execute(f'SELECT * FROM "{table}"').fetchall()
        for row in rows:
            if not row['scan_mode']:
                cs.execute(f'UPDATE {table} SET scan_mode = "plexmate" WHERE id = {row["id"]}')
            if not row['periodic_id']:
                cs.execute(f'UPDATE {table} SET periodic_id = -1 WHERE id = {row["id"]}')

            if row['task'] == 'refresh':
                pass
            elif row['task'] == 'scan':
                # Plex Web API로 스캔 요청
                cs.execute(f'UPDATE {table} SET scan_mode = "web" WHERE id = {row["id"]}')
            elif row['task'] == 'startup':
                pass
            elif row['task'] == 'pm_scan':
                # Plexmate로 스캔 요청
                cs.execute(f'UPDATE {table} SET task = "scan" WHERE id = {row["id"]}')
            elif row['task'] == 'pm_ready_refresh':
                # Plexmate Ready 새로고침
                pass
            elif row['task'] == 'refresh_pm_scan':
                # 새로고침 후 Plexmate 스캔
                cs.execute(f'UPDATE {table} SET task = "refresh_scan" WHERE id = {row["id"]}')
                pass
            elif row['task'] == 'refresh_pm_periodic':
                # 새로고침 후 주기적 스캔
                cs.execute(f'UPDATE {table} SET task = "refresh_scan" WHERE id = {row["id"]}')
                cs.execute(f'UPDATE {table} SET scan_mode = "periodic" WHERE id = {row["id"]}')
                cs.execute(f'UPDATE {table} SET periodic_id = {int(row["target"])} WHERE id = {row["id"]}')
                cs.execute(f'UPDATE {table} SET target = "" WHERE id = {row["id"]}')
            elif row['task'] == 'refresh_scan':
                # 새로고침 후 웹 스캔
                cs.execute(f'UPDATE {table} SET scan_mode = "web" WHERE id = {row["id"]}')

        # final check
        rows = cs.execute(f'SELECT * FROM "{table}"').fetchall()
        for row in rows:
            LOGGER.debug(f"{row['id']} | {row['ctime']} | {row['task']} | {row['desc']} | {row['target']} | {row['scan_mode']} | {row['periodic_id']}")
            #print(dict(row))
            if not row['task'] in TASK_KEYS:
                LOGGER.error(f'wrong task: {row["task"]}')
            if not row['scan_mode'] in SCAN_MODE_KEYS:
                LOGGER.error(f'wrong scan_mode: {row["scan_mode"]}')


def migrate_schedule_v3(cs: sqlite3.Cursor, table: str) -> None:
    LOGGER.debug('DB 버전 3 로 마이그레이션')
    rows = cs.execute(f'SELECT name FROM pragma_table_info("{table}")').fetchall()
    cols = [row['name'] for row in rows]
    if 'clear_type' not in cols:
        cs.execute(f'ALTER TABLE "{table}" ADD COLUMN "clear_type" VARCHAR')
    if 'clear_level' not in cols:
        cs.execute(f'ALTER TABLE "{table}" ADD COLUMN "clear_level" VARCHAR')
    if 'clear_section' not in cols:
        cs.execute(f'ALTER TABLE "{table}" ADD COLUMN "clear_section" INTEGER')


def migrate_schedule_v4(cs: sqlite3.Cursor, table: str) -> None:
    LOGGER.debug('DB 버전 4 로 마이그레이션')
    try:
        cs.execute(f'ALTER TABLE "{table}" DROP COLUMN "journal"')
    except Exception as e:
        LOGGER.error(e)


def migrate_schedule_v5(cs: sqlite3.Cursor, table: str) -> None:
    LOGGER.debug('DB 버전 5 로 마이그레이션')
    try:
        cs.execute(f'ALTER TABLE "{table}" ADD COLUMN "section_id" INTEGER DEFAULT -1 NOT NULL')
    except Exception as e:
        LOGGER.error(e)


def migrate_schedule_v6(cs: sqlite3.Cursor, table: str) -> None:
    try:
        rows = cs.execute(f'SELECT id, section_id FROM {table}').fetchall()
        for row in rows:
            if not row['section_id']:
                cs.execute(f'UPDATE {table} SET section_id = -1 WHERE id = {row["id"]}')
    except Exception as e:
        LOGGER.error(e)

def migrate_schedule_v7(cs: sqlite3.Cursor, table: str) -> None:
    pass


def migrate_setting_v1(cs: sqlite3.Cursor, table: str) -> None:
    LOGGER.warning(f'DB 버전 확인 필요')

def migrate_setting_v2(cs: sqlite3.Cursor, table: str) -> None:
    LOGGER.debug('DB 버전 2 로 마이그레이션')
    mapping = {
        'tool_gds_tool_request_span': 'setting_gds_tool_request_span',
        'tool_gds_tool_request_auto': 'setting_gds_tool_request_auto',
        'tool_gds_tool_fp_span': 'setting_gds_tool_fp_span',
        'tool_gds_tool_fp_auto': 'setting_gds_tool_fp_auto',
        'tool_login_log_enable': 'setting_logging_login',
    }
    for old, new in mapping.items():
        try:
            row = cs.execute(f'SELECT value FROM "{table}" WHERE key="{old}"').fetchone()
            if row:
                cs.execute(f'UPDATE "{table}" SET value="{row[-1]}" WHERE key="{new}"')
                cs.execute(f'DELETE FROM "{table}" WHERE key="{old}"')
        except Exception as e:
            LOGGER.error(e)

def migrate_setting_v3(cs: sqlite3.Cursor, table: str) -> None:
    pass