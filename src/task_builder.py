from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent.parent / "config"


class TaskBuilder:
    def __init__(self, template_file: str = "prompt_template.txt"):
        self.template_path = PROMPT_DIR / template_file
        with open(self.template_path, "r", encoding="utf-8") as f:
            self.template = f.read()

    def build_prompt(self, case: dict) -> str:
        """
        注入具体字段到模板。
        case: 来自 Loader 的 Case 字典
        """
        return self.template.format(
            user_question=case.get("user_question", ""),
            auto_reply=case.get("auto_reply", ""),
            human_reference=case.get("human_reference", ""),
            notes=case.get("annotator_notes", "")
        )