# Claude Azure

Run Claude Code against your own Azure Foundry deployments through a local LiteLLM gateway. Each teammate installs it on their own computer. No shared server or hosting is required.

**Status:** Linux and Windows implementation with automated tests. Linux credential-service design and Azure model compatibility have been exercised on one Linux installation. The portable package's mock integration tests do not replace installation tests on your hardware. Windows DPAPI, Task Scheduler, and Docker Desktop still require a real Windows acceptance test before team rollout.

## What you need

- Claude Code already installed and used at least once.
- Your Azure resource endpoint, exact deployment names, and API key.
- Linux: systemd 250+, Python 3.10+, Docker Engine, sudo, and permission to use Docker.
- Windows: x64 Windows supported by Docker Desktop, Windows PowerShell 5.1+, Docker Desktop initialized in Linux-container mode, and Task Scheduler. No host Python installation is needed.
- Internet access to the pinned image registry and your Azure endpoint.

The installer checks prerequisites. It does not install Docker, change Docker group membership, enable virtualization, or change machine-wide PowerShell execution policy.

## Install

Clone the repository, review the scripts, then run from its directory.

```bash
git clone https://github.com/haritp/claude-azure.git
cd claude-azure
```

Linux:

```bash
./setup.sh
```

Windows, in PowerShell:

```powershell
.\Setup.ps1
```

If locally reviewed scripts are blocked by execution policy, follow your organization's policy. A process-scoped option is `powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\Setup.ps1`. Files downloaded from the internet may need to be unblocked after review; enterprise policy can override process settings.

Setup asks for endpoint, deployment names, local port (default `48763`), and a hidden API key. Both a resource URL and a single `/openai/v1/responses` or `/chat/completions` URL are normalized to the base `/openai/v1/` URL. Duplicated URLs are rejected.

On Linux ensure `~/.local/bin` is on PATH. On Windows open a new terminal after installation.

## Credential protection

Linux automatically selects `systemd-creds` host+TPM2 encryption when TPM2 is available. Without TPM2 it explains and selects host-key encryption. You can explicitly require a mode:

```bash
./setup.sh --storage host+tpm2
./setup.sh --storage host
```

An explicitly required TPM mode never silently downgrades. If a TPM is detected but sealing fails, setup stops; choose host mode explicitly only if you accept its weaker protection. Host-only encryption does not protect against an attacker who obtains both the encrypted credential and the systemd host key from disk. TPM policy or Secure Boot changes can require re-enrollment. Linux without systemd is not supported; there is no automatic plaintext fallback.

Windows uses DPAPI **CurrentUser**, with a restricted profile ACL. It does not require a TPM. Only that Windows account can normally decrypt the blob; the startup task therefore runs as the same signed-in user. Do not copy a blob to another account/device and expect it to decrypt; rerun setup there.

No API key is committed, passed in process arguments, placed in Docker environment variables, or written to a host plaintext file. Linux systemd decrypts its credential at service startup; Windows decrypts inside the task process. The secret-bearing configuration is passed to Docker on stdin and written only to the container's temporary filesystem. Secrets necessarily exist in process memory; an administrator, Docker administrator, or compromised running gateway can access them. Swap/hibernation and full-disk protection remain OS concerns.

The gateway token is a different local credential, stored in a permission-restricted file so the launcher can authenticate. Treat it as sensitive too. Rotate Azure credentials by rerunning setup; it re-encrypts the new key and restarts the gateway.

## Usage and existing chats

```text
claude-azure
claude-azure --resume
claude-azure --continue
claude-azure --luna --resume
```

The Azure profile has separate settings and links its project chat directory to your normal Claude Code directory. Linux also links input history; Windows uses a directory junction for project chats and keeps input history separate. Conversation data is not uploaded or migrated by setup. When you resume a conversation through Azure, its messages are sent to your Azure deployment.

Normal `claude` settings and subscription login are not replaced. A shared conversation can retain an Azure model identifier in its transcript. To return that conversation to a subscription Claude model, explicitly select one:

```text
claude --model sonnet --resume
```

Sol defaults to low reasoning and uses Responses for function/tool calls. Luna is pinned to reasoning `none` so its tools can use Chat Completions. The compatibility hook prevents Claude's thinking controls from silently enabling Luna reasoning; Luna's thinking/effort UI is therefore intentionally ignored. Sol's unsupported disabled/minimal settings are normalized to low; supported higher settings can be passed through.

