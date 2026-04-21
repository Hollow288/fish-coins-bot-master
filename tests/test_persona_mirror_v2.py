import importlib.util
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "fish_coins_bot" / "plugins" / "persona_mirror"


def _ensure_package(name: str, path: Path) -> None:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    module.__path__ = [str(path)]


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_ensure_package("fish_coins_bot", REPO_ROOT / "fish_coins_bot")
_ensure_package("fish_coins_bot.plugins", REPO_ROOT / "fish_coins_bot" / "plugins")
_ensure_package("fish_coins_bot.plugins.persona_mirror", PLUGIN_DIR)
_ensure_package("fish_coins_bot.plugins.persona_mirror.services", PLUGIN_DIR / "services")

profile_schema = _load_module(
    "fish_coins_bot.plugins.persona_mirror.profile_schema",
    PLUGIN_DIR / "profile_schema.py",
)
prompts = _load_module(
    "fish_coins_bot.plugins.persona_mirror.prompts",
    PLUGIN_DIR / "prompts.py",
)


config_module = types.ModuleType("fish_coins_bot.plugins.persona_mirror.config")
config_module.get_plugin_config = lambda: types.SimpleNamespace(summary_batch_size=30)
sys.modules["fish_coins_bot.plugins.persona_mirror.config"] = config_module

models_module = types.ModuleType("fish_coins_bot.plugins.persona_mirror.models")
models_module.PersonaCorrection = type("PersonaCorrection", (), {})
models_module.PersonaProfileState = type("PersonaProfileState", (), {})
models_module.PersonaProfileSnapshot = type("PersonaProfileSnapshot", (), {})
models_module.PersonaTarget = type("PersonaTarget", (), {})
sys.modules["fish_coins_bot.plugins.persona_mirror.models"] = models_module

persona_service = _load_module(
    "fish_coins_bot.plugins.persona_mirror.services.persona_service",
    PLUGIN_DIR / "services" / "persona_service.py",
)


