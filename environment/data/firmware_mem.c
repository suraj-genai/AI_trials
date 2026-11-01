#include "firmware_mem.h"
#include "metadata.h"
#include <stdio.h>
#include <string.h>

/* Internal 32KB physical arena + ground-truth tracking (all static/locked) */
static uint8_t  g_arena[FM_ARENA_BYTES];
static uint16_t g_gt_owners[FM_PAYLOAD_BLOCKS];
static uint32_t g_gt_packet_id[FM_PAYLOAD_BLOCKS];

static bool     g_scratch_used[FM_SCRATCH_BLOCKS];
static uint16_t g_scratch_owners[FM_SCRATCH_BLOCKS];
static uint32_t g_scratch_packet_id[FM_SCRATCH_BLOCKS];

static uint8_t  g_md_buffer[FM_MD_MAX_CHAIN_BYTES];
static size_t   g_md_len = 0;
static bool     g_md_committed_this_step = false;

/* Instruction tracking */
static bool     g_in_step = false;
static bool     g_step_is_alloc = false;
static uint16_t g_step_mask = 0;
static int32_t  g_step_expected_count = 0;
static int32_t  g_step_actual_count = 0;
static int32_t  g_step_Initial_matching_blocks = 0;
static uint32_t g_next_packet_id = 1;
static uint32_t g_rng_state = 0xA53C9E17u;

/* Scoring & telemetry */
static uint64_t g_score_metadata = 0;
static uint64_t g_score_moves = 0;
static size_t   g_peak_md_bytes = 0;
static uint32_t g_over224_steps = 0;
static uint32_t g_over256_steps = 0;
static uint32_t g_total_moves = 0;

static uint32_t xorshift32(void) {
    uint32_t x = g_rng_state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g_rng_state = x;
    return x;
}

static size_t payload_byte_offset(uint16_t pidx) {
    /* Column 0 is 256B metadata; payload starts at Column 1 (offset 256) */
    return FM_MD_PRIMARY_BYTES + ((size_t)pidx * FM_BLOCK_BYTES);
}

static size_t scratch_byte_offset(uint16_t sidx) {
    return FM_MD_PRIMARY_BYTES + ((size_t)(FM_PAYLOAD_BLOCKS + sidx) * FM_BLOCK_BYTES);
}

/* Generate deterministic 32-byte packet for (packet_id, owner_mask) */
static void build_packet_bytes(uint32_t packet_id, uint16_t owner_mask, uint8_t out[32]) {
    uint64_t h = 1469598103934665603ULL;
    out[0] = (uint8_t)(packet_id & 0xFFu);
    out[1] = (uint8_t)((packet_id >> 8) & 0xFFu);
    out[2] = (uint8_t)((packet_id >> 16) & 0xFFu);
    out[3] = (uint8_t)((packet_id >> 24) & 0xFFu);
    out[4] = (uint8_t)(owner_mask & 0xFFu);
    out[5] = (uint8_t)((owner_mask >> 8) & 0xFFu);
    for (int i = 6; i < 24; i++) {
        uint32_t mix = packet_id * 2654435761u + (uint32_t)owner_mask * 40503u + (uint32_t)i * 97u;
        out[i] = (uint8_t)((mix >> ((i % 4) * 8)) & 0xFFu);
    }
    for (int i = 0; i < 24; i++) {
        h ^= (uint64_t)out[i];
        h *= 1099511628211ULL;
    }
    for (int i = 0; i < 8; i++) {
        out[24 + i] = (uint8_t)((h >> (i * 8)) & 0xFFu);
    }
}

static uint64_t compute_step_metadata_penalty(size_t md_len) {
    /* Tier 1: Fast L1 Register Window (0 .. 224 bytes = first 7 blocks of Col 0) */
    if (md_len <= FM_MD_FAST_BYTES) {
        return (uint64_t)md_len;
    }
    /* Tier 2: L1 Contention Zone (225 .. 256 bytes = 8th block of Col 0) */
    if (md_len <= FM_MD_PRIMARY_BYTES) {
        uint64_t over_224 = (uint64_t)(md_len - FM_MD_FAST_BYTES);
        return (uint64_t)FM_MD_FAST_BYTES + (over_224 * over_224 * 4ULL);
    }
    /* Tier 3: Chained Paging Mode (> 256 bytes) */
    uint64_t base_col0 = (uint64_t)FM_MD_FAST_BYTES + (32ULL * 32ULL * 4ULL); /* 4,320 */
    uint64_t chained_bytes = (uint64_t)(md_len - FM_MD_PRIMARY_BYTES);
    uint64_t chained_blocks = (chained_bytes + 31ULL) / 32ULL;
    return base_col0 + (chained_blocks * 2500ULL) + (chained_bytes * 50ULL);
}

