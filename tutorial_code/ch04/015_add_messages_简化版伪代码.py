def add_messages(existing: list, new: list) -> list:
    # 1. 规范化:把 dict 格式转成 Message 对象
    existing = [_to_message(m) for m in existing]
    new = [_to_message(m) for m in new]
    
    # 2. 处理 REMOVE_ALL_MESSAGES 哨兵
    if any(m is REMOVE_ALL_MESSAGES for m in new):
        # 找到最后一个 REMOVE_ALL_MESSAGES,之后的留下,之前的全清
        idx = max(i for i, m in enumerate(new) if m is REMOVE_ALL_MESSAGES)
        existing = []
        new = new[idx+1:]
    
    # 3. 给没有 id 的消息生成 uuid
    for m in new:
        if m.id is None:
            m.id = generate_uuid()
    
    # 4. 按 id 合并:同 id 的新消息替换旧消息,新 id 的追加
    existing_ids = {m.id: i for i, m in enumerate(existing)}
    result = list(existing)
    for m in new:
        if m.id in existing_ids:
            result[existing_ids[m.id]] = m   # 替换
        else:
            result.append(m)                  # 追加
    
    return result