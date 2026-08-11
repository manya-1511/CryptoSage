---
title: MITRE ATT&CK T1600 — Weaken Encryption
source_type: MITRE
identifier: ATT&CK T1600
---

# ATT&CK T1600: Weaken Encryption

MITRE ATT&CK technique T1600 describes adversary behavior aimed at
reducing the effectiveness of encryption protecting a system or its
communications -- for example, by downgrading a negotiated cipher
suite to a weaker algorithm (T1600.001, "Reduce Key Space") or
disabling encryption features entirely. This technique is directly
relevant to firmware/device analysis: a device that still supports or
defaults to deprecated algorithms (DES, RC4, export-grade ciphers)
presents a larger attack surface for downgrade-style attacks even if a
stronger algorithm is also supported, because an adversary positioned
on the network path may be able to force negotiation of the weaker
option.

Firmware and protocol implementations are recommended to remove
support for deprecated algorithms entirely, rather than merely
de-prioritizing them, to eliminate downgrade attack feasibility.
