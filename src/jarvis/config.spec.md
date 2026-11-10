# Configuration File Selection

`get_config_path()` selects the file shared by runtime loading and desktop configuration operations. A non-empty `JARVIS_CONFIG_PATH` takes precedence and expands home-directory notation. Without it, a non-empty `XDG_CONFIG_HOME` supplies the directory containing `jarvis/config.json`; otherwise the file is `~/.config/jarvis/config.json`. Relative explicit paths retain their relative meaning.

`load_config()` and `load_settings()` use this selection for reads and migrations. Settings, setup-wizard pages, feature-state notices and the configuration-directory action use the same selection for reads, writes and navigation. Selecting an explicit file does not read or overwrite the normal per-user file.

Saved opaque keys and literal values survive the existing migration and desktop-save boundaries. Configuration values, defaults and model resolution are independent of path selection.

## Diagnostic switch

`JARVIS_VOICE_DEBUG=1` enables diagnostics. Typed Settings and debug logging read this process environment flag through the same helper. Runtime settings loading applies dotenv during normal configuration initialisation. Logging itself reads the current environment without loading, migrating or writing JSON configuration, creating directories or caching the switch. Diagnostic output uses stderr and cannot interrupt the caller when that stream is unavailable.

## Runtime settings

Every declared default is represented in typed runtime Settings. Saved values take precedence independently, including `llm_thinking_enabled`, `intent_judge_thinking_enabled` and `dictation_thinking_enabled`. These switches default to disabled and apply to their respective LLM contexts.

`stop_commands` supplies the listener's text interruption phrases. An empty list disables text interruption phrases; intent judgement retains its stop decisions. `stop_command_fuzzy_ratio` supplies the same threshold to short-control matching and standalone-control priority during TTS echo handling. List normalisation follows the shared configuration list parser.

## Secret references

A config value of the form `keyring:<service>/<name>`, or `keyring:<name>` for the `jarvis` service, names a secret in the operating system keyring. `load_settings()` resolves references in `llm_api_key`, `embedding_api_key`, `brave_search_api_key` and in every string nested inside `mcps`, so typed runtime Settings carry the secret while the file carries the reference. Literal values pass through unchanged.

Resolution never writes to the config file. A reference whose secret is missing, or whose keyring is unavailable, resolves to an empty string; the reference text is never used as a credential. Diagnostics name the service and secret name only, never the value.

`load_config()` and desktop configuration reads return the saved values, so the settings window and setup wizard show and preserve references as written. `python -m jarvis.secret_store set|delete <name>` manages stored secrets; `set` reads the value from a hidden prompt and prints the reference to place in the config.

## Reply language and extra instructions

`reply_language` and `system_prompt_extra` default to empty strings and are trimmed on load. A non-empty `reply_language` makes the chat model's system message instruct it to respond in that language regardless of the user's language, in place of the English instruction that applies when the text-to-speech engine is Piper or Chatterbox. `system_prompt_extra` is appended to the same system message verbatim. Both reach every reply turn through the typed Settings.
