#include "allocator.h"
#include "firmware_mem.h"
#include "metadata.h"

static bool sync_metadata(void) {
    uint16_t owners[FM_PAYLOAD_BLOCKS];
    uint8_t  md_buf[FM_MD_MAX_CHAIN_BYTES];
    size_t   md_len = 0;

    fm_get_all_owners(owners);
    if (!md_encode(owners, md_buf, sizeof(md_buf), &md_len)) return false;
    return fm_commit_metadata(md_buf, md_len);
}

void allocator_init(void) {}

bool allocator_alloc(uint16_t group_mask, uint32_t count) {
    uint32_t allocated = 0;
    for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS && allocated < count; i++) {
        if (fm_get_block_owner(i) == 0) {
            if (!fm_alloc_block(i, group_mask)) return false;
            allocated++;
        }
    }
    if (allocated != count) return false;
    return sync_metadata();
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
    return sync_metadata();
}