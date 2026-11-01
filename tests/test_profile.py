"""全局画像读写与去重"""

from deepdocument.memory import profile as profile_mod
from deepdocument.memory.profile import load_profile, save_profile, update_profile


def test_profile_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", tmp_path / "user_profile.md")

    update_profile("按结论归类，不要逐篇罗列")
    loaded = load_profile()
    assert "结论" in loaded.structure or any("结论" in r for r in loaded.rejects)

    update_profile("按结论归类，不要逐篇罗列")  # 去重
    again = load_profile()
    assert again.structure == loaded.structure
    assert again.rejects == loaded.rejects


def test_reject_feedback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", tmp_path / "user_profile.md")

    update_profile("不要把检索词直接写成标题")
    loaded = load_profile()
    assert any("检索词" in r for r in loaded.rejects)
