# Claude Azure

Use your Azure Foundry models in Claude Code, with a local gateway and access to your existing chats. Each teammate runs it on their own computer—no shared server needed.

- Linux and Windows setup scripts
- Encrypted API-key storage selected for your device
- Automatic gateway startup
- Separate Azure settings, shared Claude chat history

Linux has been exercised locally. Windows has automated script checks and still needs a full installation test on a Windows device.

## Quick start

```bash
git clone https://github.com/haritp/claude-azure.git
cd claude-azure
```

**Linux**

```bash
./setup.sh
```

**Windows PowerShell**

```powershell
.\Setup.ps1
```

The installer asks for your Azure endpoint, deployment names, and API key. Key entry is hidden. The default local port is `48763`.

After setup, open a new terminal and run:

```text
claude-azure
```

## Prerequisites

Install and launch Claude Code once before setup, and have your Azure resource details ready.

- **Linux:** systemd 250+, Python 3.10+, Docker Engine, sudo, and Docker access.
- **Windows:** x64 Windows, PowerShell 5.1+, Docker Desktop initialized in Linux-container mode, and Task Scheduler. Host Python isn't required.

On Linux, make sure `~/.local/bin` is on PATH. If Windows blocks downloaded scripts, review and unblock them according to your organization's PowerShell policy.

## Pick up an existing chat

```text
claude-azure --resume
claude-azure --continue
claude-azure --luna --resume
claude-azure --astra --resume
claude-azure --grok --resume
```

Sol is the default. Use `--luna`, `--astra`, or `--grok` to select another model.

The launcher uses its own settings and links to your existing project chats. Normal `claude` keeps its subscription login and settings. To resume an Azure-used conversation with a subscription Claude model, select the model explicitly:

```text
claude --model sonnet --resume
```

When you continue a chat through Azure, that conversation's messages are sent to your Azure deployment.

## Models

The default deployment names are `gpt-6.1-sol`, `gpt-6-luna`, `gpt-6-astra`, and `grok-4.6`; you can enter your team's deployment names during setup. All four use the same Azure endpoint and API key.

- **Sol and Astra:** tool calls use the Responses API, with low reasoning by default.
- **Luna:** uses Chat Completions with reasoning disabled for tool compatibility. Its thinking/effort controls are ignored.
- **Grok:** uses Chat Completions.

The three GPT models have `[1m]` gateway aliases and a 900,000-token Claude Code compaction setting. The model picker shows the deployment names. Azure may enforce separate image-count limits before the token window fills; compact or start a new chat if a request exceeds those limits.

LiteLLM handles API translation. Using non-Claude models this way is an unofficial Claude Code integration.

## API-key storage

Setup automatically chooses:

- **Linux with TPM2:** systemd host+TPM2 encryption.
- **Linux without TPM2:** systemd host-key encryption.
- **Windows:** DPAPI encryption tied to your Windows account.

Host-key encryption offers less protection against a full-disk read than TPM-backed encryption. An explicitly requested TPM mode won't silently fall back. Linux without systemd isn't supported.

To choose a Linux mode yourself:

```bash
./setup.sh --storage host+tpm2
./setup.sh --storage host
```

Rerun setup to replace your API key. Credentials stay local and aren't added to the repository. See [SECURITY.md](SECURITY.md) for details.

## Startup

Linux runs the gateway at boot through systemd:

```bash
sudo systemctl status claude-azure-local
sudo systemctl restart claude-azure-local
```

Windows uses a scheduled task at sign-in under your account. It starts Docker Desktop from a standard installation location and waits for the engine.

The gateway listens only on localhost. If the default port or `claude-azure` command is already in use, setup stops so you can resolve the conflict.

## Verify

Linux:

```bash
python3 src/verify.py --port 48763 --token-file "$HOME/.config/claude-azure-local/gateway-token"
```

Windows:

```powershell
& "$env:LOCALAPPDATA\ClaudeAzureLocal\Verify.ps1"
```

Verification checks model discovery, streaming, tool calls, and continuation after tool results. It sends small requests billed to your Azure account.

## Uninstall

Linux:

```bash
./linux/uninstall.sh
./linux/uninstall.sh --purge
```

Windows:

```powershell
& "$env:LOCALAPPDATA\ClaudeAzureLocal\Uninstall.ps1"
& "$env:LOCALAPPDATA\ClaudeAzureLocal\Uninstall.ps1" -Purge
```

Use purge to also remove this package's stored credentials and private settings. Your original Claude chat directory is kept.

## Development

```bash
python3 -m unittest discover -s tests -v
./tests/integration.sh
```

The integration test runs offline with fake credentials. CI also checks the Windows scripts and DPAPI behavior with a dummy secret; a full Windows installation test is still needed.

`image-lock.json` pins the LiteLLM image for reproducible installs. LiteLLM and Docker are separately licensed dependencies. This project's wrapper code uses the [MIT license](LICENSE).
