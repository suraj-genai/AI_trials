#ifndef GROUND_TRUTH_H
#define GROUND_TRUTH_H

#include <stdint.h>
#include <stdbool.h>
#include "firmware_mem.h"

/*
 * Trusted reference ownership state.
 *
 * This represents the semantic state of the payload arena:
 *   0      = free
 *   nonzero = entity/group ownership mask
 *
 * This module contains no allocator policy and no metadata encoding.
 */

void gt_init(void);

uint16_t gt_get_owner(uint16_t payload_idx);
void gt_get_all_owners(uint16_t out_owners[FM_PAYLOAD_BLOCKS]);

bool gt_set_owner(uint16_t payload_idx, uint16_t group_mask);
bool gt_clear_owner(uint16_t payload_idx, uint16_t expected_group_mask);

int32_t gt_count_owner(uint16_t group_mask);
#endif