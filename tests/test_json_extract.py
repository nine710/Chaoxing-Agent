"""模型响应 JSON 提取工具的回归测试。"""

from models.json_extract import extract_all_json_objects


def test_extract_json_object_with_braces_inside_string_after_prose():
    text = (
        '答案如下：'
        '{"question_type":"single_choice","answer":["A"],'
        '"confidence":0.9,"reason":"集合 A={1,2} 满足条件"}'
    )

    objs = extract_all_json_objects(text)

    assert len(objs) == 1
    assert objs[0]["answer"] == ["A"]
    assert objs[0]["reason"] == "集合 A={1,2} 满足条件"


def test_extract_json_object_with_escaped_quote_and_braces_inside_string():
    text = (
        '模型输出：'
        '{"reason":"他说 \\"A={1,2}\\" 是正确的",'
        '"answer":["A"],"confidence":0.9,"question_type":"single_choice"}'
    )

    objs = extract_all_json_objects(text)

    assert len(objs) == 1
    assert objs[0]["reason"] == '他说 "A={1,2}" 是正确的'


def test_extract_multiple_json_objects_keeps_order():
    text = (
        '{"key":"A","text":"选项 A"} 然后 '
        '{"question_type":"single_choice","answer":["A"],"confidence":0.9,"reason":"ok"}'
    )

    objs = extract_all_json_objects(text)

    assert objs[0]["key"] == "A"
    assert objs[1]["answer"] == ["A"]
