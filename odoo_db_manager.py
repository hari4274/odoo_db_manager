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

def read_odoo_config(config_file):
    """
    Read parameters from an Odoo configuration file.
    
    Args:
        config_file (str): Path to the Odoo configuration file.
    
    Returns:
        dict: Odoo configuration parameters.
    """
    config = configparser.ConfigParser()
    if config_file and os.path.exists(config_file):
        config.read(config_file)
        options = config['options'] if 'options' in config else {}
    else:
        options = {}
    
    conf = {
        'db_name': options.get('db_name', '').split(',') if options.get('db_name') else [],
        'data_dir': options.get('data_dir', os.path.expanduser('~/.local/share/Odoo')),
        'db_user': options.get('db_user', 'odoo'),
        'db_host': options.get('db_host', 'localhost'),
        'db_port': options.get('db_port', '5432'),
        'db_password': options.get('db_password', ''),
        'admin_passwd': options.get('admin_passwd', 'admin')
    }
    conf['filestore_path'] = os.path.join(conf['data_dir'], 'filestore')
    return conf

def read_backup_config(config_file):
    """
    Read parameters from a backup configuration file.
    
    Args:
        config_file (str): Path to the backup configuration file.
    
    Returns:
        dict: Backup configuration parameters.
    """
    config = configparser.ConfigParser()
    if config_file and os.path.exists(config_file):
        config.read(config_file)
        options = config['backup'] if 'backup' in config else {}
    else:
        options = {}
    
    conf = {
        'backup_dir': options.get('backup_dir', '/path/to/backup/directory'),
        'backup_db_names': options.get('backup_db_names', '').split(',') if options.get('backup_db_names') else [],
        'backup_retention_days': int(options.get('backup_retention_days', 7))
    }
    return conf

