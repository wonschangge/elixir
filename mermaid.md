```mermaid
flowchart TD
    IMPORT_ENV[source ~/.elixir.rc] -->|导入环境变量| SCRIPTS
    SCRIPTS(./scripts.sh list-tags) --> |更新数据库| UPDATE
    UPDATE(./update.py 10)
```