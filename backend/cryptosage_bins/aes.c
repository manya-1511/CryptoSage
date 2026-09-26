#include <stdint.h>

static const uint8_t AES_SBOX[16] = {
    0x63, 0x7c, 0x77, 0x7b,
    0xf2, 0x6b, 0x6f, 0xc5,
    0x30, 0x01, 0x67, 0x2b,
    0xfe, 0xd7, 0xab, 0x76
};

__attribute__((noinline))
void aes_encrypt_test(const uint8_t *in, uint8_t *out)
{
    for (int i = 0; i < 16; i++) {
        out[i] = AES_SBOX[in[i] & 0x0f] ^ 0x63;
    }
}

int main(void)
{
    uint8_t in[16] = {0};
    uint8_t out[16] = {0};

    aes_encrypt_test(in, out);

    return out[0];
}
