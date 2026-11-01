#include "ground_truth.h"
#include <string.h>

static uint16_t g_owners[FM_PAYLOAD_BLOCKS];

void gt_init(void)
{
    memset(g_owners, 0, sizeof(g_owners));
}

uint16_t gt_get_owner(uint16_t payload_idx)
{
    if (payload_idx >= FM_PAYLOAD_BLOCKS) {
        return 0;
    }

    return g_owners[payload_idx];
}

void gt_get_all_owners(uint16_t out_owners[FM_PAYLOAD_BLOCKS])
{
    if (out_owners == NULL) {
        return;
    }

    memcpy(out_owners, g_owners, sizeof(g_owners));
}

bool gt_set_owner(uint16_t payload_idx, uint16_t group_mask)
{
    if (payload_idx >= FM_PAYLOAD_BLOCKS) {
        return false;
    }

    if (group_mask == 0) {
        return false;
    }

    if (g_owners[payload_idx] != 0) {
        return false;
    }

    g_owners[payload_idx] = group_mask;
    return true;
}

bool gt_clear_owner(uint16_t payload_idx, uint16_t expected_group_mask)
{
    if (payload_idx >= FM_PAYLOAD_BLOCKS) {
        return false;
    }

    if (expected_group_mask == 0) {
        return false;
    }

    if (g_owners[payload_idx] != expected_group_mask) {
        return false;
    }

    g_owners[payload_idx] = 0;
    return true;
}

int32_t gt_count_owner(uint16_t group_mask)
{
    if (group_mask == 0) {
        return 0;
    }

    int32_t count = 0;

    for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS; i++) {
        if (g_owners[i] == group_mask) {
            count++;
        }
    }

    return count;
}