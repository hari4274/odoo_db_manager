# Odoo Database Manager (odoo_db_manager)

![Python](https://img.shields.io/badge/Python-3.6%2B-blue)
![Odoo](https://img.shields.io/badge/Odoo-10%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

A versatile Python script for managing Odoo databases, providing backup, restore, duplicate, drop, and create functionalities. Compatible with all Odoo versions (10+) using PostgreSQL and the standard backup format.

## Features

- **Backup**: Create secure ZIP backups (`backup_<db_name>_<timestamp>.zip`) of Odoo databases and filestores, excluding sensitive data like the master password.
- **Restore**: Restore databases and filestores from ZIP backups, handling mismatched filestore directory names (e.g., `filestore/old_dbname` to `target_db`).
- **Duplicate**: Copy an existing Odoo database and filestore to a new database.
- **Drop Database**: Safely drop a database and its filestore, terminating active connections.
- **Create Database**: Create an empty Odoo database and filestore directory, ready for initialization.
- **Configuration**: Supports Odoo (`odoo.conf`) and backup (`backup.conf`) config files, with command-line overrides.
- **Retention Policy**: Automatically clean up old backups based on a retention period.
- **Generic Compatibility**: Works with any Odoo version (10 to 18+) using standard PostgreSQL commands.

## Prerequisites

- **Python**: 3.6 or higher
- **PostgreSQL**: With `pg_dump`, `psql`, `createdb`, and `dropdb` utilities installed
- **Odoo**: Any version (10+) with a valid configuration file
- **Permissions**: 
  - PostgreSQL user must have permissions to create, drop, and restore databases.
  - Write access to the Odoo filestore directory and backup directory.

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
```

- `db_name`: Comma-separated list of databases.
- `data_dir`: Odoo data directory (filestore at `data_dir/filestore`).
- `db_user`, `db_host`, `db_port`, `db_password`: PostgreSQL credentials.
- `admin_passwd`: Odoo admin password (not used in backup filenames).

### Backup Config (`backup.conf`)
Example:
```ini
[backup]
backup_dir = /path/to/backup/directory
backup_db_names = my_odoo_db,another_db
backup_retention_days = 7
```

- `backup_dir`: Directory for backup ZIP files.
- `backup_db_names`: Databases to back up (overrides `odoo.conf`).
- `backup_retention_days`: Days to retain backups.

**Note**: Command-line arguments override both config files.

## Usage

Run the script with the desired action and options:

```bash
python3 odoo_db_manager.py <action> [options]
```

### Available Actions
- `backup`: Create backups for specified databases.
- `restore`: Restore a database and filestore from a ZIP backup.
- `duplicate`: Copy a source database to a target database.
- `drop_db`: Drop a database and its filestore.
- `create_db`: Create an empty database and filestore directory.

### Common Options
- `--odoo-config`: Path to Odoo config file (e.g., `/etc/odoo/odoo.conf`).
- `--backup-config`: Path to backup config file (e.g., `backup.conf`).
- `--db-name`: Target database name (for restore, duplicate, drop_db, create_db).
- `--source-db`: Source database name (for duplicate).
- `--filestore-path`: Odoo filestore directory (overrides config).
- `--backup-dir`: Backup directory (overrides config).
- `--backup-file`: Path to backup ZIP file (for restore).
- `--db-user`, `--db-host`, `--db-port`, `--db-password`: PostgreSQL credentials.
- `--drop-existing`: Drop existing database before restoring or duplicating.
- `--retention-days`: Days to retain backups (overrides config).

### Examples

1. **Backup Databases**:
   ```bash
   python3 odoo_db_manager.py backup --odoo-config /etc/odoo/odoo.conf --backup-config backup.conf
   ```
   Creates ZIP files (e.g., `backup_my_odoo_db_2025-05-21_15-17-00.zip`) in the backup directory.

2. **Restore a Database**:
   ```bash
   python3 odoo_db_manager.py restore --odoo-config /etc/odoo/odoo.conf --db-name alb_stg_test --backup-file /path/to/backup/backup_old_dbname_2025-05-21_15-17-00.zip --drop-existing
   ```
   Restores the database and filestore, handling mismatched filestore names.

3. **Duplicate a Database**:
   ```bash
   python3 odoo_db_manager.py duplicate --odoo-config /etc/odoo/odoo.conf --source-db my_odoo_db --db-name my_odoo_db_copy --drop-existing
   ```

4. **Drop a Database**:
   ```bash
   python3 odoo_db_manager.py drop_db --odoo-config /etc/odoo/odoo.conf --db-name alb_stg_test
   ```

5. **Create a Database**:
   ```bash
   python3 odoo_db_manager.py create_db --odoo-config /etc/odoo/odoo.conf --db-name alb_stg_test
   ```

### Stopping Odoo Service
For restore, duplicate, or drop actions, stop the Odoo service to avoid conflicts:
```bash
sudo systemctl stop odoo
# Run command
sudo systemctl start odoo
```

## Backup File Structure
Backups are ZIP files containing:
```
backup_<db_name>_<timestamp>.zip
├── dump.sql
└── filestore/
    └── <db_name>/
        ├── <attachment_files>
```

## Security Notes
- **Backup Filenames**: Exclude sensitive data (e.g., master password).
- **Database Credentials**: Use a `.pgpass` file in production instead of `--db-password` or `PGPASSWORD`.
- **Permissions**: Ensure the script user has access to the filestore and PostgreSQL.

## Troubleshooting
- **Filestore Not Restored**:
  - Verify the ZIP contains `filestore/<db_name>/<files>`:
    ```bash
    unzip -l /path/to/backup/backup_old_dbname_2025-05-21_15-17-00.zip
    ```
  - Check `--filestore-path` is correct (e.g., `/var/lib/odoo/filestore`).
- **Database Errors**:
  - Ensure PostgreSQL credentials and permissions are correct.
  - Stop Odoo before restore, duplicate, or drop actions.
- **Non-Standard Setup**:
  - If your Odoo version uses a different filestore path or backup format, open an issue with details.

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