def create_odoo_backup(db_name, filestore_path, backup_dir, db_user="odoo", db_host="localhost", db_port="5432", db_password=None):
    """
    Create a backup of an Odoo instance, including database dump and filestore, compressed into a ZIP file.
    
    Args:
        db_name (str): Name of the PostgreSQL database to back up.
        filestore_path (str): Path to the Odoo filestore directory.
        backup_dir (str): Directory where the backup ZIP file will be saved.
        db_user (str): PostgreSQL database user.
        db_host (str): PostgreSQL database host.
        db_port (str): PostgreSQL database port.
        db_password (str, optional): PostgreSQL database password.
    
    Returns:
        str: Path to the created backup ZIP file.
    """
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"backup_{db_name}_{timestamp}.zip"
    backup_filepath = os.path.join(backup_dir, backup_filename)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        dump_file = os.path.join(temp_dir, f"{db_name}.sql")
        env = os.environ.copy()
        if db_password:
            env["PGPASSWORD"] = db_password
        
        try:
            subprocess.run([
                "pg_dump",
                "-U", db_user,
                "-h", db_host,
                "-p", db_port,
                "-f", dump_file,
                db_name
            ], check=True, env=env)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Database dump failed for {db_name}: {e}")
        
        with zipfile.ZipFile(backup_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(dump_file, f"dump.sql")
            filestore_db_path = os.path.join(filestore_path, db_name)
            if os.path.exists(filestore_db_path):
                for root, _, files in os.walk(filestore_db_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, filestore_path)
                        zipf.write(file_path, os.path.join("filestore", rel_path))
            else:
                print(f"Warning: Filestore path {filestore_db_path} does not exist.")
        
        if not os.path.exists(backup_filepath):
            raise Exception(f"Failed to create backup ZIP file for {db_name}.")
    
    return backup_filepath

def restore_odoo_backup(backup_filepath, db_name, filestore_path, db_user="odoo", db_host="localhost", db_port="5432", db_password=None, drop_existing=False):
    """
    Restore an Odoo backup from a ZIP file, including database and filestore.
    
    Args:
        backup_filepath (str): Path to the backup ZIP file.
        db_name (str): Name of the PostgreSQL database to restore to.
        filestore_path (str): Path to the Odoo filestore directory.
        db_user (str): PostgreSQL database user.
        db_host (str): PostgreSQL database host.
        db_port (str): PostgreSQL database port.
        db_password (str, optional): PostgreSQL database password.
        drop_existing (bool): If True, drop the existing database before restoring.
    
    Returns:
        bool: True if restoration is successful.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract the ZIP file
        with zipfile.ZipFile(backup_filepath, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        # Restore the database dump
        dump_file = os.path.join(temp_dir, "dump.sql")
        env = os.environ.copy()
        if db_password:
            env["PGPASSWORD"] = db_password
        
        try:
            if drop_existing:
                # Terminate all connections to the target database
                subprocess.run([
                    "psql",
                    "-U", db_user,
                    "-h", db_host,
                    "-p", db_port,
                    "-c", f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{db_name}' AND pid <> pg_backend_pid();",
                    "postgres"
                ], check=True, env=env)
                # Drop the existing database if it exists
                subprocess.run([
                    "dropdb",
                    "--if-exists",
                    "-U", db_user,
                    "-h", db_host,
                    "-p", db_port,
                    db_name
                ], check=True, env=env)
            
            # Create a new database
            subprocess.run([
                "createdb",
                "-U", db_user,
                "-h", db_host,
                "-p", db_port,
                db_name
            ], check=True, env=env)
            
            # Restore the database from dump
            subprocess.run([
                "psql",
                "-U", db_user,
                "-h", db_host,
                "-p", db_port,
                "-d", db_name,
                "-f", dump_file
            ], check=True, env=env)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Database restoration failed for {db_name}: {e}")
        
        # Restore the filestore
        filestore_base_path = os.path.join(temp_dir, "filestore")
        target_filestore_path = os.path.join(filestore_path, db_name)
        
        # Find any filestore directory in the ZIP (e.g., filestore/old_dbname)
        filestore_dir = None
        if os.path.exists(filestore_base_path):
            for item in os.listdir(filestore_base_path):
                item_path = os.path.join(filestore_base_path, item)
                if os.path.isdir(item_path):
                    filestore_dir = item_path
                    break
        
        if filestore_dir:
            if os.path.exists(target_filestore_path):
                shutil.rmtree(target_filestore_path)
            shutil.copytree(filestore_dir, target_filestore_path)
            print(f"Filestore restored from {filestore_dir} to {target_filestore_path}")
        else:
            print(f"Warning: No filestore directory found in backup ZIP at {filestore_base_path}.")
    
    return True

def duplicate_odoo_database(source_db, target_db, filestore_path, db_user="odoo", db_host="localhost", db_port="5432", db_password=None, drop_existing=False):
    """
    Duplicate an Odoo database and its filestore to a new database.
    
    Args:
        source_db (str): Name of the source PostgreSQL database.
        target_db (str): Name of the target PostgreSQL database.
        filestore_path (str): Path to the Odoo filestore directory.
        db_user (str): PostgreSQL database user.
        db_host (str): PostgreSQL database host.
        db_port (str): PostgreSQL database port.
        db_password (str, optional): PostgreSQL database password.
        drop_existing (bool): If True, drop the existing target database before duplicating.
    
    Returns:
        bool: True if duplication is successful.
    """
    env = os.environ.copy()
    if db_password:
        env["PGPASSWORD"] = db_password
    
    try:
        if drop_existing:
            # Terminate all connections to the target database
            subprocess.run([
                "psql",
                "-U", db_user,
                "-h", db_host,
                "-p", db_port,
                "-c", f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{target_db}' AND pid <> pg_backend_pid();",
                "postgres"
            ], check=True, env=env)
            # Drop the existing target database if it exists
            subprocess.run([
                "dropdb",
                "--if-exists",
                "-U", db_user,
                "-h", db_host,
                "-p", db_port,
                target_db
            ], check=True, env=env)
        
        # Create the target database
        subprocess.run([
            "createdb",
            "-U", db_user,
            "-h", db_host,
            "-p", db_port,
            target_db
        ], check=True, env=env)
        
        # Copy the source database to the target database
        dump_process = subprocess.Popen([
            "pg_dump",
            "-U", db_user,
            "-h", db_host,
            "-p", db_port,
            source_db
        ], stdout=subprocess.PIPE, env=env)
        
        restore_process = subprocess.Popen([
            "psql",
            "-U", db_user,
            "-h", db_host,
            "-p", db_port,
            "-d", target_db
        ], stdin=dump_process.stdout, env=env)
        
        dump_process.stdout.close()
        restore_process.communicate()
        
        if dump_process.returncode or restore_process.returncode:
            raise Exception(f"Database duplication failed from {source_db} to {target_db}")
        
        # Copy the filestore
        source_filestore_path = os.path.join(filestore_path, source_db)
        target_filestore_path = os.path.join(filestore_path, target_db)
        if os.path.exists(source_filestore_path):
            if os.path.exists(target_filestore_path):
                shutil.rmtree(target_filestore_path)
            shutil.copytree(source_filestore_path, target_filestore_path)
        else:
            print(f"Warning: No filestore found for source database {source_db}.")
    
    except subprocess.CalledProcessError as e:
        raise Exception(f"Database duplication failed for {source_db} to {target_db}: {e}")
    
    return True

def drop_odoo_database(db_name, filestore_path, db_user="odoo", db_host="localhost", db_port="5432", db_password=None):
    """
    Drop an Odoo database and its associated filestore.
    
    Args:
        db_name (str): Name of the PostgreSQL database to drop.
        filestore_path (str): Path to the Odoo filestore directory.
        db_user (str): PostgreSQL database user.
        db_host (str): PostgreSQL database host.
        db_port (str): PostgreSQL database port.
        db_password (str, optional): PostgreSQL database password.
    
    Returns:
        bool: True if drop is successful.
    """
    env = os.environ.copy()
    if db_password:
        env["PGPASSWORD"] = db_password
    
    try:
        # Terminate all connections to the database
        subprocess.run([
            "psql",
            "-U", db_user,
            "-h", db_host,
            "-p", db_port,
            "-c", f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{db_name}' AND pid <> pg_backend_pid();",
            "postgres"
        ], check=True, env=env)
        
        # Drop the database if it exists
        subprocess.run([
            "dropdb",
            "--if-exists",
            "-U", db_user,
            "-h", db_host,
            "-p", db_port,
            db_name
        ], check=True, env=env)
        
        # Remove the filestore directory
        filestore_db_path = os.path.join(filestore_path, db_name)
        if os.path.exists(filestore_db_path):
            shutil.rmtree(filestore_db_path)
            print(f"Filestore removed for database {db_name} at {filestore_db_path}")
        else:
            print(f"Warning: No filestore found for database {db_name} at {filestore_db_path}")
    
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to drop database {db_name}: {e}")
    
    return True

def create_odoo_database(db_name, filestore_path, db_user="odoo", db_host="localhost", db_port="5432", db_password=None):
    """
    Create a new, empty Odoo database and its associated filestore directory.
    
    Args:
        db_name (str): Name of the PostgreSQL database to create.
        filestore_path (str): Path to the Odoo filestore directory.
        db_user (str): PostgreSQL database user.
        db_host (str): PostgreSQL database host.
        db_port (str): PostgreSQL database port.
        db_password (str, optional): PostgreSQL database password.
    
    Returns:
        bool: True if creation is successful.
    """
    env = os.environ.copy()
    if db_password:
        env["PGPASSWORD"] = db_password
    
    try:
        # Create the database
        subprocess.run([
            "createdb",
            "-U", db_user,
            "-h", db_host,
            "-p", db_port,
            db_name
        ], check=True, env=env)
        
        # Create an empty filestore directory
        filestore_db_path = os.path.join(filestore_path, db_name)
        os.makedirs(filestore_db_path, exist_ok=True)
        print(f"Filestore directory created for database {db_name} at {filestore_db_path}")
    
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to create database {db_name}: {e}")
    
    return True

def cleanup_old_backups(backup_dir, retention_days):
    """
    Delete backup files older than the specified retention period.
    
    Args:
        backup_dir (str): Directory containing backup files.
        retention_days (int): Number of days to retain backups.
    """
    if not os.path.exists(backup_dir):
        return
    
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    for backup_file in glob.glob(os.path.join(backup_dir, "backup_*.zip")):
        file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(backup_file))
        if file_mtime < cutoff_date:
            try:
                os.remove(backup_file)
                print(f"Deleted old backup: {backup_file}")
            except OSError as e:
                print(f"Failed to delete old backup {backup_file}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Generic Odoo Backup, Restore, Duplicate, Drop, and Create Script")
    parser.add_argument("action", choices=["backup", "restore", "duplicate", "drop_db", "create_db"], help="Action to perform: 'backup', 'restore', 'duplicate', 'drop_db', or 'create_db'")
    parser.add_argument("--odoo-config", help="Path to Odoo configuration file")
    parser.add_argument("--backup-config", help="Path to backup configuration file")
    parser.add_argument("--db-name", help="Name of the target PostgreSQL database (for restore, duplicate, drop_db, or create_db)")
    parser.add_argument("--source-db", help="Name of the source PostgreSQL database (for duplicate)")
    parser.add_argument("--filestore-path", help="Path to Odoo filestore directory (overrides config files)")
    parser.add_argument("--backup-dir", help="Directory for backup files (overrides config files)")
    parser.add_argument("--backup-file", help="Path to the backup ZIP file (for restore action)")
    parser.add_argument("--db-user", help="PostgreSQL database user (overrides config files)")
    parser.add_argument("--db-host", help="PostgreSQL database host (overrides config files)")
    parser.add_argument("--db-port", help="PostgreSQL database port (overrides config files)")
    parser.add_argument("--db-password", help="PostgreSQL database password (overrides config files)")
    parser.add_argument("--drop-existing", action="store_true", help="Drop existing database before restoring or duplicating")
    parser.add_argument("--retention-days", type=int, help="Number of days to retain backups (overrides backup config)")
    
    args = parser.parse_args()
    
    try:
        # Read configuration files
        odoo_config = read_odoo_config(args.odoo_config)
        backup_config = read_backup_config(args.backup_config)
        
        # Determine parameters (command-line > backup config > odoo config > defaults)
        db_names = [args.db_name] if args.db_name else backup_config['backup_db_names'] or odoo_config['db_name']
        filestore_path = args.filestore_path or odoo_config['filestore_path']
        backup_dir = args.backup_dir or backup_config['backup_dir']
        db_user = args.db_user or odoo_config['db_user']
        db_host = args.db_host or odoo_config['db_host']
        db_port = args.db_port or odoo_config['db_port']
        db_password = args.db_password or odoo_config['db_password']
        retention_days = args.retention_days if args.retention_days is not None else backup_config['backup_retention_days']
        
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
                    db_password=db_password
                )
                print(f"Backup successfully created for {db_name} at: {backup_path}")
            
            # Clean up old backups
            cleanup_old_backups(backup_dir, retention_days)
        
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
                drop_existing=args.drop_existing
            )
            if success:
                print(f"Database {args.db_name} and filestore successfully restored.")
        
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
                drop_existing=args.drop_existing
            )
            if success:
                print(f"Database {args.source_db} successfully duplicated to {args.db_name} with filestore.")
        
        elif args.action == "drop_db":
            if not args.db_name:
                raise ValueError("Database name is required for drop_db action")
            success = drop_odoo_database(
                db_name=args.db_name,
                filestore_path=filestore_path,
                db_user=db_user,
                db_host=db_host,
                db_port=db_port,
                db_password=db_password
            )
            if success:
                print(f"Database {args.db_name} and filestore successfully dropped.")
        
        elif args.action == "create_db":
            if not args.db_name:
                raise ValueError("Database name is required for create_db action")
            success = create_odoo_database(
                db_name=args.db_name,
                filestore_path=filestore_path,
                db_user=db_user,
                db_host=db_host,
                db_port=db_port,
                db_password=db_password
            )
            if success:
                print(f"Database {args.db_name} and filestore directory successfully created.")
    
    except Exception as e:
        print(f"Operation failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()