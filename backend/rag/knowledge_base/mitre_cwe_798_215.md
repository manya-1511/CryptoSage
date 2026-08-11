---
title: MITRE CWE-798 and CWE-215 — Hardcoded Credentials and Information Exposure Through Debug Information
source_type: MITRE
identifier: CWE-798, CWE-215
---

# CWE-798: Use of Hard-coded Credentials

CWE-798 covers software that contains embedded, fixed credentials or
cryptographic keys directly in its binary or source code. Hardcoded
keys cannot be rotated without a software update, are extractable by
any party with access to the binary (via static analysis, string
extraction, or disassembly), and, if reused across multiple deployed
devices, mean that a single extracted key compromises every device
sharing it. Recommended mitigation is to provision keys at
manufacturing/deployment time into a hardware security module (HSM),
Trusted Platform Module (TPM), or secure element, or to derive
device-specific keys rather than embedding a shared constant.

# CWE-215: Information Exposure Through Debug Information

CWE-215 covers software shipped with debug information (symbols,
verbose logging, debug-only code paths) still present in the
production build. Debug symbols meaningfully assist reverse engineering
by preserving function/variable names and structure that would
otherwise be stripped, and debug builds often disable compiler
hardening features (stack protection, optimizations that also serve as
a mild obfuscation barrier) by default. Standard mitigation is to strip
debug symbols and build with a release configuration before shipping.
