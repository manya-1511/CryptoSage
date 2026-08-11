---
title: NIST FIPS 197 — Advanced Encryption Standard (AES)
source_type: NIST
identifier: FIPS 197
---

# Advanced Encryption Standard (AES)

FIPS 197 specifies the Advanced Encryption Standard (AES), a symmetric
block cipher operating on 128-bit blocks with key sizes of 128, 192,
or 256 bits (AES-128, AES-192, AES-256). AES was selected by NIST in
2001 through a public competition to replace the aging Data Encryption
Standard (DES), and it remains the U.S. federal government's approved
symmetric encryption algorithm for protecting sensitive information.

AES is built on the Rijndael cipher design and uses a substitution-
permutation network with a fixed S-box for the SubBytes step, along
with ShiftRows, MixColumns, and AddRoundKey operations across 10, 12,
or 14 rounds depending on key length. No practical cryptanalytic attack
against full-round AES is publicly known; its security margin is
considered strong when used with an appropriate mode of operation
(e.g. GCM or CTR rather than unauthenticated ECB) and correct key
management.

AES-256 in particular provides a post-quantum symmetric security
margin considered adequate under current NIST guidance (see NIST SP
800-57) and is commonly recommended for long-term data protection.
