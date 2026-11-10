"""The reply language and extra instructions reach the chat model's system message."""
from unittest.mock import patch

import pytest

from jarvis.config import get_default_config, load_settings
from jarvis.reply import engine


def _system_message(cfg, db, dialogue_memory):
    systems = []

    def chat(**kwargs):
        systems.append(kwargs['messages'][0]['content'])
        return {'message': {'role': 'assistant', 'content': 'Goed.'}}

    with patch.object(engine, 'select_tools', return_value=['stop']), \
         patch.object(engine, 'plan_query', return_value=['Reply to the user.']), \
         patch.object(engine, 'chat_with_messages', side_effect=chat):
        engine.run_reply_engine(db, cfg, None, 'Hallo', dialogue_memory, quiet=True)
    return systems[0]


@pytest.mark.unit
def test_configured_reply_language_replaces_english_default(mock_config, db, dialogue_memory):
    mock_config.reply_language = 'Dutch'
    system = _system_message(mock_config, db, dialogue_memory)
    assert 'Always respond in Dutch' in system
    assert 'Always respond in English' not in system


@pytest.mark.unit
def test_unset_reply_language_keeps_english_default(mock_config, db, dialogue_memory):
    mock_config.reply_language = ''
    assert 'Always respond in English' in _system_message(mock_config, db, dialogue_memory)


@pytest.mark.unit
def test_extra_instructions_are_appended_verbatim(mock_config, db, dialogue_memory):
    mock_config.system_prompt_extra = 'Check the house with a tool before answering.'
    assert 'Check the house with a tool before answering.' in _system_message(mock_config, db, dialogue_memory)


@pytest.mark.unit
def test_blank_extra_instructions_add_nothing(mock_config, db, dialogue_memory):
    mock_config.system_prompt_extra = '   '
    system = _system_message(mock_config, db, dialogue_memory)
    mock_config.system_prompt_extra = ''
    assert system == _system_message(mock_config, db, dialogue_memory)


@pytest.mark.unit
def test_defaults_are_empty():
    defaults = get_default_config()
    assert defaults['reply_language'] == ''
    assert defaults['system_prompt_extra'] == ''


@pytest.mark.unit
def test_settings_carry_saved_values(monkeypatch, tmp_path):
    cfg_path = tmp_path / 'config.json'
    cfg_path.write_text('{"reply_language": " Dutch ", "system_prompt_extra": " Use tools. "}', encoding='utf-8')
    monkeypatch.setenv('JARVIS_CONFIG_PATH', str(cfg_path))
    settings = load_settings()
    assert settings.reply_language == 'Dutch'
    assert settings.system_prompt_extra == 'Use tools.'
