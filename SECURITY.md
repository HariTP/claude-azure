# Security

Do not report secrets, Azure keys, gateway tokens, decrypted configuration, conversation contents, or unredacted provider responses in public issues. Use [GitHub private vulnerability reporting](https://github.com/haritp/claude-azure/security/advisories/new) for sensitive security reports. Do not post vulnerability details in a public issue before the maintainer has reviewed them.

The wrappers reduce accidental credential exposure. They do not protect against a compromised user session, root/Administrator, Docker administrators, malware inside the running gateway, or a compromised host. Localhost binding does not make other programs on the same host trustworthy; the gateway still requires its token.

Linux host-only encryption is weaker than host+TPM protection. Windows DPAPI CurrentUser is bound to the user's Windows credential context and is not an independent barrier against that user's processes. Runtime plaintext is unavoidable for inference and can be exposed by memory inspection, swap or hibernation.

The container is restricted and receives only its own source code and secret-bearing stdin; it is not given project files, the user's home directory, a host socket, or cloud administration credentials. Prompt data and source snippets provided by Claude Code still go to the configured Azure endpoint.

Review vendor advisories before deployment. The pinned release was chosen as an incident-recommended baseline, not certified vulnerability-free. Never enable verbose/body logging while debugging real credentials. Use dummy data and the mock integration test first.