This behavior targets the documented GPT-6.1 Sol and GPT-6 Luna capabilities. Other deployment types need their own compatibility tests. Display labels are `Azure Sol` and `Azure Luna`.

**Non-Claude models in Claude Code are not supported by Anthropic.** LiteLLM supplies the translation. Claude Code updates can change chat discovery, storage, model selection, and tool behavior; test the version your team uses.

## Startup and management

Linux starts at boot, even before login, using `claude-azure-local.service` and Docker Engine. The key is decrypted again on each service start.

```bash
sudo systemctl status claude-azure-local
sudo systemctl restart claude-azure-local
```

Windows starts at sign-in under your account, using a `ClaudeAzureLocal-<user SID>` scheduled task. The task starts Docker Desktop if it finds a standard installation and waits for the engine. It retries on process failure. It cannot provide a pre-login system service with user-scoped DPAPI and Docker Desktop.

The container listens on localhost only, runs as a non-root user with a read-only root filesystem, drops capabilities, and has resource limits. No host home directory or Docker socket is mounted. Request/body logs and Docker log storage are disabled. Use service/task status and the verification scripts for diagnostics.

An existing `claude-azure` installation or occupied port is not overwritten automatically. For this repository's first installation, uninstall the old launcher/service deliberately or choose a free port after resolving the command-name conflict. Your existing personal installation is not changed merely by downloading this repository.

## Verify

Linux (substitute your configured port and profile location if needed):

```bash
python3 src/verify.py --port 48763 --token-file "$HOME/.config/claude-azure-local/gateway-token"
```

Windows setup runs `Verify.ps1`; rerun it from `%LOCALAPPDATA%\ClaudeAzureLocal` as needed. Live verification sends small, billable test requests to both Azure deployments. It checks discovery, streaming, forced tool calling, and tool-result continuation without printing model content or raw provider errors.

## Uninstall

```bash
./linux/uninstall.sh
./linux/uninstall.sh --purge
```

Windows:

```powershell
& "$env:LOCALAPPDATA\ClaudeAzureLocal\Uninstall.ps1"
& "$env:LOCALAPPDATA\ClaudeAzureLocal\Uninstall.ps1" -Purge
```

Without purge, encrypted credentials and private profile files remain. Purge removes this package's encrypted key and profile, not the original shared chat directory. Do not manually recursively delete a Windows junction target. Uninstall leaves the downloaded repository/image cache alone.

## Security and dependency updates

`image-lock.json` pins LiteLLM **1.106.2** to architecture-specific digests. This is the baseline recommended in LiteLLM's October 21 incident notice; it is not a promise that the release has no other vulnerabilities. The amd64 build provenance was inspected for the official source repository and recorded revision. A matching version/tag or signature alone does not prove safety after a release-pipeline compromise.

Before rollout or an image update, review the current vendor security notices, provenance and dependency findings. Never replace the lock with `latest`, `main-stable`, or an unpinned `pip install`. There are no automatic dependency updates. The arm64 digest is pinned, but arm64 runtime acceptance has not been performed here.

See [SECURITY.md](SECURITY.md) for the threat model and reporting guidance. This repository contains only original wrapper code; LiteLLM and Docker remain separately licensed dependencies.

## Development

```bash
python3 -m unittest discover -s tests -v
./tests/integration.sh
```

The integration test uses fake credentials and a local mock upstream in a network-disabled container. It asserts Sol uses `/responses`, Luna uses `/chat/completions`, and both stream tool calls and continue after tool results. Windows CI parses scripts, checks shared configuration behavior, and performs a DPAPI round trip using a dummy secret. It does not exercise interactive installation or real Azure credentials.

## References

- [LiteLLM incident notice](https://docs.litellm.ai/blog/security-incident-oct-21-2026)
- [systemd credentials](https://www.freedesktop.org/software/systemd/man/255/systemd-creds.html)
- [Windows DPAPI scopes](https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.dataprotectionscope)
- [Claude Code gateway support and subscriptions](https://code.claude.com/docs/en/llm-gateway)
- [Azure model capabilities](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models)
