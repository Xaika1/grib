import re

from app.core.errors import QueryError

_TOKENS = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|`[^`]*`|--[^\n]*|/\*.*?\*/", re.S)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|upsert|drop|alter|create|truncate|grant|revoke|attach|detach|pragma|"
    r"vacuum|copy|call|into|outfile|dumpfile|lock|unlock|handler|load_file|pg_sleep|sleep|benchmark|"
    r"set_config|pg_read_file|pg_read_binary_file|pg_ls_\w+|pg_stat_file|pg_terminate_backend|pg_cancel_backend|"
    r"pg_reload_conf|pg_rotate_logfile|pg_switch_wal|pg_promote|pg_create_restore_point|pg_advisory\w*|"
    r"pg_notify|lo_\w+|dblink\w*|query_to_xml\w*|cursor_to_xml\w*|table_to_xml\w*|database_to_xml\w*|schema_to_xml\w*)\b",
    re.I,
)


def _strip(sql: str) -> str:
    def repl(m: re.Match) -> str:
        tok = m.group(0)
        if tok[0] == "'":
            return "''"
        if tok[0] in "\"`":
            return " " + tok[1:-1] + " "
        return " "

    return _TOKENS.sub(repl, sql)


def check(sql: str) -> str:
    text = (sql or "").strip()
    while text.endswith(";"):
        text = text[:-1].rstrip()
    if not text:
        raise QueryError("Пустой запрос")

    bare = _strip(text).strip()
    if ";" in bare:
        raise QueryError("Разрешён только один запрос, без «;» внутри")
    first = bare.split(None, 1)[0].lower() if bare else ""
    if first not in ("select", "with"):
        raise QueryError("Разрешены только запросы SELECT")
    bad = _FORBIDDEN.search(bare)
    if bad:
        raise QueryError(f"Запрещённое слово в запросе: {bad.group(1).upper()}")
    return text
