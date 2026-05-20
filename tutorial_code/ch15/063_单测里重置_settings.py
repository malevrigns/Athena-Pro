def test_with_custom_settings(monkeypatch):
    get_settings.cache_clear()                # 清缓存
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    s = get_settings()                         # 新实例,带 fake
    assert s.llm.model == "fake-model"