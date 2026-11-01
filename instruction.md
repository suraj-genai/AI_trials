Repair the supplied C implementation of a fixed-size low-level memory allocator.

The allocator implementation is provided in:

`/app/firmware_mem.h`
`/app/firmware_mem.c`
`/app/allocator.h`
`/app/allocator.c`
`/app/metadata.h`
`/app/metadata.c`
`/app/main.c`

The allocator manages a 32 KiB memory arena divided into 128 columns of 256 bytes each.

The arena is organized as follows:

- Column 0 is reserved for allocator metadata.
- Columns 1–124 are available for application payload storage.
- Columns 125–127 are reserved workspace for internal allocator operations.

The processor issues logical memory-management requests such as allocating memory for variables, releasing allocations, resizing allocations, and sharing portions of existing allocations. The allocator is responsible for selecting and maintaining the physical memory layout.

The implementation must correctly maintain:

- logical-to-physical mappings for all active variables;
- allocation and release of payload space;
- fragmented free space;
- resizing of existing allocations;
- sharing of physical memory between variables;
- correct reference/lifetime handling of shared regions;
- consistency between allocator state and the metadata stored in the arena header;
- valid metadata throughout the supplied workload;
- the fixed arena geometry and reserved regions.

The supplied codebase contains one or more implementation defects. Repair the implementation so that the complete workload executes successfully and the allocator remains internally consistent throughout.

Do not change the arena size or column layout, remove allocator functionality, or replace the implementation with an external memory-management mechanism.