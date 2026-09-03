def parse_admin_ids(*values: str | None) -> frozenset[str]:
    """把逗号分隔的管理员 QQ 字符串解析成集合。

    - 多个 QQ 用英文逗号分隔, 每个 ID 前后的空白会被忽略。
    - 传入多个参数时取第一个非空者, 用于「优先 X, 留空回退 ADMIN_ID」的场景,
      例如 parse_admin_ids(PERSONA_ADMIN_IDS, ADMIN_ID)。
    - 全部为空时返回空集合 (语义上 = 无人是管理员)。
    """
    raw = next((value for value in values if value and value.strip()), "")
    return frozenset(item.strip() for item in raw.split(",") if item.strip())
