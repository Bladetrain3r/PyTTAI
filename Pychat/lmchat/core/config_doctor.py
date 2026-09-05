import os


def diagnose(config_data, registry):
    findings = []
    providers = config_data.get("providers", {})
    has_providers = bool(providers)

    for name, cfg in providers.items():
        type_ = cfg.get("type", name)
        if type_ not in registry:
            findings.append({
                "provider": name,
                "type": type_,
                "level": "error",
                "code": "UNKNOWN_TYPE",
                "message": f"unknown provider type '{type_}'; known: {sorted(registry)}",
            })
            continue

        cls = registry[type_]
        requires = getattr(cls, "REQUIRES_KEY", False)
        env_vars = getattr(cls, "KEY_ENV_VARS", ())
        has_config_key = bool(cfg.get("api_key"))
        has_env_key = any(os.environ.get(v) for v in env_vars)

        produced_error = False
        produced_warn = False

        if requires and not (has_config_key or has_env_key):
            findings.append({
                "provider": name,
                "type": type_,
                "level": "error",
                "code": "MISSING_KEY",
                "message": f"requires an API key; set api_key or one of {list(env_vars)}",
            })
            produced_error = True

        if has_config_key:
            findings.append({
                "provider": name,
                "type": type_,
                "level": "warn",
                "code": "CLEARTEXT_KEY",
                "message": "api_key stored in cleartext config; prefer an env var or secret manager",
            })
            produced_warn = True

        if not produced_error and not produced_warn:
            findings.append({
                "provider": name,
                "type": type_,
                "level": "ok",
                "code": "OK",
                "message": "ok",
            })

    if not has_providers and "model" not in config_data:
        findings.append({
            "provider": "(top-level)",
            "type": "-",
            "level": "warn",
            "code": "NO_PROVIDERS",
            "message": "no providers configured and no top-level model",
        })

    return findings


def render(findings):
    if not findings:
        return "no findings"
    lines = []
    for f in findings:
        lines.append(f"[{f['level'].upper()}] {f['provider']} ({f['type']}): {f['code']} - {f['message']}")
    return "\n".join(lines)
