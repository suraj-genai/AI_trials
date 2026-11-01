#define _POSIX_C_SOURCE 200809L

#include "test_harness.h"

#include "firmware_mem.h"
#include "allocator.h"

#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TRACE_LINE_BYTES 512u

static void set_error(char *dst, size_t dst_size,
                      const char *message, unsigned long line_number)
{
    if (dst == NULL || dst_size == 0u) {
        return;
    }

    if (line_number > 0u) {
        (void)snprintf(dst, dst_size, "line %lu: %s", line_number, message);
    } else {
        (void)snprintf(dst, dst_size, "%s", message);
    }
}

static char *trim(char *text)
{
    char *end;

    while (*text != '\0' && isspace((unsigned char)*text)) {
        text++;
    }

    if (*text == '\0') {
        return text;
    }

    end = text + strlen(text) - 1u;
    while (end > text && isspace((unsigned char)*end)) {
        *end = '\0';
        end--;
    }

    return text;
}

/* The workload uses decimal entity IDs 1..16, separated by spaces/commas. */
static bool parse_group_mask(const char *text, uint16_t *mask_out)
{
    const char *cursor = text;
    uint16_t mask = 0u;
    bool found_entity = false;

    if (text == NULL || mask_out == NULL) {
        return false;
    }

    while (*cursor != '\0') {
        char *end = NULL;
        long entity;

        if (isspace((unsigned char)*cursor) || *cursor == ',') {
            cursor++;
            continue;
        }

        errno = 0;
        entity = strtol(cursor, &end, 10);
        if (end == cursor || errno == ERANGE || entity < 1 || entity > 16) {
            return false;
        }

        mask |= (uint16_t)(1u << (unsigned int)(entity - 1));
        found_entity = true;
        cursor = end;

        if (*cursor != '\0' &&
            !isspace((unsigned char)*cursor) &&
            *cursor != ',') {
            return false;
        }
    }

    *mask_out = mask;
    return found_entity && mask != 0u;
}

static bool parse_count(const char *text, bool is_alloc, int32_t *count_out)
{
    char *end = NULL;
    long value;
    char *trimmed;

    if (count_out == NULL) {
        return false;
    }

    if (text == NULL) {
        if (is_alloc) {
            return false;
        }
        *count_out = -1; /* Empty DEALLOC count means free all matching blocks. */
        return true;
    }

    trimmed = trim((char *)text);
    if (*trimmed == '\0') {
        if (is_alloc) {
            return false;
        }
        *count_out = -1;
        return true;
    }

    errno = 0;
    value = strtol(trimmed, &end, 10);
    if (end == trimmed || errno == ERANGE) {
        return false;
    }

    while (*end != '\0' && isspace((unsigned char)*end)) {
        end++;
    }
    if (*end != '\0') {
        return false;
    }

    if (is_alloc) {
        if (value <= 0 || value > INT32_MAX) {
            return false;
        }
    } else if (value < -1 || value > INT32_MAX) {
        return false;
    }

    *count_out = (int32_t)value;
    return true;
}

static bool execute_instruction(char *line,
                                 uint32_t step_number,
                                 char *error_buffer,
                                 size_t error_buffer_size)
{
    char *save = NULL;
    char *operation;
    char *entities;
    char *count_text;
    char *unexpected;
    uint16_t group_mask;
    int32_t count;
    bool is_alloc;
    bool operation_ok;

    operation = strtok_r(line, "|", &save);
    entities = strtok_r(NULL, "|", &save);
    count_text = strtok_r(NULL, "|", &save);
    unexpected = strtok_r(NULL, "|", &save);

    if (operation == NULL || entities == NULL || unexpected != NULL) {
        set_error(error_buffer, error_buffer_size,
                  "expected OPERATION | ENTITY_IDS | COUNT", step_number);
        return false;
    }

    operation = trim(operation);
    entities = trim(entities);
    if (strcmp(operation, "ALLOC") == 0) {
        is_alloc = true;
    } else if (strcmp(operation, "DEALLOC") == 0) {
        is_alloc = false;
    } else {
        set_error(error_buffer, error_buffer_size,
                  "operation must be ALLOC or DEALLOC", step_number);
        return false;
    }

    if (!parse_group_mask(entities, &group_mask)) {
        set_error(error_buffer, error_buffer_size,
                  "entity IDs must be integers in the range 1..16", step_number);
        return false;
    }

    if (!parse_count(count_text, is_alloc, &count)) {
        set_error(error_buffer, error_buffer_size,
                  "invalid allocation/deallocation count", step_number);
        return false;
    }

    if (!fm_begin_instruction(is_alloc, group_mask, count)) {
        set_error(error_buffer, error_buffer_size,
                  "fm_begin_instruction rejected the request", step_number);
        return false;
    }

    operation_ok = is_alloc
        ? allocator_alloc(group_mask, (uint32_t)count)
        : allocator_dealloc(group_mask, count);

    if (!operation_ok) {
        set_error(error_buffer, error_buffer_size,
                  "allocator operation returned false", step_number);
        return false;
    }

    if (!fm_end_instruction(step_number)) {
        set_error(error_buffer, error_buffer_size,
                  "trusted firmware validation failed", step_number);
        return false;
    }

    return true;
}

