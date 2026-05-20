from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_app_shell_sidebar_can_be_collapsed():
    shell = (ROOT / "web/src/components/layout/AppShell.vue").read_text(encoding="utf-8")
    styles = "\n".join(
        [
            (ROOT / "web/src/styles/main.css").read_text(encoding="utf-8"),
            (ROOT / "web/src/styles/shell.css").read_text(encoding="utf-8"),
        ]
    )

    assert "sideCollapsed" in shell
    assert "隐藏导航栏" in shell
    assert "显示导航栏" in shell
    assert "side-collapsed" in shell
    assert ".app-shell.side-collapsed" in styles
    assert ".side-restore" in styles
