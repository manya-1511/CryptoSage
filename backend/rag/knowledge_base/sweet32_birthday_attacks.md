---
title: Sweet32 -- Birthday Attacks on 64-bit Block Ciphers
source_type: Academic Paper
identifier: Bhargavan & Leurent, ACM CCS 2016
---

# Sweet32: Birthday Attacks on 64-bit Block Ciphers in TLS and OpenVPN

Bhargavan and Leurent's 2016 paper "On the Practical (In-)Security of
64-bit Block Ciphers" (popularly known as "Sweet32") demonstrated a
practical collision-based plaintext-recovery attack against 64-bit
block ciphers -- specifically 3DES and Blowfish -- when used in CBC
mode to encrypt large volumes of data under a single key, as commonly
occurs in long-lived TLS or VPN sessions. The attack exploits the
birthday bound: with a 64-bit block size, a collision becomes likely
after roughly 2^32 blocks (about 32 GB) of ciphertext, at which point
an attacker can recover plaintext through comparison of colliding
blocks, without breaking the underlying cipher itself.

This result is a key reason 64-bit-block ciphers (3DES, Blowfish, and
similar legacy designs) are now discouraged for encrypting large data
volumes, independent of their nominal key length, and is frequently
cited alongside NIST SP 800-131A's 3DES deprecation guidance.