void fm_init(void) {
    memset(g_arena, 0, sizeof(g_arena));
    memset(g_gt_owners, 0, sizeof(g_gt_owners));
    memset(g_gt_packet_id, 0, sizeof(g_gt_packet_id));
    memset(g_scratch_used, 0, sizeof(g_scratch_used));
    memset(g_scratch_owners, 0, sizeof(g_scratch_owners));
    memset(g_scratch_packet_id, 0, sizeof(g_scratch_packet_id));
    memset(g_md_buffer, 0, sizeof(g_md_buffer));
    g_md_len = 0;
    g_in_step = false;
    g_next_packet_id = 1;
    g_rng_state = 0xA53C9E17u;
    g_score_metadata = 0;
    g_score_moves = 0;
    g_peak_md_bytes = 0;
    g_over224_steps = 0;
    g_over256_steps = 0;
    g_total_moves = 0;
}

bool fm_begin_instruction(bool is_alloc, uint16_t group_mask, int32_t count) {
    if (g_in_step || group_mask == 0) return false;
    g_in_step = true;
    g_step_is_alloc = is_alloc;
    g_step_mask = group_mask;
    g_step_expected_count = count;
    g_step_actual_count = 0;
    g_md_committed_this_step = false;

    int32_t matching = 0;
    for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS; i++) {
        if (g_gt_owners[i] == group_mask) matching++;
    }
    g_step_Initial_matching_blocks = matching;
    return true;
}

bool fm_alloc_block(uint16_t payload_idx, uint16_t group_mask) {
    if (!g_in_step || !g_step_is_alloc) return false;
    if (payload_idx >= FM_PAYLOAD_BLOCKS) return false;
    if (group_mask != g_step_mask) return false;
    if (g_step_actual_count >= g_step_expected_count) return false;
    if (g_gt_owners[payload_idx] != 0) return false;

    uint32_t pid = g_next_packet_id++;
    g_gt_owners[payload_idx] = group_mask;
    g_gt_packet_id[payload_idx] = pid;
    build_packet_bytes(pid, group_mask, &g_arena[payload_byte_offset(payload_idx)]);
    g_step_actual_count++;
    return true;
}

bool fm_free_block(uint16_t payload_idx) {
    if (!g_in_step || g_step_is_alloc) return false;
    if (payload_idx >= FM_PAYLOAD_BLOCKS) return false;
    /* Must match the exact group_mask requested by DEALLOC */
    if (g_gt_owners[payload_idx] != g_step_mask) return false;
    if (g_step_expected_count >= 0 && g_step_actual_count >= g_step_expected_count) return false;

    g_gt_owners[payload_idx] = 0;
    g_gt_packet_id[payload_idx] = 0;
    memset(&g_arena[payload_byte_offset(payload_idx)], 0, FM_BLOCK_BYTES);
    g_step_actual_count++;
    return true;
}

