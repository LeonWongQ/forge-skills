# Bailian Workflow Configuration Tools

Resolve the local tool directory in this order and report the selected path before use:

1. `BAILIAN_WORKFLOW_TOOLS_DIR` environment variable.
2. `.bailian/workflow-config-tools` under the current project.

Stop and ask the user for a local directory when none exists. Do not derive a directory from another project's Forge or skill link.

The tool supports Bailian import artifacts and uses the platform-compatible AES-256-ECB with PKCS#7 codec. Provide import credentials through an environment variable, never as an argument.

Before running any command below, ask: `请确认导入密钥来源：环境变量名、受保护的本地密钥文件路径，或允许本地掩码输入。请勿在聊天中粘贴密钥。` The default is a session environment-variable name supplied by the user. Without that confirmation, do not inspect, decrypt, extract, plan, build, or encrypt an artifact.

```powershell
Set-Location $env:BAILIAN_WORKFLOW_TOOLS_DIR
python workflow_config.py inspect --input <source.enc> --key-env <ENV_NAME> --format json
python workflow_config.py extract --input <source.enc> --workspace <new-private-workspace> --key-env <ENV_NAME>
python workflow_config.py validate --workspace <new-private-workspace>
python workflow_config.py plan --workspace <new-private-workspace> --input <source.enc> --key-env <ENV_NAME>
python workflow_config.py build --workspace <new-private-workspace> --input <source.enc> --output <new-output.enc> --key-env <ENV_NAME>
python workflow_config.py inspect --input <new-output.enc> --key-env <ENV_NAME>
```

`validate` must reject SCRIPT constructs that Bailian's import compiler or sandbox does not support even when CPython accepts them: multiple top-level functions, `*args`/`**kwargs`, starred call or collection unpacking, dictionary `**` unpacking, and unavailable reflection calls such as `getattr()`. SCRIPT code must read declared inputs directly, for example `params.message`. Stop before `plan` or `build` when any `script.bailian_*` diagnostic is present.

Select a workflow version during extraction when the artifact contains more than one version:

```powershell
python workflow_config.py extract --input <source.enc> --workspace <new-private-workspace> --key-env <ENV_NAME> --version-code <CODE>
```

For an extracted SCRIPT asset, use a project-owned fixture only:

```powershell
python workflow_config.py script-test --workspace <new-private-workspace> --asset <asset-id> --fixture <fixture.json>
```

`script-test` verifies local behavior only. It does not replace the platform-compatibility checks performed by `validate`.

The tool refuses to overwrite outputs. Its `build` command performs validation plus encrypt/decrypt structural verification. Do not use `decrypt` unless an explicit plaintext JSON artifact is necessary; if it is, write it to a new private path and do not commit it.
