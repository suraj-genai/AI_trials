#ifndef TEST_HARNESS_H
#define TEST_HARNESS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t instruction_count;
    uint64_t total_score;
    uint64_t metadata_score;
    uint64_t move_score;
    size_t peak_metadata_bytes;
    uint32_t steps_over_224_bytes;
    uint32_t steps_over_256_bytes;
    uint32_t total_moves;
} TestHarnessResult;

/*
 * Execute one workload from a trusted file path.
 *
 * The function calls fm_init() and allocator_init(), executes every valid
 * instruction, and relies on fm_end_instruction() for the simulator's
 * per-instruction integrity, codec round-trip, and scoring checks.
 *
 * Returns true only when the complete workload passes.
 */
bool test_harness_run_workload(const char *workload_path,
                               TestHarnessResult *result,
                               char *error_buffer,
                               size_t error_buffer_size);

#endif