class PersonaMirrorV2Tests(unittest.TestCase):
    def test_parse_basic_info_text(self) -> None:
        profile = profile_schema.parse_basic_info_text("字节 2-1 后端工程师 男")
        self.assertEqual(profile["company"], "字节跳动")
        self.assertEqual(profile["level"], "2-1")
        self.assertEqual(profile["role"], "后端工程师")
        self.assertEqual(profile["gender"], "男")

    def test_parse_persona_tags_text(self) -> None:
        profile = profile_schema.parse_persona_tags_text(
            "INTJ 摩羯座 甩锅高手 字节范 CR很严格但从来不解释原因"
        )
        self.assertEqual(profile["mbti"], "INTJ")
        self.assertEqual(profile["zodiac"], "摩羯座")
        self.assertIn("甩锅高手", profile["personality_tags"])
        self.assertIn("字节范", profile["culture_tags"])
        self.assertIn("CR很严格但从来不解释原因", profile["subjective_impression"])

    def test_parse_persona_tags_text_replaces_old_tag_fields(self) -> None:
        current = profile_schema.parse_persona_tags_text("INTJ 只读不回 字节范 老是潜水")
        updated = profile_schema.parse_persona_tags_text("ENFP 秒回强迫症 腾讯味 喜欢半夜秒回", current)
        self.assertEqual(updated["mbti"], "ENFP")
        self.assertEqual(updated["personality_tags"], ["秒回强迫症"])
        self.assertEqual(updated["culture_tags"], ["腾讯味"])
        self.assertEqual(updated["subjective_impression"], "喜欢半夜秒回")

    def test_legacy_profile_migrates_to_v2(self) -> None:
        legacy_profile = {
            "catchphrases": ["确实", "离谱"],
            "habit_words": ["我看看"],
            "sentence_style": {
                "avg_length": "12",
                "typical_length_range": "3-20",
                "structure": "短句为主",
                "punctuation": ["?", "~"],
                "rhythm": "快",
                "ending_habits": ["啊"],
            },
        }
        migrated = profile_schema.normalize_v2_profile(legacy_profile)
        self.assertEqual(migrated["version"], 2)
        self.assertEqual(migrated["layers"]["expression"]["catchphrases"], ["确实", "离谱"])
        self.assertEqual(migrated["layers"]["expression"]["sentence_style"]["avg_length"], "12")

    def test_manual_tags_override_conflicts(self) -> None:
        manual_inputs = profile_schema.parse_persona_tags_text("秒回强迫症")
        composed = profile_schema.compose_v2_profile(
            current_profile={},
            analyzer_delta={
                "expression": {},
                "decisions": {},
                "interpersonal": {},
                "boundaries": {},
                "inferred_tags": ["只读不回"],
                "conflicts": [],
            },
            builder_profile=None,
            manual_inputs=manual_inputs,
            corrections=[],
        )
        self.assertTrue(composed["pending_conflicts"])
        self.assertTrue(
            any("看到消息会很快给反馈" in rule for rule in composed["layers"]["core_rules"])
        )

    def test_corrections_flow_into_hard_constraints(self) -> None:
        profile = profile_schema.rebuild_profile_with_overrides(
            current_profile={},
            manual_inputs=profile_schema.parse_persona_tags_text("直接"),
            corrections=[
                {
                    "scene": "被催进度",
                    "wrong": "直接回收到",
                    "correct": "先问清楚截止时间再表态",
                }
            ],
        )
        hard_constraints = profile["compiled_reply_profile"]["hard_constraints"]
        self.assertTrue(any("被催进度" in item for item in hard_constraints))
        self.assertTrue(any("截止时间" in item for item in hard_constraints))

    def test_rebuild_profile_clears_stale_pending_conflicts(self) -> None:
        manual_inputs = profile_schema.parse_persona_tags_text("秒回强迫症")
        current = profile_schema.compose_v2_profile(
            current_profile={},
            analyzer_delta={
                "expression": {},
                "decisions": {},
                "interpersonal": {},
                "boundaries": {},
                "inferred_tags": ["只读不回"],
                "conflicts": [{"field": "personality_tags", "manual": "秒回强迫症", "inferred": "只读不回"}],
            },
            builder_profile=None,
            manual_inputs=manual_inputs,
            corrections=[],
        )
        rebuilt = profile_schema.rebuild_profile_with_overrides(
            current,
            manual_inputs=manual_inputs,
            corrections=[],
        )
        self.assertTrue(current["pending_conflicts"])
        self.assertEqual(rebuilt["pending_conflicts"], [])

    def test_refresh_snapshot_payload_uses_current_profile_state(self) -> None:
        state = types.SimpleNamespace(last_summary_message_id=42)
        payload = persona_service._build_refresh_snapshot_payload(
            target_user_id="123",
            profile_json={"version": 2},
            profile_state=state,
            reason="manual_inputs_updated",
        )
        self.assertEqual(payload["target_user_id"], "123")
        self.assertEqual(payload["summary_type"], "manual_refresh")
        self.assertEqual(payload["start_message_id"], 42)
        self.assertEqual(payload["end_message_id"], 42)
        self.assertEqual(payload["summary_json"], {"version": 2})
        self.assertIn("manual_inputs_updated", payload["prompt_text"])

    def test_prompts_include_manual_and_non_expression_layers(self) -> None:
        manual_inputs = profile_schema.parse_persona_tags_text("INTJ 字节范 甩锅高手")
        analyzer_prompt = prompts.build_analyzer_prompt(
            current_profile=profile_schema.normalize_v2_profile({}),
            incremental_stats={"sample_count": 3},
            sample_messages=["先对齐一下 context", "impact 是什么"],
            manual_inputs=manual_inputs,
            context_samples=[{"scene_type": "被@后回应", "target_said": "先说结论"}],
        )
        self.assertIn("manual_inputs", analyzer_prompt)
        self.assertIn("decisions", analyzer_prompt)
        self.assertIn("interpersonal", analyzer_prompt)

        compiled_profile = profile_schema.rebuild_profile_with_overrides(
            current_profile={},
            manual_inputs=manual_inputs,
            corrections=[
                {
                    "scene": "被质疑方案",
                    "wrong": "直接认错",
                    "correct": "先反问判断依据",
                }
            ],
        )["compiled_reply_profile"]
        speak_prompt = prompts.build_speak_prompt(
            target_identity={"display_name": "张三", "aliases": ["张三"]},
            compiled_reply_profile=compiled_profile,
            intent_text="回一句",
            recent_chat_messages=[{"text": "这个方案不太行"}],
            similar_messages=["impact 是什么"],
            top_face_ids=["13"],
            conversation_snippets=[{"scene_type": "被质疑方案", "target_replies": ["你的依据是什么"]}],
            trigger_reason={"at_target_user": True},
        )
        self.assertIn("active_corrections", speak_prompt)
        self.assertIn("decisions", speak_prompt)
        self.assertIn("boundaries", speak_prompt)


if __name__ == "__main__":
    unittest.main()
