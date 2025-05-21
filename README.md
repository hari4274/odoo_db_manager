# Odoo Database Manager

![Python](https://img.shields.io/badge/Python-3.6%2B-blue)
![Odoo](https://img.shields.io/badge/Odoo-10%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

An optimized Python script for managing Odoo databases, providing backup, restore, duplicate, and drop functionalities. Compatible with all Odoo versions (10+) using PostgreSQL and ZIP backups with compressed custom-format dumps.

## Features

- **Backup**: Create secure, compressed ZIP backups (`backup_<db_name>_<timestamp>.zip`) of Odoo databases (custom-format dumps) and filestores by default, excluding sensitive data like the master password.
- **Restore**: Restore databases and filestores by default from ZIP backups, handling mismatched filestore names (e.g., `filestore/old_dbname` to `target_db`).
- **Duplicate**: Copy a source database and its filestore by default to a new database.
- **Drop Database**: Safely drop a database and its filestore, terminating active connections.
- **Filestore Control**: Use `--without-filestore` to exclude filestore in backups, restores, or duplicates (default: include filestore).
- **Configuration**: Supports Odoo (`odoo.conf`) and backup (`backup.conf`) config files, with command-line overrides.
- **Retention Policy**: Automatically clean up old backups (default: 7 days) and log files (default: 7 days) based on retention periods.
- **Verbose Logging**: Detailed logs with timestamps enabled by default, saved to `odoo_db_manager.log` in the Odoo log directory, disable with `--no-verbose`.
- **Log Separation**: PostgreSQL command logs (e.g., `pg_dump`, `pg_restore`) are isolated to temporary files, included in `odoo_db_manager.log` only on errors.
- **Log Configuration**: Customize log file path and retention days via `backup.conf` or command-line (`--log-file`, `--log-retention-days`).
- **Backup Validation**: Validates ZIP integrity during restoration to prevent corrupted backups.
- **Optimized Compression**: Uses custom-format database dumps (`pg_dump -F c`) and high-compression ZIP for smaller, faster backups.
- **Generic Compatibility**: Works with any Odoo version (10 to 18+) using standard PostgreSQL commands.

## Prerequisites

- **Python**: 3.6 or higher
- **PostgreSQL**: With `pg_dump`, `pg_restore`, `psql`, `createdb`, and `dropdb` utilities installed
- **Odoo**: Any version (10+) with a valid configuration file
- **Permissions**: 
  - PostgreSQL user must have permissions to create, drop, and restore databases.
  - Write access to the Odoo filestore directory, backup directory, and Odoo log directory.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/odoo-db-manager.git
   cd odoo-db-manager
   ```

2. **Install Dependencies**:
   No external Python libraries are required. Ensure PostgreSQL tools are installed:
   ```bash
   sudo apt-get install postgresql-client  # Debian/Ubuntu
   # OR
   sudo yum install postgresql  # CentOS/RHEL
   ```

3. **Save the Script**:
   The main script is `odoo_db_manager.py`. Ensure it’s executable:
   ```bash
   chmod +x odoo_db_manager.py
   ```

## Configuration

The script uses two optional configuration files:

### Odoo Config (`odoo.conf`)
Example:
```ini
[options]
db_name = my_odoo_db,another_db
data_dir = /var/lib/odoo
db_user = odoo
db_host = localhost
db_port = 5432
db_password = mysecretpassword
admin_passwd = admin
logfile = /var/log/odoo/odoo.log
# OR
log_dir = /var/log/odoo
```

- `db_name`: Comma-separated list of databases.
- `data_dir`: Odoo data directory (filestore at `data_dir/filestore`).
- `db_user`, `db_host`, `db_port`, `db_password`: PostgreSQL credentials.
- `admin_passwd`: Odoo admin password (not used in backup filenames).
- `logfile` or `log_dir`: Specifies the Odoo log directory for `odoo_db_manager.log`.

### Backup Config (`backup.conf`)
Example:
```ini
[backup]
backup_dir = /path/to/backup/directory
backup_db_names = my_odoo_db,another_db
backup_retention_days = 7

[logging]
log_file = /var/log/odoo/odoo_db_manager.log
log_retention_days = 7
```

- `[backup]`:
  - `backup_dir`: Directory for backup ZIP files.
  - `backup_db_names`: Databases to back up (overrides `odoo.conf`).
  - `backup_retention_days`: Days to retain backups (default: 7).
- `[logging]`:
  - `log_file`: Path to log file (default: `odoo_db_manager.log` in Odoo log directory or current directory).
  - `log_retention_days`: Days to retain log files (default: 7).

**Note**: Command-line arguments override both config files.

## Usage

Run the script with the desired action and options:

```bash
python3 odoo_db_manager.py <action> [options]
```

### Available Actions
- `backup`: Create compressed ZIP backups for specified databases.
- `restore`: Restore a database and filestore from a ZIP backup.
- `duplicate`: Copy a source database to a target database, with filestore.
- `drop_db`: Drop a database and its filestore.

### Common Options
- `--odoo-config`: Path to Odoo config file (e.g., `/etc/odoo/odoo.conf`).
- `--backup-config`: Path to backup config file (e.g., `backup.conf`).
- `--db-name`: Target database name (for restore, duplicate, drop_db).
- `--source-db`: Source database name (for duplicate).
- `--filestore-path`: Odoo filestore directory (overrides config).
- `--backup-dir`: Backup directory (overrides config).
- `--backup-file`: Path to backup ZIP file (for restore).
- `--db-user`, `--db-host`, `--db-port`, `--db-password`: PostgreSQL credentials.
- `--drop-existing`: Drop existing database before restoring or duplicating.
- `--without-filestore`: Exclude filestore in backup, restore, or duplicate (default: include filestore).
- `--no-verbose`: Disable detailed logging (default: verbose logging enabled).
- `--retention-days`: Days to retain backups (overrides config).
- `--log-file`: Path to log file (overrides config).
- `--log-retention-days`: Days to retain log files (overrides config).

### Examples

1. **Backup with Filestore**:
   ```bash
   python3 odoo_db_manager.py backup --odoo-config /etc/odoo/odoo.conf --backup-config backup.conf
   ```
   Creates ZIP files (e.g., `backup_my_odoo_db_2025-05-21_17-30-00.zip`), logs to `/var/log/odoo/odoo_db_manager.log`, cleans up logs older than 7 days.

2. **Backup without Filestore**:
   ```bash
   python3 odoo_db_manager.py backup --odoo-config /etc/odoo/odoo.conf --db-name my_odoo_db --without-filestore
   ```
   Creates a ZIP with only the database dump.

3. **Restore with Filestore**:
   ```bash
   python3 odoo_db_manager.py restore --odoo-config /etc/odoo/odoo.conf --db-name db_stg_test --backup-file /path/to/backup/backup_old_dbname_2025-05-21_17-30-00.zip --drop-existing
   ```
   Restores database and filestore, logs to `odoo_db_manager.log`.

4. **Restore without Filestore**:
   ```bash
   python3 odoo_db_manager.py restore --odoo-config /etc/odoo/odoo.conf --db-name db_stg_test --backup-file /path/to/backup/backup_old_dbname_2025-05-21_17-30-00.zip --drop-existing --without-filestore
   ```
   Restores only the database.

5. **Duplicate with Filestore**:
   ```bash
   python3 odoo_db_manager.py duplicate --odoo-config /etc/odoo/odoo.conf --source-db my_odoo_db --db-name db_stg_test --drop-existing
   ```

6. **Drop a Database**:
   ```bash
   python3 odoo_db_manager.py drop_db --odoo-config /etc/odoo/odoo.conf --db-name db_stg_test
   ```

7. **Custom Log File and Retention**:
   ```bash
   python3 odoo_db_manager.py backup --odoo-config /etc/odoo/odoo.conf --db-name my_odoo_db --log-file /logs/custom.log --log-retention-days 14
   ```

### Stopping Odoo Service
For restore, duplicate, or drop actions, stop the Odoo service to avoid conflicts:
```bash
sudo systemctl stop odoo
# Run command
sudo systemctl start odoo
```

## Logging

- **Script Logs**: Saved to `odoo_db_manager.log` in the Odoo log directory (e.g., `/var/log/odoo/`) or as specified by `--log-file` or `backup.conf`. Logs include timestamps and are rotated (10MB limit, 5 backups).
- **Log Retention**: Old log files (`odoo_db_manager.log.*`) are deleted after 7 days by default, configurable via `log_retention_days` in `backup.conf` or `--log-retention-days`.
- **PostgreSQL Logs**: Isolated to temporary files (e.g., `/tmp/<random>/pg_dump.log`). Included in `odoo_db_manager.log` only on errors. Verbose mode logs the temporary file paths for debugging.
- **Example Log Entry**:
  ```
  2025-05-21 17:30:00,123 - INFO - Starting restore for database db_stg_test from /path/to/backup/backup_old_dbname_2025-05-21_17-30-00.zip with filestore
  2025-05-21 17:30:00,124 - DEBUG - Extracting ZIP file to /tmp/tmpabc123
  ```

## Backup File Structure
Backups are ZIP files containing:
```
backup_<db_name>_<timestamp>.zip
├── dump.dump  # Compressed custom-format database dump
└── filestore/  # Only included unless --without-filestore is used
    └── <db_name>/
        ├── <attachment_files>
```

## Security Notes
- **Backup Filenames**: Exclude sensitive data (e.g., master password).
- **Database Credentials**: Use a `.pgpass` file in production instead of `--db-password` or `PGPASSWORD`.
- **Permissions**: Ensure the script user has write access to the Odoo log directory and backup directory.

## Troubleshooting

- **Logs Not in Expected Location**:
  - Check `backup.conf` for `log_file` or `odoo.conf` for `logfile`/`log_dir`.
  - Verify write permissions for the log directory.
  - If unavailable, logs fall back to `odoo_db_manager.log` in the current directory.
  - Check `odoo_db_manager.log` for errors:
    ```bash
    cat /var/log/odoo/odoo_db_manager.log
    ```

- **Old Logs Not Deleted**:
  - Verify `log_retention_days` in `backup.conf` or `--log-retention-days`.
  - Check log directory permissions.
  - Confirm cleanup logs:
    ```bash
    grep "Cleaning up old log files" /var/log/odoo/odoo_db_manager.log
    ```

- **PostgreSQL Errors**:
  - If a command fails, check `odoo_db_manager.log` for PostgreSQL output.
  - Example error:
    ```
    2025-05-21 17:30:00,123 - ERROR - Database restoration failed for db_stg_test: ...
    PostgreSQL output: pg_restore: error: could not connect to database
    ```
  - Verify PostgreSQL credentials and ensure `pg_restore` is installed.

- **Filestore Not Restored**:
  - Verify the ZIP contains `filestore/<db_name>/<files>` if `--without-filestore` was not used:
    ```bash
    unzip -l /path/to/backup/backup_old_dbname_2025-05-21_17-30-00.zip
    ```
  - Check `--filestore-path` is correct (e.g., `/var/lib/odoo/filestore`).

- **Debugging**:
  - Verbose logs are enabled by default. Disable with `--no-verbose` for quieter output.
  - Check temporary PostgreSQL log paths in verbose logs:
    ```bash
    grep "PostgreSQL logs at" /var/log/odoo/odoo_db_manager.log
    ```

- **Corrupted ZIP File**:
  - The script checks ZIP integrity during restoration. If it fails, verify the backup file:
    ```bash
    unzip -t /path/to/backup/backup.zip
    ```

- **Non-Standard Setup**:
  - If your Odoo version uses a different filestore path, specify `--filestore-path`.

## Contributing
Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/YourFeature`).
3. Commit changes (`git commit -m 'Add YourFeature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a Pull Request.

Please include tests and update documentation as needed.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact
For questions or support, open an issue or contact [Hariprasath](https://www.linkedin.com/in/hari4274).

---

⭐ **Star this repository** if you find it useful! Contributions and feedback are greatly appreciated.