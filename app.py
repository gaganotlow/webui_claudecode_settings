#!/usr/bin/env python3

import io
import json
import os
import tomllib
import uuid
from datetime import datetime

import toml
from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)

DEFAULT_CLAUDE_HOME = os.path.expanduser("~/.claude")
DEFAULT_CODEX_HOME = os.path.expanduser("~/.codex")
APP_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "webui_config.json")

CLAUDE_ENV_KEYS = [
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_REASONING_MODEL",
]

CODEX_ENV_KEYS = [
    "OPENAI_API_KEY",
    "base_url",
    "model",
    "model_provider",
    "review_model",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def read_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def read_toml(path):
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def write_toml(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        toml.dump(data, f)


# ---------------------------------------------------------------------------
# Claude paths & operations
# ---------------------------------------------------------------------------

def get_claude_home_dir():
    data = read_json(APP_CONFIG_PATH)
    # backward compat: also check old "home_dir" key
    home = data.get("claude_home_dir") or data.get("home_dir") or DEFAULT_CLAUDE_HOME
    return os.path.abspath(os.path.expanduser(home))


def get_claude_settings_path():
    return os.path.join(get_claude_home_dir(), "settings.json")


def get_claude_profiles_path():
    return os.path.join(get_claude_home_dir(), "profiles.json")


def get_claude_current_env():
    settings = read_json(get_claude_settings_path())
    env = settings.get("env", {})
    return {k: env.get(k, "") for k in CLAUDE_ENV_KEYS}


def apply_claude_env(env_vars):
    settings = read_json(get_claude_settings_path())
    if "env" not in settings:
        settings["env"] = {}
    for k, v in env_vars.items():
        if k in CLAUDE_ENV_KEYS:
            settings["env"][k] = v
    write_json(get_claude_settings_path(), settings)


def normalize_claude_profile(profile):
    profile.setdefault("name", "未命名")
    profile.setdefault("group", "默认")
    profile.setdefault("env", {})
    for key in CLAUDE_ENV_KEYS:
        profile["env"].setdefault(key, "")
    return profile


def get_claude_profiles():
    data = read_json(get_claude_profiles_path())
    return [normalize_claude_profile(p) for p in data.get("profiles", [])]


def save_claude_profiles(profiles):
    write_json(get_claude_profiles_path(), {"profiles": profiles})


# ---------------------------------------------------------------------------
# Codex paths & operations
# ---------------------------------------------------------------------------

def get_codex_home_dir():
    data = read_json(APP_CONFIG_PATH)
    return os.path.abspath(os.path.expanduser(
        data.get("codex_home_dir", DEFAULT_CODEX_HOME)))


def get_codex_auth_path():
    return os.path.join(get_codex_home_dir(), "auth.json")


def get_codex_config_toml_path():
    return os.path.join(get_codex_home_dir(), "config.toml")


def get_codex_profiles_path():
    return os.path.join(get_codex_home_dir(), "profiles.json")


def get_codex_current_env():
    """Read current Codex config from auth.json + config.toml."""
    auth = read_json(get_codex_auth_path())
    config = read_toml(get_codex_config_toml_path())

    provider_name = config.get("model_provider", "")
    provider_config = config.get("model_providers", {}).get(provider_name, {})

    return {
        "OPENAI_API_KEY": auth.get("OPENAI_API_KEY", ""),
        "base_url": provider_config.get("base_url", ""),
        "model": config.get("model", ""),
        "model_provider": provider_name,
        "review_model": config.get("review_model", ""),
    }


def apply_codex_env(env_vars):
    """Write Codex env vars back to auth.json + config.toml."""
    # --- auth.json ---
    auth_path = get_codex_auth_path()
    auth = read_json(auth_path)
    if env_vars.get("OPENAI_API_KEY"):
        auth["auth_mode"] = "apikey"
        auth["OPENAI_API_KEY"] = env_vars["OPENAI_API_KEY"]
    write_json(auth_path, auth)

    # --- config.toml ---
    config_path = get_codex_config_toml_path()
    config = read_toml(config_path)

    if env_vars.get("model"):
        config["model"] = env_vars["model"]
    if env_vars.get("review_model"):
        config["review_model"] = env_vars["review_model"]

    provider_name = env_vars.get("model_provider") or config.get("model_provider", "")
    if provider_name:
        config["model_provider"] = provider_name
        if "model_providers" not in config:
            config["model_providers"] = {}
        if provider_name not in config["model_providers"]:
            config["model_providers"][provider_name] = {}
        provider = config["model_providers"][provider_name]
        provider["name"] = provider_name
        if env_vars.get("base_url"):
            provider["base_url"] = env_vars["base_url"]
        provider.setdefault("wire_api", "responses")
        provider.setdefault("requires_openai_auth", True)

    write_toml(config_path, config)


def normalize_codex_profile(profile):
    profile.setdefault("name", "未命名")
    profile.setdefault("group", "默认")
    profile.setdefault("env", {})
    for key in CODEX_ENV_KEYS:
        profile["env"].setdefault(key, "")
    return profile


def get_codex_profiles():
    data = read_json(get_codex_profiles_path())
    return [normalize_codex_profile(p) for p in data.get("profiles", [])]


def save_codex_profiles(profiles):
    write_json(get_codex_profiles_path(), {"profiles": profiles})


# ===================================================================
# Routes
# ===================================================================

@app.route("/")
def index():
    return render_template(
        "index.html",
        claude_env_keys=CLAUDE_ENV_KEYS,
        codex_env_keys=CODEX_ENV_KEYS,
    )


# -------------------------------------------------------------------
# App-level config (home dir switching)
# -------------------------------------------------------------------

@app.route("/api/config")
def api_config():
    data = read_json(APP_CONFIG_PATH)
    return jsonify({
        "claude_home_dir": data.get("claude_home_dir", DEFAULT_CLAUDE_HOME),
        "codex_home_dir": data.get("codex_home_dir", DEFAULT_CODEX_HOME),
        "claude_settings_path": get_claude_settings_path(),
        "claude_profiles_path": get_claude_profiles_path(),
        "codex_auth_path": get_codex_auth_path(),
        "codex_config_toml_path": get_codex_config_toml_path(),
        "codex_profiles_path": get_codex_profiles_path(),
    })


@app.route("/api/config", methods=["POST"])
def api_update_config():
    data = request.get_json(silent=True) or {}
    provider = data.get("provider", "claude")
    home_dir = (data.get("home_dir", "") or "").strip()
    if not home_dir:
        return jsonify({"error": "home_dir is required"}), 400
    home_dir = os.path.abspath(os.path.expanduser(home_dir))

    app_config = read_json(APP_CONFIG_PATH)
    if provider == "codex":
        app_config["codex_home_dir"] = home_dir
    else:
        app_config["claude_home_dir"] = home_dir
    write_json(APP_CONFIG_PATH, app_config)
    return api_config()


# -------------------------------------------------------------------
# Claude routes
# -------------------------------------------------------------------

@app.route("/api/claude/current")
def api_claude_current():
    return jsonify(get_claude_current_env())


@app.route("/api/claude/profiles")
def api_claude_profiles():
    return jsonify(get_claude_profiles())


@app.route("/api/claude/profiles", methods=["POST"])
def api_claude_create_profile():
    data = request.get_json(silent=True) or {}
    profiles = get_claude_profiles()
    profile = {
        "id": str(uuid.uuid4())[:8],
        "name": data.get("name", "未命名"),
        "group": data.get("group", "默认"),
        "created_at": datetime.now().isoformat(),
        "env": {k: data.get("env", {}).get(k, "") for k in CLAUDE_ENV_KEYS},
    }
    profiles.append(profile)
    save_claude_profiles(profiles)
    return jsonify(profile), 201


@app.route("/api/claude/profiles/<profile_id>", methods=["PUT"])
def api_claude_update_profile(profile_id):
    data = request.get_json(silent=True) or {}
    profiles = get_claude_profiles()
    for p in profiles:
        if p["id"] == profile_id:
            p["name"] = data.get("name", p["name"])
            p["group"] = data.get("group", p.get("group", "默认"))
            if "env" in data:
                for k in CLAUDE_ENV_KEYS:
                    if k in data["env"]:
                        p["env"][k] = data["env"][k]
            save_claude_profiles(profiles)
            return jsonify(p)
    return jsonify({"error": "not found"}), 404


@app.route("/api/claude/profiles/<profile_id>", methods=["DELETE"])
def api_claude_delete_profile(profile_id):
    profiles = get_claude_profiles()
    profiles = [p for p in profiles if p["id"] != profile_id]
    save_claude_profiles(profiles)
    return jsonify({"ok": True})


@app.route("/api/claude/apply/<profile_id>", methods=["POST"])
def api_claude_apply_profile(profile_id):
    profiles = get_claude_profiles()
    target = next((p for p in profiles if p["id"] == profile_id), None)
    if not target:
        return jsonify({"error": "not found"}), 404
    apply_claude_env(target["env"])
    return jsonify({"ok": True, "applied": target["name"]})


@app.route("/api/claude/apply", methods=["POST"])
def api_claude_apply_direct():
    data = request.get_json(silent=True) or {}
    env_vars = {k: data.get(k, "") for k in CLAUDE_ENV_KEYS if k in data}
    apply_claude_env(env_vars)
    return jsonify({"ok": True})


@app.route("/api/claude/export")
def api_claude_export():
    settings = read_json(get_claude_settings_path())
    export_data = {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "profiles": get_claude_profiles(),
        "settings_env": get_claude_current_env(),
        "settings": {k: v for k, v in settings.items() if k != "env"},
    }
    buf = io.BytesIO()
    buf.write(json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/json",
        as_attachment=True,
        download_name="claude_code_config_export.json",
    )


@app.route("/api/claude/import", methods=["POST"])
def api_claude_import():
    mode = request.args.get("mode", "merge")
    file = request.files.get("file")
    if file:
        raw = file.read().decode("utf-8")
    else:
        data = request.get_json(silent=True) or {}
        raw = json.dumps(data)

    try:
        import_data = json.loads(raw)
    except json.JSONDecodeError:
        return jsonify({"error": "无效的 JSON 文件"}), 400

    result = {"profiles_count": 0, "settings_updated": False}

    if mode == "replace":
        imported_profiles = import_data.get("profiles", [])
        save_claude_profiles(imported_profiles)
        result["profiles_count"] = len(imported_profiles)

        settings_env = import_data.get("settings_env", {})
        if settings_env:
            apply_claude_env(settings_env)
            result["settings_updated"] = True
    else:
        existing = get_claude_profiles()
        existing_keys = {(p.get("name", ""), p.get("group", "默认")) for p in existing}
        imported = import_data.get("profiles", [])
        merged = list(existing)
        added = 0
        for p in imported:
            key = (p.get("name", ""), p.get("group", "默认"))
            if key not in existing_keys:
                p["id"] = str(uuid.uuid4())[:8]
                p.setdefault("created_at", datetime.now().isoformat())
                merged.append(p)
                existing_keys.add(key)
                added += 1
        save_claude_profiles(merged)
        result["profiles_count"] = added

    return jsonify(result)


# -------------------------------------------------------------------
# Codex routes
# -------------------------------------------------------------------

@app.route("/api/codex/current")
def api_codex_current():
    return jsonify(get_codex_current_env())


@app.route("/api/codex/profiles")
def api_codex_profiles():
    return jsonify(get_codex_profiles())


@app.route("/api/codex/profiles", methods=["POST"])
def api_codex_create_profile():
    data = request.get_json(silent=True) or {}
    profiles = get_codex_profiles()
    profile = {
        "id": str(uuid.uuid4())[:8],
        "name": data.get("name", "未命名"),
        "group": data.get("group", "默认"),
        "created_at": datetime.now().isoformat(),
        "env": {k: data.get("env", {}).get(k, "") for k in CODEX_ENV_KEYS},
    }
    profiles.append(profile)
    save_codex_profiles(profiles)
    return jsonify(profile), 201


@app.route("/api/codex/profiles/<profile_id>", methods=["PUT"])
def api_codex_update_profile(profile_id):
    data = request.get_json(silent=True) or {}
    profiles = get_codex_profiles()
    for p in profiles:
        if p["id"] == profile_id:
            p["name"] = data.get("name", p["name"])
            p["group"] = data.get("group", p.get("group", "默认"))
            if "env" in data:
                for k in CODEX_ENV_KEYS:
                    if k in data["env"]:
                        p["env"][k] = data["env"][k]
            save_codex_profiles(profiles)
            return jsonify(p)
    return jsonify({"error": "not found"}), 404


@app.route("/api/codex/profiles/<profile_id>", methods=["DELETE"])
def api_codex_delete_profile(profile_id):
    profiles = get_codex_profiles()
    profiles = [p for p in profiles if p["id"] != profile_id]
    save_codex_profiles(profiles)
    return jsonify({"ok": True})


@app.route("/api/codex/apply/<profile_id>", methods=["POST"])
def api_codex_apply_profile(profile_id):
    profiles = get_codex_profiles()
    target = next((p for p in profiles if p["id"] == profile_id), None)
    if not target:
        return jsonify({"error": "not found"}), 404
    apply_codex_env(target["env"])
    return jsonify({"ok": True, "applied": target["name"]})


@app.route("/api/codex/apply", methods=["POST"])
def api_codex_apply_direct():
    data = request.get_json(silent=True) or {}
    env_vars = {k: data.get(k, "") for k in CODEX_ENV_KEYS if k in data}
    apply_codex_env(env_vars)
    return jsonify({"ok": True})


@app.route("/api/codex/export")
def api_codex_export():
    export_data = {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "profiles": get_codex_profiles(),
        "settings_env": get_codex_current_env(),
    }
    buf = io.BytesIO()
    buf.write(json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/json",
        as_attachment=True,
        download_name="codex_config_export.json",
    )


@app.route("/api/codex/import", methods=["POST"])
def api_codex_import():
    mode = request.args.get("mode", "merge")
    file = request.files.get("file")
    if file:
        raw = file.read().decode("utf-8")
    else:
        data = request.get_json(silent=True) or {}
        raw = json.dumps(data)

    try:
        import_data = json.loads(raw)
    except json.JSONDecodeError:
        return jsonify({"error": "无效的 JSON 文件"}), 400

    result = {"profiles_count": 0, "settings_updated": False}

    if mode == "replace":
        imported_profiles = import_data.get("profiles", [])
        save_codex_profiles(imported_profiles)
        result["profiles_count"] = len(imported_profiles)

        settings_env = import_data.get("settings_env", {})
        if settings_env:
            apply_codex_env(settings_env)
            result["settings_updated"] = True
    else:
        existing = get_codex_profiles()
        existing_keys = {(p.get("name", ""), p.get("group", "默认")) for p in existing}
        imported = import_data.get("profiles", [])
        merged = list(existing)
        added = 0
        for p in imported:
            key = (p.get("name", ""), p.get("group", "默认"))
            if key not in existing_keys:
                p["id"] = str(uuid.uuid4())[:8]
                p.setdefault("created_at", datetime.now().isoformat())
                merged.append(p)
                existing_keys.add(key)
                added += 1
        save_codex_profiles(merged)
        result["profiles_count"] = added

    return jsonify(result)


# ===================================================================

if __name__ == "__main__":
    app.run(host="192.168.111.4", port=5000, debug=True)
