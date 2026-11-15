"""answer_parser 基础单测。"""

from apps.scar.services.answer_parser import parse_answer_path_value


def test_parse_slash_path():
    r = parse_answer_path_value("2号楼/3层/窗宽 为 1500mm。")
    assert r["pred_path"] == "2号楼/3层/窗宽"
    assert float(r["pred_value"]) == 1500.0


def test_parse_oral():
    r = parse_answer_path_value("1号楼2层的层高是2800毫米。")
    assert r["pred_path"] == "1号楼/2层/层高"
    assert float(r["pred_value"]) == 2800.0
