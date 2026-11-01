#ifndef ALLOCATOR_H
#define ALLOCATOR_H

#include <stdint.h>
#include <stdbool.h>

void allocator_init(void);
bool allocator_alloc(uint16_t group_mask, uint32_t count);
bool allocator_dealloc(uint16_t group_mask, int32_t count); /* count == -1 means DEALLOC ALL */

#endif /* ALLOCATOR_H */