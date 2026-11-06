/* MIT. Place unchanged field functions in first code segment using stock
 * ELKS linker script. Preserve far calls in definitions and all callers. */
#include "f25519.h"
void f25519_load(uint8_t *x, uint32_t c) __attribute__((far_section, section(".text.edfield")));
void f25519_normalize(uint8_t *x) __attribute__((far_section, section(".text.edfield")));
uint8_t f25519_eq(const uint8_t *x, const uint8_t *y) __attribute__((far_section, section(".text.edfield")));
void f25519_select(uint8_t *dst,
		   const uint8_t *zero, const uint8_t *one,
		   uint8_t condition) __attribute__((far_section, section(".text.edfield")));
void f25519_add(uint8_t *r, const uint8_t *a, const uint8_t *b) __attribute__((far_section, section(".text.edfield")));
void f25519_sub(uint8_t *r, const uint8_t *a, const uint8_t *b) __attribute__((far_section, section(".text.edfield")));
void f25519_neg(uint8_t *r, const uint8_t *a) __attribute__((far_section, section(".text.edfield")));
void f25519_mul(uint8_t *r, const uint8_t *a, const uint8_t *b) __attribute__((far_section, section(".text.edfield")));
void f25519_mul__distinct(uint8_t *r, const uint8_t *a, const uint8_t *b) __attribute__((far_section, section(".text.edfield")));
void f25519_mul_c(uint8_t *r, const uint8_t *a, uint32_t b) __attribute__((far_section, section(".text.edfield")));
void f25519_inv(uint8_t *r, const uint8_t *x) __attribute__((far_section, section(".text.edfield")));
void f25519_inv__distinct(uint8_t *r, const uint8_t *x) __attribute__((far_section, section(".text.edfield")));
void f25519_sqrt(uint8_t *r, const uint8_t *x) __attribute__((far_section, section(".text.edfield")));
