#include "metadata.h"
#include <string.h>

static uint8_t bits_for_palette(uint8_t p_count) {
    uint16_t total = (uint16_t)p_count + 1u; /* include 0 = free */
    uint8_t b = 1;
    while ((1u << b) < total) b++;
    return b;
}

typedef struct {
    uint8_t *buf;
    size_t   max_bytes;
    size_t   bit_pos;
    bool     overflow;
} bit_writer_t;

static void bw_put(bit_writer_t *bw, uint32_t val, uint8_t nbits) {
    for (uint8_t b = 0; b < nbits; b++) {
        size_t byte_idx = bw->bit_pos >> 3;
        uint8_t bit_idx = (uint8_t)(bw->bit_pos & 7u);
        if (byte_idx >= bw->max_bytes) {
            bw->overflow = true;
            return;
        }
        if ((val >> b) & 1u) {
            bw->buf[byte_idx] |= (uint8_t)(1u << bit_idx);
        }
        bw->bit_pos++;
    }
}

typedef struct {
    const uint8_t *buf;
    size_t         max_bytes;
    size_t         bit_pos;
    bool           overflow;
} bit_reader_t;

static uint32_t br_get(bit_reader_t *br, uint8_t nbits) {
    uint32_t val = 0;
    for (uint8_t b = 0; b < nbits; b++) {
        size_t byte_idx = br->bit_pos >> 3;
        uint8_t bit_idx = (uint8_t)(br->bit_pos & 7u);
        if (byte_idx >= br->max_bytes) {
            br->overflow = true;
            return 0;
        }
        if ((br->buf[byte_idx] >> bit_idx) & 1u) {
            val |= (1u << b);
        }
        br->bit_pos++;
    }
    return val;
}

bool md_encode(const uint16_t owners[FM_PAYLOAD_BLOCKS],
               uint8_t *out_buf,
               size_t max_out_len,
               size_t *out_len) {
    if (!owners || !out_buf || !out_len || max_out_len < 4) return false;

    uint16_t palette[64];
    uint8_t p_count = 0;

    for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS; i++) {
        uint16_t m = owners[i];
        if (m == 0) continue;
        bool found = false;
        for (uint8_t p = 0; p < p_count; p++) {
            if (palette[p] == m) { found = true; break; }
        }
        if (!found) {
            if (p_count >= 63) return false;
            palette[p_count++] = m;
        }
    }

    size_t hdr_bytes = 2u + (size_t)p_count * 2u;
    if (hdr_bytes >= max_out_len) return false;

    memset(out_buf, 0, max_out_len);
    out_buf[0] = 0xB2u;
    out_buf[1] = p_count;
    for (uint8_t p = 0; p < p_count; p++) {
        out_buf[2u + p * 2u]     = (uint8_t)(palette[p] & 0xFFu);
        out_buf[2u + p * 2u + 1] = (uint8_t)((palette[p] >> 8) & 0xFFu);
    }

    uint8_t idx_bits = bits_for_palette(p_count);
    bit_writer_t bw = { out_buf, max_out_len, hdr_bytes * 8u, false };

    uint16_t i = 0;
    while (i < FM_PAYLOAD_BLOCKS) {
        uint16_t m = owners[i];
        uint16_t run_len = 0;
        while (i < FM_PAYLOAD_BLOCKS && owners[i] == m) {
            i++;
            run_len++;
        }
        uint8_t pidx = 0;
        if (m != 0) {
            for (uint8_t p = 0; p < p_count; p++) {
                if (palette[p] == m) { pidx = (uint8_t)(p + 1u); break; }
            }
        }
        bw_put(&bw, pidx, idx_bits);
        if (run_len <= 16u) {
            bw_put(&bw, 0u, 1);
            bw_put(&bw, (uint32_t)(run_len - 1u), 4);
        } else {
            bw_put(&bw, 1u, 1);
            bw_put(&bw, (uint32_t)(run_len - 1u), 10);
        }
        if (bw.overflow) return false;
    }

    *out_len = (bw.bit_pos + 7u) >> 3;
    return true;
}

bool md_decode(const uint8_t *in_buf,
               size_t in_len,
               uint16_t out_owners[FM_PAYLOAD_BLOCKS]) {
    if (!in_buf || !out_owners || in_len < 2) return false;
    if (in_buf[0] != 0xB2u) return false;

    uint8_t p_count = in_buf[1];
    if (p_count > 63) return false;
    size_t hdr_bytes = 2u + (size_t)p_count * 2u;
    if (in_len < hdr_bytes) return false;

    uint16_t palette[64];
    palette[0] = 0;
    for (uint8_t p = 0; p < p_count; p++) {
        palette[p + 1u] = (uint16_t)in_buf[2u + p * 2u] |
                          ((uint16_t)in_buf[2u + p * 2u + 1u] << 8);
    }

    uint8_t idx_bits = bits_for_palette(p_count);
    bit_reader_t br = { in_buf, in_len, hdr_bytes * 8u, false };

    uint16_t pos = 0;
    while (pos < FM_PAYLOAD_BLOCKS) {
        uint32_t pidx = br_get(&br, idx_bits);
        uint32_t is_long = br_get(&br, 1);
        uint32_t run_len = is_long ? (br_get(&br, 10) + 1u) : (br_get(&br, 4) + 1u);
        if (br.overflow || pidx > p_count || pos + run_len > FM_PAYLOAD_BLOCKS) {
            return false;
        }
        uint16_t mask = palette[pidx];
        for (uint32_t k = 0; k < run_len; k++) {
            out_owners[pos++] = mask;
        }
    }
    return true;
}