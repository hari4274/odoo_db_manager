import os
import subprocess
import zipfile
import datetime
import shutil
import tempfile
import argparse
import configparser
from pathlib import Path
import glob
import logging
import logging.handlers

def setup_logging(verbose=True, log_file=None, log_dir=None):
    """
    Set up logging configuration with console and file output.
    
    Args:
        verbose (bool): If True, enable detailed debug logging (default: True).
        log_file (str): Path to log file (default: odoo_db_manager.log in log_dir or current directory).
        log_dir (str): Directory for log file (default: Odoo log directory or current directory).
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger('odoo_db_manager')
    logger.setLevel(level)
    
    logger.handlers = []
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    if not log_file:
        log_file = os.path.join(log_dir or '.', 'odoo_db_manager.log')
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        logger.debug(f"Logging to file: {log_file}")
    except Exception as e:
        logger.error(f"Failed to set up log file {log_file}: {e}")
        logger.info("Falling back to console-only logging")
    
    return logger

def read_odoo_config(config_file, logger):
    """
    Read parameters from an Odoo configuration file, including log directory.
    
    Args:
        config_file (str): Path to the Odoo configuration file.
        logger: Logger instance for logging.
    
    Returns:
        dict: Odoo configuration parameters including log_dir.
    """
    logger.debug(f"Reading Odoo config from {config_file}")
    config = configparser.ConfigParser()
    log_dir = None
    
    if config_file and os.path.exists(config_file):
        config.read(config_file)
        options = config['options'] if 'options' in config else {}
        if options.get('logfile'):
            log_dir = os.path.dirname(options['logfile'])
        elif options.get('log_dir'):
            log_dir = options['log_dir']
    else:
        logger.warning(f"Odoo config file {config_file} not found, using defaults")
        options = {}
    
    conf = {
        'db_name': options.get('db_name', '').split(',') if options.get('db_name') else [],
        'data_dir': options.get('data_dir', os.path.expanduser('~/.local/share/Odoo')),
        'db_user': options.get('db_user', 'odoo'),
        'db_host': options.get('db_host', 'localhost'),
        'db_port': options.get('db_port', '5432'),
        'db_password': options.get('db_password', ''),
        'admin_passwd': options.get('admin_passwd', 'admin'),
        'log_dir': log_dir
    }
    conf['filestore_path'] = os.path.join(conf['data_dir'], 'filestore')
    logger.debug(f"Odoo config: {conf}")
    return conf

def read_backup_config(config_file, logger):
    """
    Read parameters from a backup configuration file, including logging options.
    
    Args:
        config_file (str): Path to the backup configuration file.
        logger: Logger instance for logging.
    
    Returns:
        dict: Backup and logging configuration parameters.
    """
    logger.debug(f"Reading backup config from {config_file}")
    config = configparser.ConfigParser()
    conf = {
        'backup_dir': '/path/to/backup/directory',
        'backup_db_names': [],
        'backup_retention_days': 7,
        'log_file': None,
        'log_retention_days': 7
    }
    
    if config_file and os.path.exists(config_file):
        config.read(config_file)
        backup_options = config['backup'] if 'backup' in config else {}
        conf['backup_dir'] = backup_options.get('backup_dir', conf['backup_dir'])
        conf['backup_db_names'] = backup_options.get('backup_db_names', '').split(',') if backup_options.get('backup_db_names') else []
        conf['backup_retention_days'] = int(backup_options.get('backup_retention_days', conf['backup_retention_days']))
        
        logging_options = config['logging'] if 'logging' in config else {}
        conf['log_file'] = logging_options.get('log_file', conf['log_file'])
        conf['log_retention_days'] = int(logging_options.get('log_retention_days', conf['log_retention_days']))
    else:
        logger.warning(f"Backup config file {config_file} not found, using defaults")
    
    logger.debug(f"Backup and logging config: {conf}")
    return conf

def create_odoo_backup(db_name, filestore_path, backup_dir, db_user="odoo", db_host="localhost", db_port="5432", db_password=None, with_filestore=True, logger=None, temp_dir=None):
    """
    Create a backup of an Odoo instance, including SQL dump and optionally filestore, compressed into a ZIP file.
    
    Args:
        db_name (str): Name of the PostgreSQL database to back up.
        filestore_path (str): Path to the Odoo filestore directory.
        backup_dir (str): Directory where the backup ZIP file will be saved.
        db_user (str): PostgreSQL database user.
        db_host (str): PostgreSQL database host.
        db_port (str): PostgreSQL database port.
        db_password (str, optional): PostgreSQL database password.
        with_filestore (bool): If True, include filestore in the backup (default: True).
        logger: Logger instance for logging.
        temp_dir (str): Temporary directory for PostgreSQL logs.
    
    Returns:
        str: Path to the created backup ZIP file.
    """
    logger.info(f"Starting backup for database {db_name} {'with' if with_filestore else 'without'} filestore")
    
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"backup_{db_name}_{timestamp}.zip"
    backup_filepath = os.path.join(backup_dir, backup_filename)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        dump_file = os.path.join(temp_dir, f"{db_name}.sql")
        psql_log = os.path.join(temp_dir, "pg_dump.log")
        env = os.environ.copy()
        if db_password:
            env["PGPASSWORD"] = db_password
        
        try:
            logger.debug(f"Creating SQL dump at {dump_file}, PostgreSQL logs at {psql_log}")
            with open(psql_log, 'w') as log_file, open(dump_file, 'w') as dump_out:
                subprocess.run([
                    "pg_dump",
                    "-U", db_user,
                    "-h", db_host,
                    "-p", db_port,
                    db_name
                ], check=True, env=env, stdout=dump_out, stderr=log_file)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            with open(psql_log, 'r') as log_file:
                psql_output = log_file.read()
            logger.error(f"Database dump failed for {db_name}: {e}\nPostgreSQL output: {psql_output}")
            raise Exception(f"Database dump failed for {db_name}: {e}")
        
        logger.debug(f"Creating ZIP file at {backup_filepath}")
        try:
            with zipfile.ZipFile(backup_filepath, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
                zipf.write(dump_file, "dump.sql")
                if with_filestore:
                    filestore_db_path = os.path.join(filestore_path, db_name)
                    if os.path.exists(filestore_db_path):
                        logger.debug(f"Adding filestore from {filestore_db_path}")
                        for root, _, files in os.walk(filestore_db_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                rel_path = os.path.relpath(file_path, filestore_path)
                                zipf.write(file_path, os.path.join("filestore", rel_path))
                    else:
                        logger.warning(f"Filestore path {filestore_db_path} does not exist")
        except zipfile.BadZipFile as e:
            logger.error(f"Failed to create ZIP file: {e}")
            raise Exception(f"Failed to create ZIP file: {e}")
        
        if not os.path.exists(backup_filepath):
            logger.error(f"Backup ZIP file not created at {backup_filepath}")
            raise Exception(f"Failed to create backup ZIP file for {db_name}")
    
    logger.info(f"Backup completed for {db_name} at {backup_filepath}")
    return backup_filepath

def restore_odoo_backup(backup_filepath, db_name, filestore_path, db_user="odoo", db_host="localhost", db_port="5432", db_password=None, drop_existing=False, with_filestore=True, logger=None, temp_dir=None):
    """
    Restore an Odoo backup from a ZIP file, including SQL dump and optionally filestore.
    
    Args:
        backup_filepath (str): Path to the backup ZIP file.
        db_name (str): Name of the PostgreSQL database to restore to.
        filestore_path (str): Path to the Odoo filestore directory.
        db_user (str): PostgreSQL database user.
        db_host (str): PostgreSQL database host.
        db_port (str): PostgreSQL database port.
        db_password (str, optional): PostgreSQL database password.
        drop_existing (bool): If True, drop the existing database before restoring.
        with_filestore (bool): If True, restore the filestore from the backup (default: True).
        logger: Logger instance for logging.
        temp_dir (str): Temporary directory for PostgreSQL logs.
    
    Returns:
        bool: True if restoration is successful.
    """
    logger.info(f"Starting restore for database {db_name} from {backup_filepath} {'with' if with_filestore else 'without'} filestore")
    
    try:
        with zipfile.ZipFile(backup_filepath, 'r') as zipf:
            zipf.testzip()
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid or corrupted ZIP file: {e}")
        raise Exception(f"Invalid or corrupted ZIP file: {e}")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.debug(f"Extracting ZIP file to {temp_dir}")
        with zipfile.ZipFile(backup_filepath, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        dump_file = os.path.join(temp_dir, "dump.sql")
        psql_log = os.path.join(temp_dir, "psql_restore.log")
        env = os.environ.copy()
        if db_password:
            env["PGPASSWORD"] = db_password
        
        if drop_existing:
            try:
                logger.debug(f"Terminating connections to database {db_name}")
                with open(psql_log, 'w') as log_file:
                    subprocess.run([
                        "psql",
                        "-U", db_user,
                        "-h", db_host,
                        "-p", db_port,
                        "-c", f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{db_name}' AND pid <> pg_backend_pid();",
                        "postgres"
                    ], check=True, env=env, stdout=log_file, stderr=log_file)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                with open(psql_log, 'r') as log_file:
                    psql_output = log_file.read()
                logger.error(f"Terminating connections failed for {db_name}: {e}\nPostgreSQL output: {psql_output}")
                raise Exception(f"Terminating connections failed for {db_name}: {e}")
            
            try:
                logger.debug(f"Dropping existing database {db_name}")
                with open(psql_log, 'a') as log_file:
                    subprocess.run([
                        "dropdb",
                        "--if-exists",
                        "-U", db_user,
                        "-h", db_host,
                        "-p", db_port,
                        db_name
                    ], check=True, env=env, stdout=log_file, stderr=log_file)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                with open(psql_log, 'r') as log_file:
                    psql_output = log_file.read()
                logger.error(f"Dropping database failed for {db_name}: {e}\nPostgreSQL output: {psql_output}")
                raise Exception(f"Dropping database failed for {db_name}: {e}")
        
        try:
            logger.debug(f"Creating new database {db_name}")
            with open(psql_log, 'a') as log_file:
                subprocess.run([
                    "createdb",
                    "-U", db_user,
                    "-h", db_host,
                    "-p", db_port,
                    db_name
                ], check=True, env=env, stdout=log_file, stderr=log_file)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            with open(psql_log, 'r') as log_file:
                psql_output = log_file.read()
            logger.error(f"Creating database failed for {db_name}: {e}\nPostgreSQL output: {psql_output}")
            raise Exception(f"Creating database failed for {db_name}: {e}")
        
        try:
            logger.debug(f"Restoring database from {dump_file}")
            with open(psql_log, 'a') as log_file, open(dump_file, 'r') as dump_in:
                subprocess.run([
                    "psql",
                    "-U", db_user,
                    "-h", db_host,
                    "-p", db_port,
                    "-d", db_name,
                    # "--no-owner",
                    # "--set", "ON_ERROR_STOP=on"
                ], check=True, env=env, stdin=dump_in, stdout=log_file, stderr=log_file)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            with open(psql_log, 'r') as log_file:
                psql_output = log_file.read()
            logger.error(f"Database restoration failed for {db_name}: {e}\nPostgreSQL output: {psql_output}")
            raise Exception(f"Database restoration failed for {db_name}: {e}")
        
        if with_filestore:
            filestore_base_path = os.path.join(temp_dir, "filestore")
            target_filestore_path = os.path.join(filestore_path, db_name)
            
            filestore_dir = None
            if os.path.exists(filestore_base_path):
                for item in os.listdir(filestore_base_path):
                    item_path = os.path.join(filestore_base_path, item)
                    if os.path.isdir(item_path):
                        filestore_dir = item_path
                        break
            
            if filestore_dir:
                logger.debug(f"Restoring filestore from {filestore_dir} to {target_filestore_path}")
                if os.path.exists(target_filestore_path):
                    shutil.rmtree(target_filestore_path)
                shutil.copytree(filestore_dir, target_filestore_path)
                logger.info(f"Filestore restored from {filestore_dir} to {target_filestore_path}")
            else:
                logger.warning(f"No filestore directory found in backup ZIP at {filestore_base_path}")
    
    logger.info(f"Restore completed for {db_name}")
    return True

def duplicate_odoo_database(source_db, target_db, filestore_path, db_user="odoo", db_host="localhost", db_port="5432", db_password=None, drop_existing=False, with_filestore=True, logger=None, temp_dir=None):
    """
    Duplicate an Odoo database and optionally its filestore to a new database.
    
    Args:
        source_db (str): Name of the source PostgreSQL database.
        target_db (str): Name of the target PostgreSQL database.
        filestore_path (str): Path to the Odoo filestore directory.
        db_user (str): PostgreSQL database user.
        db_host (str): PostgreSQL database host.
        db_port (str): PostgreSQL database port.
        db_password (str, optional): PostgreSQL database password.
        drop_existing (bool): If True, drop the existing target database before duplicating.
        with_filestore (bool): If True, copy the filestore (default: True).
        logger: Logger instance for logging.
        temp_dir (str): Temporary directory for PostgreSQL logs.
    
    Returns:
        bool: True if duplication is successful.
    """
    logger.info(f"Starting duplication from {source_db} to {target_db} {'with' if with_filestore else 'without'} filestore")
    
    env = os.environ.copy()
    if db_password:
        env["PGPASSWORD"] = db_password
    
    psql_log = os.path.join(temp_dir, "psql_duplicate.log")
    
    if drop_existing:
        try:
            logger.debug(f"Terminating connections to target database {target_db}")
            with open(psql_log, 'w') as log_file:
                subprocess.run([
                    "psql",
                    "-U", db_user,
                    "-h", db_host,
                    "-p", db_port,
                    "-c", f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{target_db}' AND pid <> pg_backend_pid();",
                    "postgres"
                ], check=True, env=env, stdout=log_file, stderr=log_file)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            with open(psql_log, 'r') as log_file:
                psql_output = log_file.read()
            logger.error(f"Terminating connections failed for {target_db}: {e}\nPostgreSQL output: {psql_output}")
            raise Exception(f"Terminating connections failed for {target_db}: {e}")
        
        try:
            logger.debug(f"Dropping existing target database {target_db}")
            with open(psql_log, 'a') as log_file:
                subprocess.run([
                    "dropdb",
                    "--if-exists",
                    "-U", db_user,
                    "-h", db_host,
                    "-p", db_port,
                    target_db
                ], check=True, env=env, stdout=log_file, stderr=log_file)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            with open(psql_log, 'r') as log_file:
                psql_output = log_file.read()
            logger.error(f"Dropping database failed for {target_db}: {e}\nPostgreSQL output: {psql_output}")
            raise Exception(f"Dropping database failed for {target_db}: {e}")
    
    try:
        logger.debug(f"Creating target database {target_db}")
        with open(psql_log, 'a') as log_file:
            subprocess.run([
                "createdb",
                "-U", db_user,
                "-h", db_host,
                "-p", db_port,
                target_db
            ], check=True, env=env, stdout=log_file, stderr=log_file)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        with open(psql_log, 'r') as log_file:
            psql_output = log_file.read()
        logger.error(f"Creating database failed for {target_db}: {e}\nPostgreSQL output: {psql_output}")
        raise Exception(f"Creating database failed for {target_db}: {e}")
    
    try:
        logger.debug(f"Copying database from {source_db} to {target_db}")
        with open(psql_log, 'a') as log_file:
            dump_process = subprocess.Popen([
                "pg_dump",
                "-U", db_user,
                "-h", db_host,
                "-p", db_port,
                source_db
            ], stdout=subprocess.PIPE, stderr=log_file, env=env)
            
            restore_process = subprocess.Popen([
                "psql",
                "-U", db_user,
                "-h", db_host,
                "-p", db_port,
                "-d", target_db,
                # "--no-owner",
                # "--set", "ON_ERROR_STOP=on"
            ], stdin=dump_process.stdout, stderr=log_file, env=env)
            
            dump_process.stdout.close()
            restore_process.communicate()
            
            if dump_process.returncode or restore_process.returncode:
                with open(psql_log, 'r') as log_file:
                    psql_output = log_file.read()
                logger.error(f"Database duplication failed from {source_db} to {target_db}\nPostgreSQL output: {psql_output}")
                raise Exception(f"Database duplication failed from {source_db} to {target_db}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        with open(psql_log, 'r') as log_file:
            psql_output = log_file.read()
        logger.error(f"Database duplication failed for {source_db} to {target_db}: {e}\nPostgreSQL output: {psql_output}")
        raise Exception(f"Database duplication failed for {source_db} to {target_db}: {e}")
    
    if with_filestore:
        source_filestore_path = os.path.join(filestore_path, source_db)
        target_filestore_path = os.path.join(filestore_path, target_db)
        if os.path.exists(source_filestore_path):
            logger.debug(f"Copying filestore from {source_filestore_path} to {target_filestore_path}")
            if os.path.exists(target_filestore_path):
                shutil.rmtree(target_filestore_path)
            shutil.copytree(source_filestore_path, target_filestore_path)
            logger.info(f"Filestore copied from {source_filestore_path} to {target_filestore_path}")
        else:
            logger.warning(f"No filestore found for source database {source_db}")
    
    logger.info(f"Duplication completed from {source_db} to {target_db}")
    return True

def drop_odoo_database(db_name, filestore_path, db_user="odoo", db_host="localhost", db_port="5432", db_password=None, logger=None, temp_dir=None):
    """
    Drop an Odoo database and its associated filestore.
    
    Args:
        db_name (str): Name of the PostgreSQL database to drop.
        filestore_path (str): Path to the Odoo filestore directory.
        db_user (str): PostgreSQL database user.
        db_host (str): PostgreSQL database host.
        db_port (str): PostgreSQL database port.
        db_password (str, optional): PostgreSQL database password.
        logger: Logger instance for logging.
        temp_dir (str): Temporary directory for PostgreSQL logs.
    
    Returns:
        bool: True if drop is successful.
    """
    logger.info(f"Starting drop for database {db_name}")
    
    env = os.environ.copy()
    if db_password:
        env["PGPASSWORD"] = db_password
    
    psql_log = os.path.join(temp_dir, "psql_drop.log")
    
    try:
        logger.debug(f"Terminating connections to database {db_name}")
        with open(psql_log, 'w') as log_file:
            subprocess.run([
                "psql",
                "-U", db_user,
                "-h", db_host,
                "-p", db_port,
                "-c", f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{db_name}' AND pid <> pg_backend_pid();",
                "postgres"
            ], check=True, env=env, stdout=log_file, stderr=log_file)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        with open(psql_log, 'r') as log_file:
            psql_output = log_file.read()
        logger.error(f"Terminating connections failed for {db_name}: {e}\nPostgreSQL output: {psql_output}")
        raise Exception(f"Terminating connections failed for {db_name}: {e}")
    
    try:
        logger.debug(f"Dropping database {db_name}")
        with open(psql_log, 'a') as log_file:
            subprocess.run([
                "dropdb",
                "--if-exists",
                "-U", db_user,
                "-h", db_host,
                "-p", db_port,
                db_name
            ], check=True, env=env, stdout=log_file, stderr=log_file)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        with open(psql_log, 'r') as log_file:
            psql_output = log_file.read()
        logger.error(f"Dropping database failed for {db_name}: {e}\nPostgreSQL output: {psql_output}")
        raise Exception(f"Dropping database failed for {db_name}: {e}")
    
    filestore_db_path = os.path.join(filestore_path, db_name)
    if os.path.exists(filestore_db_path):
        logger.debug(f"Removing filestore at {filestore_db_path}")
        shutil.rmtree(filestore_db_path)
        logger.info(f"Filestore removed for database {db_name} at {filestore_db_path}")
    else:
        logger.warning(f"No filestore found for database {db_name} at {filestore_db_path}")
    
    logger.info(f"Drop completed for {db_name}")
    return True

def cleanup_old_files(directory, pattern, retention_days, logger=None, file_type="file"):
    """
    Delete files matching the pattern older than the specified retention period.
    
    Args:
        directory (str): Directory containing files.
        pattern (str): Glob pattern for files (e.g., "backup_*.zip" or "odoo_db_manager.log*").
        retention_days (int): Number of days to retain files.
        logger: Logger instance for logging.
        file_type (str): Type of file for logging (e.g., "backup" or "log").
    
    Returns:
        None
    """
    if not os.path.exists(directory):
        logger.warning(f"{file_type.capitalize()} directory {directory} does not exist, skipping cleanup")
        return
    
    logger.info(f"Cleaning up old {file_type} files in {directory} older than {retention_days} days")
    
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    for file in glob.glob(os.path.join(directory, pattern)):
        file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file))
        if file_mtime < cutoff_date:
            try:
                os.remove(file)
                logger.info(f"Deleted old {file_type} file: {file}")
            except OSError as e:
                logger.error(f"Failed to delete old {file_type} file {file}: {e}")
    
    logger.info(f"{file_type.capitalize()} cleanup completed")

def main():
    parser = argparse.ArgumentParser(description="Optimized Odoo Database Management Script")
    parser.add_argument("action", choices=["backup", "restore", "duplicate", "drop_db"], help="Action to perform: 'backup', 'restore', 'duplicate', or 'drop_db'")
    parser.add_argument("--odoo-config", help="Path to Odoo configuration file")
    parser.add_argument("--backup-config", help="Path to backup configuration file")
    parser.add_argument("--db-name", help="Name of the target PostgreSQL database (for restore, duplicate, drop_db)")
    parser.add_argument("--source-db", help="Name of the source PostgreSQL database (for duplicate)")
    parser.add_argument("--filestore-path", help="Path to Odoo filestore directory (overrides config files)")
    parser.add_argument("--backup-dir", help="Directory for backup files (overrides config files)")
    parser.add_argument("--backup-file", help="Path to the backup ZIP file (for restore action)")
    parser.add_argument("--db-user", help="PostgreSQL database user (overrides config files)")
    parser.add_argument("--db-host", help="PostgreSQL database host (overrides config files)")
    parser.add_argument("--db-port", help="PostgreSQL database port (overrides config files)")
    parser.add_argument("--db-password", help="PostgreSQL database password (overrides config files)")
    parser.add_argument("--drop-existing", action="store_true", help="Drop existing database before restoring or duplicating")
    parser.add_argument("--without-filestore", action="store_false", dest="with_filestore", help="Exclude filestore in backup, restore, or duplicate (default: include filestore)")
    parser.add_argument("--no-verbose", action="store_false", dest="verbose", help="Disable detailed logging (default: verbose logging enabled)")
    parser.add_argument("--retention-days", type=int, help="Number of days to retain backups (overrides backup config)")
    parser.add_argument("--log-file", help="Path to log file (overrides backup config)")
    parser.add_argument("--log-retention-days", type=int, help="Number of days to retain log files (overrides backup config)")
    
    args = parser.parse_args()
    args.verbose = True if not hasattr(args, 'verbose') else args.verbose
    args.with_filestore = True if not hasattr(args, 'with_filestore') else args.with_filestore
    
    odoo_config = read_odoo_config(args.odoo_config, logging.getLogger('odoo_db_manager'))
    log_dir = odoo_config.get('log_dir')
    
    logger = setup_logging(args.verbose, args.log_file, log_dir)
    
    try:
        logger.debug("Reading configuration files")
        backup_config = read_backup_config(args.backup_config, logger)
        
        db_names = [args.db_name] if args.db_name else backup_config['backup_db_names'] or odoo_config['db_name']
        filestore_path = args.filestore_path or odoo_config['filestore_path']
        backup_dir = args.backup_dir or backup_config['backup_dir']
        db_user = args.db_user or odoo_config['db_user']
        db_host = args.db_host or odoo_config['db_host']
        db_port = args.db_port or odoo_config['db_port']
        db_password = args.db_password or odoo_config['db_password']
        retention_days = args.retention_days if args.retention_days is not None else backup_config['backup_retention_days']
        log_file = args.log_file or backup_config['log_file']
        log_retention_days = args.log_retention_days if args.log_retention_days is not None else backup_config['log_retention_days']
        
        log_file_path = log_file or os.path.join(log_dir or '.', 'odoo_db_manager.log')
        log_dir_for_cleanup = os.path.dirname(log_file_path)
        with tempfile.TemporaryDirectory() as temp_dir:
            if args.action == "backup":
                if not db_names:
                    raise ValueError("No database names specified in config files or command-line arguments")
                for db_name in db_names:
                    db_name = db_name.strip()
                    if not db_name:
                        continue
                    backup_path = create_odoo_backup(
                        db_name=db_name,
                        filestore_path=filestore_path,
                        backup_dir=backup_dir,
                        db_user=db_user,
                        db_host=db_host,
                        db_port=db_port,
                        db_password=db_password,
                        with_filestore=args.with_filestore,
                        logger=logger,
                        temp_dir=temp_dir
                    )
                    print(f"Backup successfully created for {db_name} at: {backup_path}")
                
                cleanup_old_files(backup_dir, "backup_*.zip", retention_days, logger, "backup")
                cleanup_old_files(log_dir_for_cleanup, "odoo_db_manager.log*", log_retention_days, logger, "log")
            
            elif args.action == "restore":
                if not args.backup_file:
                    raise ValueError("Backup file path is required for restore action")
                if not args.db_name:
                    raise ValueError("Database name is required for restore action")
                success = restore_odoo_backup(
                    backup_filepath=args.backup_file,
                    db_name=args.db_name,
                    filestore_path=filestore_path,
                    db_user=db_user,
                    db_host=db_host,
                    db_port=db_port,
                    db_password=db_password,
                    drop_existing=args.drop_existing,
                    with_filestore=args.with_filestore,
                    logger=logger,
                    temp_dir=temp_dir
                )
                if success:
                    print(f"Database {args.db_name} {'and filestore ' if args.with_filestore else ''}successfully restored.")
                cleanup_old_files(log_dir_for_cleanup, "odoo_db_manager.log*", log_retention_days, logger, "log")
            
            elif args.action == "duplicate":
                if not args.source_db:
                    raise ValueError("Source database name is required for duplicate action")
                if not args.db_name:
                    raise ValueError("Target database name is required for duplicate action")
                success = duplicate_odoo_database(
                    source_db=args.source_db,
                    target_db=args.db_name,
                    filestore_path=filestore_path,
                    db_user=db_user,
                    db_host=db_host,
                    db_port=db_port,
                    db_password=db_password,
                    drop_existing=args.drop_existing,
                    with_filestore=args.with_filestore,
                    logger=logger,
                    temp_dir=temp_dir
                )
                if success:
                    print(f"Database {args.source_db} successfully duplicated to {args.db_name}{' with filestore' if args.with_filestore else ''}.")
                cleanup_old_files(log_dir_for_cleanup, "odoo_db_manager.log*", log_retention_days, logger, "log")
            
            elif args.action == "drop_db":
                if not args.db_name:
                    raise ValueError("Database name is required for drop_db action")
                success = drop_odoo_database(
                    db_name=args.db_name,
                    filestore_path=filestore_path,
                    db_user=db_user,
                    db_host=db_host,
                    db_port=db_port,
                    db_password=db_password,
                    logger=logger,
                    temp_dir=temp_dir
                )
                if success:
                    print(f"Database {args.db_name} and filestore successfully dropped.")
                cleanup_old_files(log_dir_for_cleanup, "odoo_db_manager.log*", log_retention_days, logger, "log")
    
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        print(f"Operation failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()