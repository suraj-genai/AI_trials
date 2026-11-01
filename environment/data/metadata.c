#include "metadata.h"
#include <string.h>

/*
 * PROTOCOL 1 (Verbose Segment Table):
 * - Header (2 bytes): [0] = 0xA1 magic, [1] = segment_count (uint8_t, up to 250)
 * - Body (4 bytes per non-zero contiguous run, max run length 64 per entry):
 *   - uint16_t packed_geom = (start_idx & 0x3FF) | (((run_len - 1) & 0x3F) << 10)
 *   - uint16_t group_mask
 */
bool md_encode(const uint16_t owners[FM_PAYLOAD_BLOCKS],
               uint8_t *out_buf,
               size_t max_out_len,
               size_t *out_len) {
    if (!owners || !out_buf || !out_len || max_out_len < 2) return false;

    size_t pos = 2;
    uint16_t seg_count = 0;
    uint16_t i = 0;

    while (i < FM_PAYLOAD_BLOCKS) {
        if (owners[i] == 0) {
            i++;
            continue;
        }
        uint16_t mask = owners[i];
        uint16_t start = i;
        uint16_t run_len = 0;
        while (i < FM_PAYLOAD_BLOCKS && owners[i] == mask && run_len < 64) {
            i++;
            run_len++;
        }
        if (pos + 4 > max_out_len || seg_count >= 255) return false;

        uint16_t geom = (uint16_t)((start & 0x3FFu) | (((run_len - 1u) & 0x3Fu) << 10));
        out_buf[pos + 0] = (uint8_t)(geom & 0xFFu);
        out_buf[pos + 1] = (uint8_t)((geom >> 8) & 0xFFu);
        out_buf[pos + 2] = (uint8_t)(mask & 0xFFu);
        out_buf[pos + 3] = (uint8_t)((mask >> 8) & 0xFFu);
        pos += 4;
        seg_count++;
    }

    out_buf[0] = 0xA1u;
    out_buf[1] = (uint8_t)seg_count;
    *out_len = pos;
    return true;
}

bool md_decode(const uint8_t *in_buf,
               size_t in_len,
               uint16_t out_owners[FM_PAYLOAD_BLOCKS]) {
    if (!in_buf || !out_owners || in_len < 2) return false;
    if (in_buf[0] != 0xA1u) return false;

    uint16_t seg_count = in_buf[1];
    if (in_len != (size_t)(2 + seg_count * 4)) return false;

    memset(out_owners, 0, sizeof(uint16_t) * FM_PAYLOAD_BLOCKS);
    size_t pos = 2;
    for (uint16_t s = 0; s < seg_count; s++) {
        uint16_t geom = (uint16_t)in_buf[pos] | ((uint16_t)in_buf[pos + 1] << 8);
        uint16_t mask = (uint16_t)in_buf[pos + 2] | ((uint16_t)in_buf[pos + 3] << 8);
        pos += 4;

        uint16_t start = geom & 0x3FFu;
        uint16_t run_len = ((geom >> 10) & 0x3Fu) + 1u;
        if (mask == 0 || start + run_len > FM_PAYLOAD_BLOCKS) return false;

        for (uint16_t k = 0; k < run_len; k++) {
            out_owners[start + k] = mask;
        }
    }
    return true;
}