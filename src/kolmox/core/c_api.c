#include "kolmox.h"
#include <string.h>

void kmx_transpose_f32(const uint8_t* src, uint8_t* dst, size_t count) {
    uint8_t* p0 = dst;
    uint8_t* p1 = dst + count;
    uint8_t* p2 = dst + (2 * count);
    uint8_t* p3 = dst + (3 * count);

    for (size_t i = 0; i < count; ++i) {
        p0[i] = src[4 * i];
        p1[i] = src[4 * i + 1];
        p2[i] = src[4 * i + 2];
        p3[i] = src[4 * i + 3];
    }
}

void kmx_untranspose_f32(const uint8_t* src, uint8_t* dst, size_t count) {
    const uint8_t* p0 = src;
    const uint8_t* p1 = src + count;
    const uint8_t* p2 = src + (2 * count);
    const uint8_t* p3 = src + (3 * count);

    for (size_t i = 0; i < count; ++i) {
        dst[4 * i]     = p0[i];
        dst[4 * i + 1] = p1[i];
        dst[4 * i + 2] = p2[i];
        dst[4 * i + 3] = p3[i];
    }
}

void kmx_bcj_x86_forward(uint8_t* buffer, size_t size) {
    size_t i = 0;
    while (i + 4 < size) {
        uint8_t b = buffer[i];
        if (b == 0xE8 || b == 0xE9) {
            int32_t rel;
            memcpy(&rel, &buffer[i + 1], 4);
            uint32_t abs_addr = (uint32_t)(rel + (int32_t)(i + 5));
            memcpy(&buffer[i + 1], &abs_addr, 4);
            i += 5;
        } else {
            i += 1;
        }
    }
}

void kmx_bcj_x86_inverse(uint8_t* buffer, size_t size) {
    size_t i = 0;
    while (i + 4 < size) {
        uint8_t b = buffer[i];
        if (b == 0xE8 || b == 0xE9) {
            uint32_t abs_addr;
            memcpy(&abs_addr, &buffer[i + 1], 4);
            int32_t rel = (int32_t)abs_addr - (int32_t)(i + 5);
            memcpy(&buffer[i + 1], &rel, 4);
            i += 5;
        } else {
            i += 1;
        }
    }
}
