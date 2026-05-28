#!/usr/bin/env python3

import json
import os
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

DEFAULT_HOME_DIR = os.path.expanduser("~/.claude")
APP_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "webui_config.json")

ENV_KEYS = [
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_REASONING_MODEL",
]


def read_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_home_dir():
    data = read_json(APP_CONFIG_PATH)
    return os.path.abspath(os.path.expanduser(data.get("home_dir", DEFAULT_HOME_DIR)))


def get_settings_path():
    return os.path.join(get_home_dir(), "settings.json")


def get_profiles_path():
    return os.path.join(get_home_dir(), "profiles.json")


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_current_env():
    settings = read_json(get_settings_path())
    env = settings.get("env", {})
    return {k: env.get(k, "") for k in ENV_KEYS}


def apply_env(env_vars):
    settings = read_json(get_settings_path())
    if "env" not in settings:
        settings["env"] = {}
    for k, v in env_vars.items():
        if k in ENV_KEYS:
            settings["env"][k] = v
    write_json(get_settings_path(), settings)


def normalize_profile(profile):
    profile.setdefault("name", "未命名")
    profile.setdefault("group", "默认")
    profile.setdefault("env", {})
    for key in ENV_KEYS:
        profile["env"].setdefault(key, "")
    return profile


def get_profiles():
    data = read_json(get_profiles_path())
    return [normalize_profile(p) for p in data.get("profiles", [])]


def save_profiles(profiles):
    write_json(get_profiles_path(), {"profiles": profiles})


@app.route("/")
def index():
    return render_template("index.html", env_keys=ENV_KEYS)


@app.route("/api/config")
def api_config():
    home_dir = get_home_dir()
    return jsonify({
        "home_dir": home_dir,
        "settings_path": get_settings_path(),
        "profiles_path": get_profiles_path(),
    })


@app.route("/api/config", methods=["POST"])
def api_update_config():
    data = request.get_json(silent=True) or {}
    home_dir = data.get("home_dir", "").strip()
    if not home_dir:
        return jsonify({"error": "home_dir is required"}), 400
    home_dir = os.path.abspath(os.path.expanduser(home_dir))
    write_json(APP_CONFIG_PATH, {"home_dir": home_dir})
    return api_config()


@app.route("/api/current")
def api_current():
    return jsonify(get_current_env())


@app.route("/api/profiles")
def api_profiles():
    return jsonify(get_profiles())


@app.route("/api/profiles", methods=["POST"])
def api_create_profile():
    data = request.get_json(silent=True) or {}
    profiles = get_profiles()
    profile = {
        "id": str(uuid.uuid4())[:8],
        "name": data.get("name", "未命名"),
        "group": data.get("group", "默认"),
        "created_at": datetime.now().isoformat(),
        "env": {k: data.get("env", {}).get(k, "") for k in ENV_KEYS},
    }
    profiles.append(profile)
    save_profiles(profiles)
    return jsonify(profile), 201


@app.route("/api/profiles/<profile_id>", methods=["PUT"])
def api_update_profile(profile_id):
    data = request.get_json(silent=True) or {}
    profiles = get_profiles()
    for p in profiles:
        if p["id"] == profile_id:
            p["name"] = data.get("name", p["name"])
            p["group"] = data.get("group", p.get("group", "默认"))
            if "env" in data:
                for k in ENV_KEYS:
                    if k in data["env"]:
                        p["env"][k] = data["env"][k]
            save_profiles(profiles)
            return jsonify(p)
    return jsonify({"error": "not found"}), 404


@app.route("/api/profiles/<profile_id>", methods=["DELETE"])
def api_delete_profile(profile_id):
    profiles = get_profiles()
    profiles = [p for p in profiles if p["id"] != profile_id]
    save_profiles(profiles)
    return jsonify({"ok": True})


@app.route("/api/apply/<profile_id>", methods=["POST"])
def api_apply_profile(profile_id):
    profiles = get_profiles()
    target = next((p for p in profiles if p["id"] == profile_id), None)
    if not target:
        return jsonify({"error": "not found"}), 404
    apply_env(target["env"])
    return jsonify({"ok": True, "applied": target["name"]})


@app.route("/api/apply", methods=["POST"])
def api_apply_direct():
    data = request.get_json(silent=True) or {}
    env_vars = {k: data.get(k, "") for k in ENV_KEYS if k in data}
    apply_env(env_vars)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
