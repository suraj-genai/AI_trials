#include "allocator.h"
#include "firmware_mem.h"
#include "metadata.h"
#include <string.h>


static bool compact_arena_via_scratchpad(void) {
    uint16_t owners[FM_PAYLOAD_BLOCKS];
    fm_get_all_owners(owners);

    uint16_t groups[64];
    uint8_t g_count = 0;
    for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS; i++) {
        uint16_t m = owners[i];
        if (m == 0) continue;
        bool seen = false;
        for (uint8_t g = 0; g < g_count; g++) {
            if (groups[g] == m) { seen = true; break; }
        }
        if (!seen && g_count < 64) groups[g_count++] = m;
    }

    uint16_t target_mask[FM_PAYLOAD_BLOCKS];
    memset(target_mask, 0, sizeof(target_mask));
    uint16_t write_cursor = 0;
    for (uint8_t g = 0; g < g_count; g++) {
        uint16_t m = groups[g];
        for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS; i++) {
            if (owners[i] == m) {
                target_mask[write_cursor++] = m;
            }
        }
    }

    uint16_t scratch_src_mask[FM_SCRATCH_BLOCKS];
    while (1) {
        uint16_t s_count = 0;
        for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS && s_count < FM_SCRATCH_BLOCKS; i++) {
            uint16_t cur = fm_get_block_owner(i);
            if (cur != 0 && cur != target_mask[i]) {
                if (!fm_move_block(FM_DOMAIN_PAYLOAD, i, FM_DOMAIN_SCRATCH, s_count)) return false;
                scratch_src_mask[s_count++] = cur;
            }
        }
        if (s_count == 0) break;

        for (uint16_t s = 0; s < s_count; s++) {
            uint16_t m = scratch_src_mask[s];
            bool placed = false;
            for (uint16_t j = 0; j < FM_PAYLOAD_BLOCKS; j++) {
                if (fm_get_block_owner(j) == 0 && target_mask[j] == m) {
                    if (!fm_move_block(FM_DOMAIN_SCRATCH, s, FM_DOMAIN_PAYLOAD, j)) return false;
                    placed = true;
                    break;
                }
            }
            if (!placed) {
                for (uint16_t j = 0; j < FM_PAYLOAD_BLOCKS; j++) {
                    if (fm_get_block_owner(j) == 0) {
                        if (!fm_move_block(FM_DOMAIN_SCRATCH, s, FM_DOMAIN_PAYLOAD, j)) return false;
                        break;
                    }
                }
            }
        }
    }
    return true;
}

static bool sync_metadata_with_lazy_compaction(void) {
    uint16_t owners[FM_PAYLOAD_BLOCKS];
    uint8_t  md_buf[FM_MD_MAX_CHAIN_BYTES];
    size_t   md_len = 0;

    fm_get_all_owners(owners);
    if (!md_encode(owners, md_buf, sizeof(md_buf), &md_len)) return false;

    if (md_len > 216u) {
        if (!compact_arena_via_scratchpad()) return false;
        fm_get_all_owners(owners);
        if (!md_encode(owners, md_buf, sizeof(md_buf), &md_len)) return false;
    }
    return fm_commit_metadata(md_buf, md_len);
}

void allocator_init(void) {}

bool allocator_alloc(uint16_t group_mask, uint32_t count) {
    uint32_t allocated = 0;

    while (allocated < count) {
        bool found_adj = false;
        for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS && allocated < count; i++) {
            if (fm_get_block_owner(i) != 0) continue;
            bool left_match  = (i > 0 && fm_get_block_owner(i - 1) == group_mask);
            bool right_match = (i + 1 < FM_PAYLOAD_BLOCKS && fm_get_block_owner(i + 1) == group_mask);
            if (left_match || right_match) {
                if (!fm_alloc_block(i, group_mask)) return false;
                allocated++;
                found_adj = true;
            }
        }
        if (!found_adj) break;
    }

    uint32_t rem = count - allocated;
    if (rem > 0) {
        uint16_t best_start = 0xFFFFu;
        uint16_t best_len = 0xFFFFu;
        uint16_t i = 0;
        while (i < FM_PAYLOAD_BLOCKS) {
            if (fm_get_block_owner(i) != 0) { i++; continue; }
            uint16_t start = i;
            while (i < FM_PAYLOAD_BLOCKS && fm_get_block_owner(i) == 0) i++;
            uint16_t len = i - start;
            if (len >= rem && len < best_len) {
                best_len = len;
                best_start = start;
            }
        }
        if (best_start != 0xFFFFu) {
            for (uint32_t k = 0; k < rem; k++) {
                if (!fm_alloc_block((uint16_t)(best_start + k), group_mask)) return false;
                allocated++;
            }
        }
    }

    for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS && allocated < count; i++) {
        if (fm_get_block_owner(i) == 0) {
            if (!fm_alloc_block(i, group_mask)) return false;
            allocated++;
        }
    }

    if (allocated != count) return false;
    return sync_metadata_with_lazy_compaction();
}

bool allocator_dealloc(uint16_t group_mask, int32_t count) {
    int32_t freed = 0;
    for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS; i++) {
        if (count >= 0 && freed >= count) break;
        if (fm_get_block_owner(i) == group_mask) {
            if (!fm_free_block(i)) return false;
            freed++;
        }
    }
    return sync_metadata_with_lazy_compaction();
}