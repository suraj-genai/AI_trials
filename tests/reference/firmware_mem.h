#ifndef FIRMWARE_MEM_H
#define FIRMWARE_MEM_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#define FM_ARENA_BYTES        32768u
#define FM_BLOCK_BYTES        32u
#define FM_ROWS               8u
#define FM_TOTAL_COLS         128u
#define FM_TOTAL_BLOCKS       (FM_TOTAL_COLS * FM_ROWS) /* 1024 blocks */

#define FM_MD_PRIMARY_BYTES   256u
#define FM_MD_FAST_BYTES      224u

#define FM_MD_EXTENSION_BYTES (FM_BLOCK_BYTES * FM_ROWS) /* 256 B */
#define FM_MD_MAX_CHAIN_BYTES \
    (FM_MD_PRIMARY_BYTES + FM_MD_EXTENSION_BYTES)        /* 512 B */

#define FM_PAYLOAD_COLS       103u
#define FM_PAYLOAD_BLOCKS     (FM_PAYLOAD_COLS * FM_ROWS) /* 824 */

#define FM_SCRATCH_COLS       20u
#define FM_SCRATCH_BLOCKS     (FM_SCRATCH_COLS * FM_ROWS) /* 160 */

#define FM_RESTRICTED_COLS    4u
#define FM_RESTRICTED_BLOCKS  (FM_RESTRICTED_COLS * FM_ROWS) /* 32 */

typedef enum {
    FM_DOMAIN_PAYLOAD = 0,
    FM_DOMAIN_SCRATCH = 1
} fm_domain_t;

bool fm_alloc_block(uint16_t payload_idx, uint16_t group_mask);
bool fm_free_block(uint16_t payload_idx);
bool fm_move_block(fm_domain_t src_dom, uint16_t src_idx,
                   fm_domain_t dst_dom, uint16_t dst_idx);
bool fm_commit_metadata(const uint8_t *buf, size_t len);

uint16_t fm_get_block_owner(uint16_t payload_idx);
void     fm_get_all_owners(uint16_t out_owners[FM_PAYLOAD_BLOCKS]);

void     fm_init(void);
bool     fm_begin_instruction(bool is_alloc, uint16_t group_mask, int32_t count);
bool     fm_end_instruction(uint32_t step_num);
uint64_t fm_get_total_score(void);
uint64_t fm_get_metadata_score(void);
uint64_t fm_get_move_score(void);
size_t   fm_get_peak_md_bytes(void);
uint32_t fm_get_over224_steps(void);
uint32_t fm_get_over256_steps(void);
uint32_t fm_get_total_moves(void);
void fm_get_metadata(const uint8_t **buf, size_t *len);

#endif /* FIRMWARE_MEM_H */