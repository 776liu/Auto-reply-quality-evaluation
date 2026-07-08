import json
from pathlib import Path
from typing import List, Dict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def load_and_align(
        auto_file: str = "task3_auto_replies.json",
        human_file: str = "task3_human_ref.json"
) ->List[Dict]:
    """
    读取并校验两个 JSON 文件，按 id 对齐数据。
    返回:List[dict]，每个元素包含 id, auto_reply, human_reference, annotator_notes。
    """

    auto_path = DATA_DIR / auto_file
    if not auto_path.exists():
        raise FileNotFoundError(f"回复文件不存在：{auto_path}")
    
    with open(auto_path, "r", encoding="utf-8") as f:
        auto_data = json.load(f)

    human_path = DATA_DIR / human_file
    if not human_path.exists():
        raise FileNotFoundError(f"人工参考文件不存在：{human_path}")
    
    with open(human_path, "r", encoding="utf-8") as f:
        human_data = json.load(f)

    if not isinstance(auto_data, list):
        raise ValueError("自动回复文件内容应为Json数组:")
    if not isinstance(human_data, list):
        raise ValueError("人工参考文件内容应为Json数组:")
    
    aligned = []
    auto_by_id: Dict[str, str] = {}
    for item in auto_data:
        auto_by_id[item["id"]] = {
            "auto_reply": item.get("auto_reply", ""),
            "user_question": item.get("user_question", "")
            }

    for item in human_data:
        case_id = item["id"]
        if case_id not in auto_by_id:
            raise ValueError(f"人工参考文件中的 id={case_id} 在自动回复文件中不存在")
        
        aligned.append({
            "id": case_id,
            "user_question": auto_by_id[case_id]["user_question"],
            "auto_reply": auto_by_id[case_id]["auto_reply"],
            "human_reference": item.get("human_reference", ""),
            "annotator_notes": item.get("annotator_notes", "")
        })

    if len(aligned) == 0:
        raise RuntimeError("对齐后数据为空，请检查输入文件")

    return aligned

if __name__ == '__main__':
    cases = load_and_align()
    print(f"成功加载 {len(cases)} 条数据")
    for case in cases[:2]:
        print(f"  - {case['id']}: auto_reply 长度={len(case['auto_reply'])}")
    
    
    

    