bool test_harness_run_workload(const char *workload_path,
                               TestHarnessResult *result,
                               char *error_buffer,
                               size_t error_buffer_size)
{
    FILE *workload;
    char line[TRACE_LINE_BYTES];
    unsigned long line_number = 0u;
    uint32_t instruction_count = 0u;

    if (workload_path == NULL || result == NULL) {
        set_error(error_buffer, error_buffer_size, "invalid harness arguments", 0u);
        return false;
    }

    memset(result, 0, sizeof(*result));
    if (error_buffer != NULL && error_buffer_size > 0u) {
        error_buffer[0] = '\0';
    }

    workload = fopen(workload_path, "r");
    if (workload == NULL) {
        if (error_buffer != NULL && error_buffer_size > 0u) {
            (void)snprintf(error_buffer, error_buffer_size,
                           "cannot open workload '%s': %s",
                           workload_path, strerror(errno));
        }
        return false;
    }

    fm_init();
    allocator_init();

    while (fgets(line, sizeof(line), workload) != NULL) {
        char *content;
        line_number++;

        if (strchr(line, '\n') == NULL && !feof(workload)) {
            set_error(error_buffer, error_buffer_size,
                      "line exceeds the harness line-buffer limit", line_number);
            (void)fclose(workload);
            return false;
        }

        content = trim(line);
        if (*content == '\0' || *content == '#') {
            continue;
        }

        instruction_count++;
        if (!execute_instruction(content, instruction_count,
                                 error_buffer, error_buffer_size)) {
            (void)fclose(workload);
            return false;
        }
    }

    if (ferror(workload)) {
        set_error(error_buffer, error_buffer_size, "error reading workload", 0u);
        (void)fclose(workload);
        return false;
    }

    (void)fclose(workload);

    if (instruction_count == 0u) {
        set_error(error_buffer, error_buffer_size, "workload contains no instructions", 0u);
        return false;
    }

    result->instruction_count = instruction_count;
    result->total_score = fm_get_total_score();
    result->metadata_score = fm_get_metadata_score();
    result->move_score = fm_get_move_score();
    result->peak_metadata_bytes = fm_get_peak_md_bytes();
    result->steps_over_224_bytes = fm_get_over224_steps();
    result->steps_over_256_bytes = fm_get_over256_steps();
    result->total_moves = fm_get_total_moves();

    return true;
}

int main(int argc, char **argv)
{
    TestHarnessResult result;
    char error_buffer[256];

    if (argc != 2) {
        (void)fprintf(stderr, "usage: %s <trusted-workload-path>\n", argv[0]);
        return 64;
    }

    if (!test_harness_run_workload(argv[1], &result,
                                   error_buffer, sizeof(error_buffer))) {
        (void)fprintf(stderr, "HARNESS_FAIL: %s\n", error_buffer);
        return 1;
    }

    (void)printf(
        "RESULT {\"instructions\":%" PRIu32
        ",\"total_score\":%" PRIu64
        ",\"metadata_score\":%" PRIu64
        ",\"move_score\":%" PRIu64
        ",\"peak_metadata_bytes\":%zu"
        ",\"steps_over_224\":%" PRIu32
        ",\"steps_over_256\":%" PRIu32
        ",\"total_moves\":%" PRIu32 "}\n",
        result.instruction_count,
        result.total_score,
        result.metadata_score,
        result.move_score,
        result.peak_metadata_bytes,
        result.steps_over_224_bytes,
        result.steps_over_256_bytes,
        result.total_moves);

    return 0;
}
