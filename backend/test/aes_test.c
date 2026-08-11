#include <stdio.h>
#include <string.h>
#include <openssl/evp.h>

int main(void)
{
    unsigned char key[32] = {
        0x60, 0x3d, 0xeb, 0x10, 0x15, 0xca, 0x71, 0xbe,
        0x2b, 0x73, 0xae, 0xf0, 0x85, 0x7d, 0x77, 0x81,
        0x1f, 0x35, 0x2c, 0x07, 0x3b, 0x61, 0x08, 0xd7,
        0x2d, 0x98, 0x10, 0xa3, 0x09, 0x14, 0xdf, 0xf4
    };

    unsigned char iv[16] = {
        0x00, 0x01, 0x02, 0x03,
        0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b,
        0x0c, 0x0d, 0x0e, 0x0f
    };

    unsigned char plaintext[] =
        "CryptoSage AES firmware security test";

    unsigned char ciphertext[128];
    int len = 0;
    int ciphertext_len = 0;

    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();

    if (!ctx)
        return 1;

    if (EVP_EncryptInit_ex(
            ctx,
            EVP_aes_256_cbc(),
            NULL,
            key,
            iv) != 1)
        return 1;

    if (EVP_EncryptUpdate(
            ctx,
            ciphertext,
            &len,
            plaintext,
            strlen((char *)plaintext)) != 1)
        return 1;

    ciphertext_len = len;

    if (EVP_EncryptFinal_ex(
            ctx,
            ciphertext + len,
            &len) != 1)
        return 1;

    ciphertext_len += len;

    printf("AES-256-CBC encryption successful\n");
    printf("Plaintext: %s\n", plaintext);
    printf("Ciphertext length: %d bytes\n", ciphertext_len);

    EVP_CIPHER_CTX_free(ctx);

    return 0;
}