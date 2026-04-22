import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from job_hunter_agent.core.skill_taxonomy import (
    get_runtime_skill_taxonomy,
    load_skill_taxonomy,
    set_runtime_skill_taxonomy_path,
)


class SkillTaxonomyTests(TestCase):
    def setUp(self) -> None:
        self._original_runtime_path = Path("./skill_taxonomy.json")
        set_runtime_skill_taxonomy_path(self._original_runtime_path)

    def tearDown(self) -> None:
        set_runtime_skill_taxonomy_path(self._original_runtime_path)

    def test_load_skill_taxonomy_reads_valid_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "taxonomy.json"
            path.write_text(
                json.dumps(
                    {
                        "skill_aliases": {
                            "python": ["python", "cpython"],
                            "sql": ["sql"],
                        },
                        "primary_stack_keywords": ["python"],
                        "secondary_stack_keywords": ["sql"],
                        "leadership_keywords": ["mentoria"],
                    }
                ),
                encoding="utf-8",
            )
            taxonomy = load_skill_taxonomy(path)

        self.assertEqual(taxonomy.skill_aliases["python"], ("python", "cpython"))
        self.assertEqual(taxonomy.primary_stack_keywords, ("python",))
        self.assertEqual(taxonomy.secondary_stack_keywords, ("sql",))
        self.assertEqual(taxonomy.leadership_keywords, ("mentoria",))
        self.assertEqual(taxonomy.prompt_focus_stacks, ("python", "sql"))

    def test_get_runtime_skill_taxonomy_uses_runtime_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "taxonomy.json"
            path.write_text(
                json.dumps(
                    {
                        "skill_aliases": {"go": ["go", "golang"]},
                        "primary_stack_keywords": ["go"],
                        "secondary_stack_keywords": ["kubernetes"],
                        "leadership_keywords": ["lideranca"],
                    }
                ),
                encoding="utf-8",
            )
            set_runtime_skill_taxonomy_path(path)
            taxonomy = get_runtime_skill_taxonomy()

        self.assertEqual(taxonomy.skill_aliases["go"], ("go", "golang"))
        self.assertEqual(taxonomy.primary_stack_keywords, ("go",))