bool fm_move_block(fm_domain_t src_dom, uint16_t src_idx,
                   fm_domain_t dst_dom, uint16_t dst_idx) {
    if (!g_in_step) return false;
    /* Hardware rule: Payload <-> Scratchpad only (no direct Payload -> Payload moves) */
    if (src_dom == FM_DOMAIN_PAYLOAD && dst_dom == FM_DOMAIN_PAYLOAD) {
        return false;
    }

    if (src_dom == FM_DOMAIN_PAYLOAD && dst_dom == FM_DOMAIN_SCRATCH) {
        if (src_idx >= FM_PAYLOAD_BLOCKS || dst_idx >= FM_SCRATCH_BLOCKS) return false;
        if (g_gt_owners[src_idx] == 0 || g_scratch_used[dst_idx]) return false;

        memcpy(&g_arena[scratch_byte_offset(dst_idx)],
               &g_arena[payload_byte_offset(src_idx)],
               FM_BLOCK_BYTES);
        memset(&g_arena[payload_byte_offset(src_idx)], 0, FM_BLOCK_BYTES);

        g_scratch_used[dst_idx] = true;
        g_scratch_owners[dst_idx] = g_gt_owners[src_idx];
        g_scratch_packet_id[dst_idx] = g_gt_packet_id[src_idx];
        g_gt_owners[src_idx] = 0;
        g_gt_packet_id[src_idx] = 0;
    } else if (src_dom == FM_DOMAIN_SCRATCH && dst_dom == FM_DOMAIN_PAYLOAD) {
        if (src_idx >= FM_SCRATCH_BLOCKS || dst_idx >= FM_PAYLOAD_BLOCKS) return false;
        if (!g_scratch_used[src_idx] || g_gt_owners[dst_idx] != 0) return false;

        memcpy(&g_arena[payload_byte_offset(dst_idx)],
               &g_arena[scratch_byte_offset(src_idx)],
               FM_BLOCK_BYTES);
        memset(&g_arena[scratch_byte_offset(src_idx)], 0, FM_BLOCK_BYTES);

        g_gt_owners[dst_idx] = g_scratch_owners[src_idx];
        g_gt_packet_id[dst_idx] = g_scratch_packet_id[src_idx];
        g_scratch_used[src_idx] = false;
        g_scratch_owners[src_idx] = 0;
        g_scratch_packet_id[src_idx] = 0;
    } else if (src_dom == FM_DOMAIN_SCRATCH && dst_dom == FM_DOMAIN_SCRATCH) {
        if (src_idx >= FM_SCRATCH_BLOCKS || dst_idx >= FM_SCRATCH_BLOCKS) return false;
        if (!g_scratch_used[src_idx] || g_scratch_used[dst_idx]) return false;

        memcpy(&g_arena[scratch_byte_offset(dst_idx)],
               &g_arena[scratch_byte_offset(src_idx)],
               FM_BLOCK_BYTES);
        memset(&g_arena[scratch_byte_offset(src_idx)], 0, FM_BLOCK_BYTES);

        g_scratch_used[dst_idx] = true;
        g_scratch_owners[dst_idx] = g_scratch_owners[src_idx];
        g_scratch_packet_id[dst_idx] = g_scratch_packet_id[src_idx];
        g_scratch_used[src_idx] = false;
        g_scratch_owners[src_idx] = 0;
        g_scratch_packet_id[src_idx] = 0;
    } else {
        return false;
    }

    g_total_moves++;
    g_score_moves += 25ULL; /* 25 bus cycles per 32B DMA transfer */
    return true;
}

bool fm_commit_metadata(const uint8_t *buf, size_t len) {
    if (!g_in_step || buf == NULL || len == 0 || len > FM_MD_MAX_CHAIN_BYTES) return false;
    memcpy(g_md_buffer, buf, len);
    /* Mirror first 256B into physical Column 0 of g_arena */
    size_t col0_copy = (len < FM_MD_PRIMARY_BYTES) ? len : FM_MD_PRIMARY_BYTES;
    memset(g_arena, 0, FM_MD_PRIMARY_BYTES);
    memcpy(g_arena, buf, col0_copy);

    g_md_len = len;
    g_md_committed_this_step = true;
    return true;
}

uint16_t fm_get_block_owner(uint16_t payload_idx) {
    if (payload_idx >= FM_PAYLOAD_BLOCKS) return 0;
    return g_gt_owners[payload_idx];
}

void fm_get_all_owners(uint16_t out_owners[FM_PAYLOAD_BLOCKS]) {
    memcpy(out_owners, g_gt_owners, sizeof(g_gt_owners));
}

static void generate_canary_map(uint16_t out_map[FM_PAYLOAD_BLOCKS]) {
    uint16_t palette[6];
    for (int i = 0; i < 6; i++) {
        palette[i] = (uint16_t)((xorshift32() & 0xFFFu) | 1u);
    }
    uint16_t idx = 0;
    while (idx < FM_PAYLOAD_BLOCKS) {
        uint16_t run_len = (uint16_t)(8u + (xorshift32() % 45u));
        uint16_t pick = (xorshift32() % 3u == 0u) ? 0u : palette[xorshift32() % 6u];
        for (uint16_t k = 0; k < run_len && idx < FM_PAYLOAD_BLOCKS; k++, idx++) {
            out_map[idx] = pick;
        }
    }
}

