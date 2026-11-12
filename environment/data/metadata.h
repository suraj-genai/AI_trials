#ifndef METADATA_H
#define METADATA_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "firmware_mem.h"


bool md_encode(const uint16_t owners[FM_PAYLOAD_BLOCKS],
               uint8_t *out_buf,
               size_t max_out_len,
               size_t *out_len);

bool md_decode(const uint8_t *in_buf,
               size_t in_len,
               uint16_t out_owners[FM_PAYLOAD_BLOCKS]);

#endif /* METADATA_H */