#ifndef METADATA_H
#define METADATA_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "firmware_mem.h"

/*
 * Stateless Metadata Codec API:
 * - md_encode: Encodes the 824 payload block owner masks into out_buf.
 * - md_decode: Reconstructs the 824 payload block owner masks solely from in_buf[0..in_len-1].
 */
bool md_encode(const uint16_t owners[FM_PAYLOAD_BLOCKS],
               uint8_t *out_buf,
               size_t max_out_len,
               size_t *out_len);

bool md_decode(const uint8_t *in_buf,
               size_t in_len,
               uint16_t out_owners[FM_PAYLOAD_BLOCKS]);

#endif /* METADATA_H */