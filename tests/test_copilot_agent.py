from pathlib import Path

from v2m.copilot_agent import ProducerCopilotAgent


def test_agent_fallback_without_api_key() -> None:
    agent = ProducerCopilotAgent(api_key=None)
    result = agent.run_turn(
        chat_history=[],
        user_prompt="help me make music",
        audio_inputs={},
        active_project=None,
    )
    assert "OPENAI_API_KEY" in result.assistant_text


def test_generate_sketch_tool_creates_midi(tmp_path: Path) -> None:
    agent = ProducerCopilotAgent(
        api_key=None,
        projects_dir=tmp_path / "projects",
        sketch_dir=tmp_path / "out",
    )
    payload, _, sketch = agent._execute_tool(  # noqa: SLF001 - validated internal path
        name="generate_midi_sketch",
        args={"style": "pop", "key": "C major", "bpm": 120, "bars": 8, "complexity": 6},
        audio_inputs={},
        active_project=None,
        existing_sketch=None,
    )
    assert "sketch_midi" in payload
    assert sketch is not None
    assert sketch.exists()
