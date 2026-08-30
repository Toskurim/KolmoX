#ifndef KOLMOX_H
#define KOLMOX_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* KolmoX Domain Identifiers */
typedef enum {
    KMX_DOMAIN_GENERIC = 0,
    KMX_DOMAIN_GCODE = 1,
    KMX_DOMAIN_FLOAT32 = 2,
    KMX_DOMAIN_AUDIO_PCM16 = 3,
    KMX_DOMAIN_POINTCLOUD = 4,
    KMX_DOMAIN_BINARY_X86 = 5
} kmx_domain_t;

/* Fast Transpose Float32 Byte-Planes (Invertible) */
void kmx_transpose_f32(const uint8_t* src, uint8_t* dst, size_t count);
void kmx_untranspose_f32(const uint8_t* src, uint8_t* dst, size_t count);

/* BCJ x86 Branch Filter (Invertible) */
void kmx_bcj_x86_forward(uint8_t* buffer, size_t size);
void kmx_bcj_x86_inverse(uint8_t* buffer, size_t size);

#ifdef __cplusplus
}
#endif

#endif /* KOLMOX_H */