bool fm_end_instruction(uint32_t step_num) {
    if (!g_in_step) return false;
    g_in_step = false;

    /* 1. Check instruction count fulfillment */
    if (g_step_is_alloc) {
        if (g_step_actual_count != g_step_expected_count) {
            fprintf(stderr, "[Step %u] FAIL: ALLOC expected %d blocks, allocated %d\n",
                    step_num, g_step_expected_count, g_step_actual_count);
            return false;
        }
    } else {
        int32_t expected_free = (g_step_expected_count < 0)
            ? g_step_Initial_matching_blocks
            : ((g_step_expected_count < g_step_Initial_matching_blocks)
                ? g_step_expected_count : g_step_Initial_matching_blocks);
        if (g_step_actual_count != expected_free) {
            fprintf(stderr, "[Step %u] FAIL: DEALLOC expected %d freed blocks, freed %d\n",
                    step_num, expected_free, g_step_actual_count);
            return false;
        }
    }

    /* 2. Verify all scratchpad blocks are empty at end of instruction */
    for (uint16_t s = 0; s < FM_SCRATCH_BLOCKS; s++) {
        if (g_scratch_used[s]) {
            fprintf(stderr, "[Step %u] FAIL: Scratchpad block %u left occupied\n", step_num, s);
            return false;
        }
    }

    /* 3. Verify 32-byte packet integrity for all 824 payload blocks */
    uint8_t expected_pkt[FM_BLOCK_BYTES];
    for (uint16_t i = 0; i < FM_PAYLOAD_BLOCKS; i++) {
        const uint8_t *actual_pkt = &g_arena[payload_byte_offset(i)];
        if (g_gt_owners[i] == 0) {
            for (size_t b = 0; b < FM_BLOCK_BYTES; b++) {
                if (actual_pkt[b] != 0) {
                    fprintf(stderr, "[Step %u] FAIL: Free block %u non-zero byte\n", step_num, i);
                    return false;
                }
            }
        } else {
            build_packet_bytes(g_gt_packet_id[i], g_gt_owners[i], expected_pkt);
            if (memcmp(actual_pkt, expected_pkt, FM_BLOCK_BYTES) != 0) {
                fprintf(stderr, "[Step %u] FAIL: 32B packet corrupted at block %u\n", step_num, i);
                return false;
            }
        }
    }

    /* 4. Verify metadata was committed and passes anti-cheat canary + blind round-trip */
    if (!g_md_committed_this_step) {
        fprintf(stderr, "[Step %u] FAIL: Metadata not committed\n", step_num);
        return false;
    }

    uint16_t canary_a[FM_PAYLOAD_BLOCKS], canary_b[FM_PAYLOAD_BLOCKS];
    uint8_t  buf_a[FM_MD_MAX_CHAIN_BYTES], buf_b[FM_MD_MAX_CHAIN_BYTES];
    size_t   len_a = 0, len_b = 0;

    generate_canary_map(canary_a);
    generate_canary_map(canary_b);

    /* Calling md_encode on canary maps overwrites any static shadow state in metadata.c */
    if (!md_encode(canary_a, buf_a, sizeof(buf_a), &len_a) ||
        !md_encode(canary_b, buf_b, sizeof(buf_b), &len_b)) {
        fprintf(stderr, "[Step %u] FAIL: Canary md_encode failed\n", step_num);
        return false;
    }

    /* Out-of-order blind decode: canary_a, then real committed buffer, then canary_b */
    uint16_t dec_a[FM_PAYLOAD_BLOCKS], dec_real[FM_PAYLOAD_BLOCKS], dec_b[FM_PAYLOAD_BLOCKS];
    if (!md_decode(buf_a, len_a, dec_a) ||
        !md_decode(g_md_buffer, g_md_len, dec_real) ||
        !md_decode(buf_b, len_b, dec_b)) {
        fprintf(stderr, "[Step %u] FAIL: md_decode returned false\n", step_num);
        return false;
    }

    if (memcmp(dec_a, canary_a, sizeof(canary_a)) != 0 ||
        memcmp(dec_b, canary_b, sizeof(canary_b)) != 0) {
        fprintf(stderr, "[Step %u] FAIL: Canary round-trip mismatch (stateful metadata cheat detected)\n",
                step_num);
        return false;
    }

    if (memcmp(dec_real, g_gt_owners, sizeof(g_gt_owners)) != 0) {
        fprintf(stderr, "[Step %u] FAIL: Decoded metadata does not match physical arena owners\n",
                step_num);
        return false;
    }

    /* 5. Update telemetry and penalty score */
    if (g_md_len > g_peak_md_bytes) g_peak_md_bytes = g_md_len;
    if (g_md_len > FM_MD_FAST_BYTES) g_over224_steps++;
    if (g_md_len > FM_MD_PRIMARY_BYTES) g_over256_steps++;

    g_score_metadata += compute_step_metadata_penalty(g_md_len);
    return true;
}

uint64_t fm_get_total_score(void)    { return g_score_metadata + g_score_moves; }
uint64_t fm_get_metadata_score(void) { return g_score_metadata; }
uint64_t fm_get_move_score(void)     { return g_score_moves; }
size_t   fm_get_peak_md_bytes(void)  { return g_peak_md_bytes; }
uint32_t fm_get_over224_steps(void)  { return g_over224_steps; }
uint32_t fm_get_over256_steps(void)  { return g_over256_steps; }
uint32_t fm_get_total_moves(void)    { return g_total_moves; }

void fm_get_metadata(const uint8_t **buf, size_t *len)
{
    if (buf) *buf = g_md_buffer;
    if (len) *len = g_md_len;
}
